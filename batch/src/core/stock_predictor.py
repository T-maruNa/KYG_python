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


RANGE_LIMITS = {100: 300000, 1000: 300000, 10000: 400000}
RANGE_LABEL = {100: '低位株(100円以下)', 1000: '中位株(101〜1000円)', 10000: '大型株(1001〜10000円)'}


class StockPredictor:
    def __init__(self):
        self.analysts = get_analysts()
        self.predict_manager = TStockPredictManager()
        self.m_stock_manager = MStockManager()
        self.actual_manager = TStockActualManager()
        self.guard = AIBudgetGuard()
        self.feature_calc = FeatureCalculator()

    def _build_messages(self, analyst, csv_text: str, yesterday_date: str,
                        tomorrow_date: str, active_ranges: List[int]) -> List[Dict]:
        range_desc = '\n'.join(
            f'・{RANGE_LABEL[r]}から1銘柄' for r in active_ranges
        )
        return [
            {
                'role': 'system',
                'content': (
                    f'あなたは{analyst.name_jp}です。{analyst.title}として、{analyst.description}'
                ),
            },
            {
                'role': 'user',
                'content': (
                    f'以下のCSVは{yesterday_date}の株価と特徴量です：\n{csv_text}\n\n'
                    f'{tomorrow_date}の終値が最も上がりそうな銘柄を予測してください。\n'
                    f'あなたの専門分野である{analyst.style}の観点から、特に{analyst.focus}に注目して分析してください。\n\n'
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

    def predict(self, yesterday_date: str, tomorrow_date: str,
                active_ranges_by_analyst: Dict[str, List[int]] = None) -> None:
        """
        株価予測を実行してDBに保存する。

        active_ranges_by_analyst: {analyst_name: [100, 1000, 10000]} のように
        キャラクター別の投資可能価格帯を渡す。Noneなら全員3価格帯。
        """
        stock_data = self.actual_manager.get_stock_actual(date_from=yesterday_date)
        if not stock_data:
            print(f"警告: {yesterday_date} の株価データが見つかりません")
            return

        # 特徴量CSV（過去20営業日を使った前日比・移動平均・ボラティリティ等）
        # アナリストごとに active_ranges が異なるため共通の全帯CSVを生成し、
        # 各アナリストのプロンプトで有効価格帯のみ選択させる
        all_active = sorted({
            r
            for ranges in (active_ranges_by_analyst or {}).values()
            for r in ranges
        }) or [100, 1000, 10000]
        csv_text = self.feature_calc.build_feature_csv(
            yesterday_date, active_ranges=all_active
        )
        if not csv_text:
            # 特徴量データが不足している場合は基本OHLCにフォールバック
            print(f"警告: {yesterday_date} の特徴量データが不足しています。基本OHLCで代替します。")
            csv_lines = ['証券コード,銘柄名,終値,始値,高値,安値,出来高']
            for s in stock_data:
                csv_lines.append(
                    f"{s['stock_code']},{s['stock_name']},{s['actual_close_price']},"
                    f"{s['actual_open_price']},{s['actual_high_price']},"
                    f"{s['actual_low_price']},{s['actual_volume']}"
                )
            csv_text = '\n'.join(csv_lines)

        for analyst in self.analysts:
            active_ranges = (
                active_ranges_by_analyst.get(analyst.name, [100, 1000, 10000])
                if active_ranges_by_analyst
                else [100, 1000, 10000]
            )
            if not active_ranges:
                print(f"{analyst.name_jp}: 投資可能な価格帯がありません")
                continue

            try:
                messages = self._build_messages(
                    analyst, csv_text, yesterday_date, tomorrow_date, active_ranges
                )
                result = self.guard.execute(
                    analyst.stock_run, messages,
                    call_type='prediction', model=analyst.model,
                )
                if not result:
                    print(f"警告: {analyst.name_jp} からの応答がありません（予算上限またはエラー）")
                    continue

                self._save_predictions(result, analyst, tomorrow_date, active_ranges)

            except Exception as e:
                print(f"エラー: {analyst.name_jp} の処理中にエラー: {e}")
                continue

        # 一ノ瀬律（ランダム枠）
        ritu_ranges = (
            active_ranges_by_analyst.get('ritu', [100, 1000, 10000])
            if active_ranges_by_analyst
            else [100, 1000, 10000]
        )
        self._predict_ritu(stock_data, tomorrow_date, ritu_ranges)

    def _save_predictions(self, result: str, analyst, tomorrow_date: str,
                          active_ranges: List[int]) -> None:
        lines = [l.strip() for l in result.splitlines() if ',' in l.strip()]
        if not lines:
            print(f"警告: {analyst.name_jp} の応答に有効なCSVデータがありません")
            return

        rows = list(csv.reader(io.StringIO('\n'.join(lines))))
        header = None
        for i, row in enumerate(rows):
            if len(row) >= 8 and row[0] == '証券コード':
                header = row
                rows = rows[i + 1:]
                break

        if not header:
            print(f"警告: {analyst.name_jp} の応答に正しいヘッダーがありません")
            return

        saved_ranges = set()
        for row in rows:
            if len(row) < 8:
                continue
            try:
                stock_code = row[0].strip()
                predicted_open = float(row[2])
                predicted_high = float(row[3])
                predicted_low = float(row[4])
                predicted_close = float(row[5])
                predicted_volume = float(row[6])
                reason = row[7].strip()

                price_range = self._classify_range(predicted_open)
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

    def _predict_ritu(self, stock_data: List[Dict], tomorrow_date: str,
                      active_ranges: List[int]) -> None:
        ritu = IchinoseRitu()
        try:
            ritu_reason = self._get_ritu_reasons(ritu, len(active_ranges))

            buckets = {
                100: [s for s in stock_data if s['actual_open_price'] <= 100],
                1000: [s for s in stock_data if 100 < s['actual_open_price'] <= 1000],
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
            print(f"エラー: 一ノ瀬律の処理中にエラー: {e}")

    def _get_ritu_reasons(self, ritu: IchinoseRitu, count: int) -> List[str]:
        default = [
            'お腹が減ってたから', '眠かったから', '疲れてたから',
            '暇だったから', '気分が良かったから', '天気が良かったから',
            '運が良さそうだったから', '勘が冴えてたから', '直感！',
        ]
        try:
            messages = [
                {'role': 'system',
                 'content': f'あなたは{ritu.name_jp}です。{ritu.title}。{ritu.description}'},
                {'role': 'user',
                 'content': (
                     f'「勘で選んだ！今日はお腹減ってたから！」のような、判断材料にならない理由を{count}個言って。'
                     f'セリフ以外いらない。毎回変えて。JSON配列形式で返して。例: ["理由1","理由2"]'
                 )},
            ]
            raw = self.guard.execute(
                ritu.stock_run, messages,
                call_type='ritu_reason', model='gemini',
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
        return 100000
