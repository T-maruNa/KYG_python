"""
AI 銘柄予測。

Python 側で事前にスコアリング・絞り込みを済ませた候補を受け取り、
rei / mirai 向けに AI へ渡して選ばせる。
ritu（律）は AI を使わず、フィルタ済み候補からランダム選定する。

朝バッチの前処理フロー:
    FeatureBuilder → CandidateFilter → CandidateScorer → StockPredictor.predict()
"""
import csv
import io
import math
import random
from typing import List, Dict, Optional
from src.characters import get_analysts
from src.characters.ichinose import IchinoseRitu
from src.database.t_stock_predict_manager import TStockPredictManager
from src.database.m_stock_manager import MStockManager
from src.database.t_stock_actual_manager import TStockActualManager
from src.core.ai_budget_guard import AIBudgetGuard
from src.core.feature_calculator import FeatureCalculator
from src.core.prompt_loader import PromptLoader


RANGE_LIMITS = {100: 300_000, 1000: 300_000, 10000: 400_000}
RANGE_LABEL  = {
    100:   '小型株(100円以下)',
    1000:  '中型株(101〜1000円)',
    10000: '大型株(1001〜10000円)',
}


class StockPredictor:
    def __init__(self):
        self.analysts = get_analysts()
        self.predict_manager = TStockPredictManager()
        self.m_stock_manager = MStockManager()
        self.actual_manager  = TStockActualManager()
        self.guard = AIBudgetGuard()
        self.feature_calc = FeatureCalculator()

    # ------------------------------------------------------------------
    # メインエントリー
    # ------------------------------------------------------------------

    def predict(self, yesterday_date: str, tomorrow_date: str,
                active_ranges_by_analyst: Dict[str, List[int]] = None,
                ranking_by_analyst: Dict[str, Dict] = None,
                scored_candidates: List[Dict] = None) -> None:
        """
        株価予測を実行してDBに保存する。

        Args:
            yesterday_date: 株価データ基準日（前営業日）
            tomorrow_date: エントリー対象日（今日）
            active_ranges_by_analyst: {analyst_name: [100, 1000, 10000]}
            ranking_by_analyst: {analyst_name: {rank, total, gap_from_first}}
            scored_candidates: CandidateScorer.score_and_rank() の結果。
                               渡された場合はこの候補を AI に提示する。
                               None の場合は従来の FeatureCalculator にフォールバック。
        """
        all_active = sorted({
            r
            for ranges in (active_ranges_by_analyst or {}).values()
            for r in ranges
        }) or [100, 1000, 10000]

        # ---- rei / mirai 向け CSV 生成 ----
        if scored_candidates:
            # スコアリング済み候補から AI 用 CSV を組み立てる
            candidates_by_range = self._group_by_range(
                scored_candidates, all_active
            )
            csv_text = self._candidates_to_csv(candidates_by_range, all_active)
        else:
            # フォールバック: 従来の FeatureCalculator を使う
            stock_data = self.actual_manager.get_stock_actual(
                date_from=yesterday_date
            )
            if not stock_data:
                print(f'警告: {yesterday_date} の株価データが見つかりません')
                return
            csv_text = self.feature_calc.build_feature_csv(
                yesterday_date, active_ranges=all_active
            )
            if not csv_text:
                print(f'警告: {yesterday_date} の特徴量データが不足しています')
                return

        # ---- rei / mirai: AI に選ばせる ----
        for analyst in self.analysts:
            if analyst.name == 'ritu':
                continue  # 律は別処理
            active_ranges = (
                active_ranges_by_analyst.get(analyst.name, [100, 1000, 10000])
                if active_ranges_by_analyst
                else [100, 1000, 10000]
            )
            if not active_ranges:
                print(f'{analyst.name_jp}: 投資可能な価格帯がありません')
                continue
            try:
                ranking_info = (
                    ranking_by_analyst.get(analyst.name) if ranking_by_analyst else None
                )
                messages = self._build_messages(
                    analyst, csv_text, yesterday_date, tomorrow_date,
                    active_ranges, ranking_info=ranking_info,
                )
                result = self.guard.execute(
                    analyst.stock_run, messages,
                    call_type='prediction', model='openai',
                )
                if not result:
                    print(f'警告: {analyst.name_jp} からの応答がありません（予算上限またはエラー）')
                    continue
                self._save_predictions(
                    result, analyst, tomorrow_date, yesterday_date, active_ranges
                )
            except Exception as e:
                print(f'エラー: {analyst.name_jp} の処理中にエラー: {e}')

        # ---- 律: フィルタ済み候補からランダム選定 ----
        ritu_ranges = (
            active_ranges_by_analyst.get('ritu', [100, 1000, 10000])
            if active_ranges_by_analyst
            else [100, 1000, 10000]
        )
        if scored_candidates:
            self._predict_ritu_from_candidates(
                scored_candidates, tomorrow_date, ritu_ranges
            )
        else:
            # フォールバック: 従来の raw stock_data ランダム
            stock_data = self.actual_manager.get_stock_actual(
                date_from=yesterday_date
            )
            self._predict_ritu_legacy(stock_data or [], tomorrow_date, ritu_ranges)

    # ------------------------------------------------------------------
    # AI 用 CSV 生成
    # ------------------------------------------------------------------

    def _candidates_to_csv(self, candidates_by_range: Dict[int, List[Dict]],
                           active_ranges: List[int]) -> str:
        """スコアリング済み候補を AI へ渡す CSV 形式に変換する。"""
        header = (
            '証券コード,銘柄名,価格帯,終値,前日比率,'
            '5日騰落率,20日騰落率,出来高変化率,'
            'MA5乖離率,MA20乖離率,ボラティリティ,スコア,特徴'
        )
        rows = [header]
        for r in active_ranges:
            for c in candidates_by_range.get(r, []):
                rows.append(
                    f"{c['stock_code']},{c['stock_name']},{RANGE_LABEL.get(r, r)},"
                    f"{c['close']},{c['day_change_rate']},"
                    f"{c['rise_5']},{c['rise_20']},{c['vol_change_rate']},"
                    f"{c['ma5_dev']},{c['ma20_dev']},{c['volatility']},"
                    f"{c.get('common_score', 0)},{c.get('feature_label', '')}"
                )
        return '\n'.join(rows)

    @staticmethod
    def _group_by_range(candidates: List[Dict],
                        active_ranges: List[int]) -> Dict[int, List[Dict]]:
        result: Dict[int, List[Dict]] = {r: [] for r in active_ranges}
        for c in candidates:
            r = c.get('price_range')
            if r in result:
                result[r].append(c)
        return result

    # ------------------------------------------------------------------
    # AI プロンプト構築
    # ------------------------------------------------------------------

    def _build_messages(self, analyst, csv_text: str, yesterday_date: str,
                        tomorrow_date: str, active_ranges: List[int],
                        ranking_info: Dict = None) -> List[Dict]:
        range_desc = '\n'.join(
            f'・{RANGE_LABEL[r]}から1銘柄' for r in active_ranges
        )

        strategy_hint = ''
        if ranking_info:
            rank  = ranking_info.get('rank', 1)
            total = ranking_info.get('total', 1)
            gap   = ranking_info.get('gap_from_first', 0)
            if rank == 1:
                strategy_hint = (
                    '\nあなたは現在1位です。リードを守るため、安定・低リスクな銘柄を優先してください。'
                )
            elif rank == total or gap > 100_000:
                strategy_hint = (
                    f'\nあなたは現在{rank}位（最下位付近）で、1位との差は{gap:,}円です。'
                    f'逆転するためにはギャンブル的な高ボラティリティ銘柄を狙ってください。'
                    f'リスクを恐れず、大きく動きそうな銘柄を選んでください。'
                )
            else:
                strategy_hint = (
                    f'\nあなたは現在{rank}位で、1位との差は{gap:,}円です。'
                    f'やや攻めの姿勢で、上昇余地の大きい銘柄を選んでください。'
                )

        return [
            {
                'role': 'system',
                'content': PromptLoader.character_system(analyst.name, analyst.name_jp),
            },
            {
                'role': 'user',
                'content': (
                    f'以下のCSVはPythonが事前にスコアリング・絞り込みを済ませた候補銘柄です（{yesterday_date}基準）：\n'
                    f'{csv_text}\n\n'
                    f'{tomorrow_date}の終値が最も上がりそうな銘柄を、あなたのキャラクターとして選んでください。'
                    f'{strategy_hint}\n\n'
                    f'以下の条件で銘柄を選んでください：\n{range_desc}\n'
                    f'合計{len(active_ranges)}銘柄を選んでください。\n'
                    f'CSVに記載されていない銘柄は選ばないでください。\n'
                    f'ハルシネーションしないでください。\n\n'
                    f'予想結果はcsv形式で出力してください。\n'
                    f'csv形式の例：\n'
                    f'証券コード,銘柄名,予想始値,予想高値,予想安値,予想終値,予想出来高,予測理由\n'
                    f'ヘッダーは必ず上記の通りにしてください。\n'
                    f'結果はcsvの中身以外は一切出力しないでください。'
                ),
            },
        ]

    # ------------------------------------------------------------------
    # 予測保存
    # ------------------------------------------------------------------

    def _save_predictions(self, result: str, analyst, tomorrow_date: str,
                          yesterday_date: str, active_ranges: List[int]) -> None:
        lines = [l.strip() for l in result.splitlines() if ',' in l.strip()]
        if not lines:
            print(f'警告: {analyst.name_jp} の応答に有効なCSVデータがありません')
            return

        rows = list(csv.reader(io.StringIO('\n'.join(lines))))
        header = None
        for i, row in enumerate(rows):
            if len(row) >= 8 and row[0] == '証券コード':
                header = row
                rows = rows[i + 1:]
                break
        if not header:
            print(f'警告: {analyst.name_jp} の応答に正しいヘッダーがありません')
            return

        saved_ranges = set()
        for row in rows:
            if len(row) < 8:
                continue
            try:
                stock_code      = row[0].strip()
                predicted_open  = float(row[2])
                predicted_high  = float(row[3])
                predicted_low   = float(row[4])
                predicted_close = float(row[5])
                predicted_volume = float(row[6])
                reason          = row[7].strip()

                actual_records = self.actual_manager.get_stock_actual(
                    stock_code=stock_code,
                    date_from=yesterday_date,
                    date_to=yesterday_date,
                )
                base_price = (
                    actual_records[0].get('actual_close_price') or predicted_open
                    if actual_records else predicted_open
                )
                price_range = self._classify_range(base_price)
                if price_range not in active_ranges:
                    continue
                if price_range in saved_ranges:
                    continue

                stock_name = self.m_stock_manager.get_stock_name(stock_code) or '不明'
                self.predict_manager.insert_prediction(
                    predicted_date=tomorrow_date,
                    analyst_name=analyst.name,
                    stock_code=stock_code,
                    stock_name=stock_name,
                    range=price_range,
                    predicted_open_price=predicted_open,
                    predicted_high_price=predicted_high,
                    predicted_low_price=predicted_low,
                    predicted_close_price=predicted_close,
                    predicted_volume=predicted_volume,
                    prediction_reason=reason,
                )
                saved_ranges.add(price_range)

            except (ValueError, IndexError):
                continue

    # ------------------------------------------------------------------
    # 律（ritu）選定
    # ------------------------------------------------------------------

    def _predict_ritu_from_candidates(self, candidates: List[Dict],
                                      tomorrow_date: str,
                                      active_ranges: List[int]) -> None:
        """
        フィルタ済みスコアリング済み候補から律の選択銘柄をランダム選定する。
        完全無差別ではなく、最低限の流動性チェック通過済み候補から選ぶ。
        """
        ritu = IchinoseRitu()
        try:
            ritu_reason = self._get_ritu_reasons(ritu, len(active_ranges))

            buckets: Dict[int, List[Dict]] = {r: [] for r in active_ranges}
            for c in candidates:
                if c['price_range'] in buckets:
                    buckets[c['price_range']].append(c)

            for i, price_range in enumerate(active_ranges):
                bucket = buckets.get(price_range, [])
                if not bucket:
                    continue
                stock = random.choice(bucket)
                cp = stock['close']
                po = math.floor(cp * random.uniform(1.001, 1.5))
                pc = math.floor(cp * random.uniform(1.001, 1.5))
                ph = math.floor(max(po, pc) * random.uniform(1.001, 1.3))
                pl = math.floor(min(po, pc) * random.uniform(0.7, 0.999))
                pv = math.floor(stock['volume'] * random.uniform(0.8, 1.5))

                self.predict_manager.insert_prediction(
                    predicted_date=tomorrow_date,
                    analyst_name=ritu.name,
                    stock_code=stock['stock_code'],
                    stock_name=stock['stock_name'],
                    range=price_range,
                    predicted_open_price=po,
                    predicted_high_price=ph,
                    predicted_low_price=pl,
                    predicted_close_price=pc,
                    predicted_volume=pv,
                    prediction_reason=ritu_reason[i] if i < len(ritu_reason) else '勘！',
                )
        except Exception as e:
            print(f'エラー: 一ノ瀬律の処理中にエラー: {e}')

    def _predict_ritu_legacy(self, stock_data: List[Dict], tomorrow_date: str,
                             active_ranges: List[int]) -> None:
        """後方互換: scored_candidates がない場合の従来処理。"""
        ritu = IchinoseRitu()
        try:
            ritu_reason = self._get_ritu_reasons(ritu, len(active_ranges))
            buckets = {
                100:   [s for s in stock_data if s['actual_open_price'] <= 100],
                1000:  [s for s in stock_data if 100 < s['actual_open_price'] <= 1000],
                10000: [s for s in stock_data if 1000 < s['actual_open_price'] <= 10000],
            }
            for i, price_range in enumerate(active_ranges):
                bucket = buckets.get(price_range, [])
                if not bucket:
                    continue
                stock = random.choice(bucket)
                cp = stock['actual_open_price']
                po = math.floor(cp * random.uniform(1.001, 1.5))
                pc = math.floor(cp * random.uniform(1.001, 1.5))
                ph = math.floor(max(po, pc) * random.uniform(1.001, 1.3))
                pl = math.floor(min(po, pc) * random.uniform(0.7, 0.999))
                pv = math.floor(stock['actual_volume'] * random.uniform(0.8, 1.5))
                self.predict_manager.insert_prediction(
                    predicted_date=tomorrow_date,
                    analyst_name=ritu.name,
                    stock_code=stock['stock_code'],
                    stock_name=stock['stock_name'],
                    range=price_range,
                    predicted_open_price=po,
                    predicted_high_price=ph,
                    predicted_low_price=pl,
                    predicted_close_price=pc,
                    predicted_volume=pv,
                    prediction_reason=ritu_reason[i] if i < len(ritu_reason) else '勘！',
                )
        except Exception as e:
            print(f'エラー: 一ノ瀬律の処理中にエラー: {e}')

    def _get_ritu_reasons(self, ritu: IchinoseRitu, count: int) -> List[str]:
        default = [
            'お腹が減ってたから', '眠かったから', '疲れてたから',
            '暇だったから', '気分が良かったから', '天気が良かったから',
            '運が良さそうだったから', '勘が冴えてたから', '直感！',
        ]
        try:
            messages = [
                {'role': 'system',
                 'content': PromptLoader.character_system(ritu.name, ritu.name_jp)},
                {'role': 'user',
                 'content': (
                     f'「勘で選んだ！今日はお腹減ってたから！」のような、判断材料にならない理由を{count}個言って。'
                     f'セリフ以外いらない。毎回変えて。JSON配列形式で返して。例: ["理由1","理由2"]'
                 )},
            ]
            raw = self.guard.execute(
                ritu.stock_run, messages,
                call_type='ritu_reason', model='openai',
            )
            import json, re
            m = re.search(r'\[.*?\]', raw, re.DOTALL)
            if m:
                reasons = json.loads(m.group())
                if isinstance(reasons, list) and reasons:
                    return [str(r).strip('"') for r in reasons[:count]]
        except Exception:
            pass
        return default[:count]

    @staticmethod
    def _classify_range(price: float) -> int:
        if price <= 100:
            return 100
        elif price <= 1000:
            return 1000
        elif price <= 10000:
            return 10000
        return 100_000
