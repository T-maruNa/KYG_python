"""
候補銘柄スコアリング。

共通スコア: 全キャラ向けの流動性・値動き品質スコア
rei スコア:   テクニカル分析重視（移動平均・高値更新・出来高変化）
mirai スコア: 出来高急増・話題性っぽい勢い・過度に荒くない動き重視

律（ritu）はスコアリング対象外。CandidateFilter 通過済み候補からランダム選定する。

内部スコアはブログ本文に直接出さない。
記事コメントは投資助言に見えない表現で別途生成する。
"""
import random
from typing import List, Dict
from config.config import config

# 特徴量ラベル生成で使う閾値
_HIGH_VOL_RATIO  = 1.5
_HIGH_VOL_CHG    = 20.0
_STRONG_RISE_5   = 5.0
_MA_ABOVE_THRESH = 2.0


class CandidateScorer:
    """
    フィルタ済み候補銘柄に common / rei / mirai スコアを付与し、
    価格帯ごとに上位 MAX_CANDIDATES_PER_RANGE 件へ絞る。
    """

    def score_and_rank(self, candidates: List[Dict]) -> List[Dict]:
        """
        各候補に common_score / rei_score / mirai_score / feature_label を付与して返す。
        """
        result = []
        for c in candidates:
            c = dict(c)
            c['common_score'] = self._common_score(c)
            c['rei_score']    = self._rei_score(c)
            c['mirai_score']  = self._mirai_score(c)
            c['feature_label'] = self._feature_label(c)
            result.append(c)
        return result

    def top_per_range(self, candidates: List[Dict],
                      score_key: str = 'common_score') -> Dict[int, List[Dict]]:
        """
        score_key で並べ替えて価格帯ごとに上位 MAX_CANDIDATES_PER_RANGE 件を返す。
        """
        limit = config.MAX_CANDIDATES_PER_RANGE
        buckets: Dict[int, List[Dict]] = {}
        for c in candidates:
            r = c['price_range']
            buckets.setdefault(r, []).append(c)
        result = {}
        for r, items in buckets.items():
            items.sort(key=lambda x: x.get(score_key, 0), reverse=True)
            # 順位を付与
            for i, item in enumerate(items, 1):
                item[f'rank_{score_key.replace("_score", "")}'] = i
            result[r] = items[:limit]
        return result

    def select_ritu(self, candidates: List[Dict],
                    active_ranges: List[int]) -> Dict[int, Dict]:
        """
        律用: フィルタ済み候補から価格帯ごとにランダム 1 件を選ぶ。
        完全無差別ランダムではなく、最低限の流動性チェックを通過した候補から選ぶ。
        """
        buckets: Dict[int, List[Dict]] = {r: [] for r in active_ranges}
        for c in candidates:
            if c['price_range'] in buckets:
                buckets[c['price_range']].append(c)
        selection = {}
        for r, items in buckets.items():
            if items:
                selection[r] = random.choice(items)
        return selection

    # ------------------------------------------------------------------
    # スコア計算（内部処理。ブログ本文には出さない）
    # ------------------------------------------------------------------

    def _common_score(self, f: Dict) -> float:
        """
        全キャラ共通の候補品質スコア。
        直近の値動きがある・出来高が極端に少なくない・短期の勢いがある
        ・過度な急騰急落ではないことを評価する。
        """
        score = 0.0

        # 出来高増加
        if f['vol_change_rate'] > 0:
            score += min(f['vol_change_rate'] * 0.05, 10)
        # 出来高が5日平均より多い
        if f['vol_ma5_ratio'] > 1.2:
            score += 5

        # 適度な前日比（動きがある）
        dr = abs(f['day_change_rate'])
        if 0.5 <= dr <= 10:
            score += dr * 0.5
        # 過度な急騰急落はマイナス
        if dr > 15:
            score -= (dr - 15) * 1.0

        # 直近5日が上昇傾向
        if f['rise_5'] > 0:
            score += min(f['rise_5'] * 0.3, 6)

        # 適度なボラティリティ（動きやすい銘柄）
        vol = f['volatility']
        if 1.0 <= vol <= 8.0:
            score += 3

        return round(score, 2)

    def _rei_score(self, f: Dict) -> float:
        """
        テクニカル分析寄りスコア（玲向け）。
        移動平均との関係・直近高値更新・出来高変化・ボラティリティを重視。
        """
        score = 0.0

        # MA5 / MA20 との関係
        if f['ma5_dev'] > 0:
            score += min(f['ma5_dev'] * 0.5, 8)
        if f['ma20_dev'] > 0:
            score += min(f['ma20_dev'] * 0.3, 5)

        # 直近高値更新
        if f['new_high_5']:
            score += 5
        if f['new_high_20']:
            score += 8

        # 出来高増加
        if f['vol_change_rate'] > 10:
            score += min(f['vol_change_rate'] * 0.1, 8)

        # 短期上昇トレンド
        if 1 <= f['rise_5'] <= 15:
            score += f['rise_5'] * 0.4
        if f['consec_up'] >= 2:
            score += f['consec_up'] * 2

        # 適度なボラティリティ
        vol = f['volatility']
        if 1.5 <= vol <= 6.0:
            score += 3

        # 安値割れはマイナス
        if f['new_low_5']:
            score -= 6
        if f['new_low_20']:
            score -= 10

        return round(score, 2)

    def _mirai_score(self, f: Dict) -> float:
        """
        話題性・雰囲気重視スコア（みらい向け）。
        出来高急増・最近値動きが出ている・過度に荒くないことを重視する。
        初期実装では外部ニュース/SNS情報なしで、
        出来高の急増と値動きの出現で「話題性っぽい動き」を推定する。
        """
        score = 0.0

        # 出来高が5日平均に対して増えている（注目度の代理指標）
        ratio = f['vol_ma5_ratio']
        if ratio > 1.5:
            score += min((ratio - 1) * 8, 15)
        elif ratio > 1.0:
            score += (ratio - 1) * 5

        # 適度な前日比（最近値動きが出ている）
        dr = f['day_change_rate']
        if 0.5 <= dr <= 8:
            score += dr * 0.6

        # 5日間で動き始めた感がある
        if 1 <= f['rise_5'] <= 20:
            score += min(f['rise_5'] * 0.4, 8)

        # 直近5日高値更新（話題になり始めのサイン）
        if f['new_high_5']:
            score += 5

        # 陽線（気分的に前向きな銘柄）
        if f['is_bullish']:
            score += 2

        # 荒すぎない（みらいは過度なギャンブルはしない）
        if f['volatility'] > 10:
            score -= (f['volatility'] - 10) * 0.5

        # ギャップアップ（注目されている感）
        if 0 < f['gap_rate'] <= 5:
            score += f['gap_rate'] * 0.5

        return round(score, 2)

    # ------------------------------------------------------------------
    # 特徴ラベル生成（AI プロンプト・DB 保存用）
    # ------------------------------------------------------------------

    def _feature_label(self, f: Dict) -> str:
        """
        候補の主な特徴を 2〜4 語のラベルで表す。
        AI プロンプトに渡すほか、DB の feature_summary にも保存する。
        記事本文に直接使わない（表現はAI側で変換）。
        """
        labels = []
        if f['vol_ma5_ratio'] >= _HIGH_VOL_RATIO:
            labels.append('出来高急増')
        elif f['vol_change_rate'] >= _HIGH_VOL_CHG:
            labels.append('出来高増加')

        if f['new_high_20']:
            labels.append('20日高値更新')
        elif f['new_high_5']:
            labels.append('5日高値更新')
        elif f['new_low_5']:
            labels.append('5日安値')

        if f['ma5_dev'] >= _MA_ABOVE_THRESH:
            labels.append('MA5上回り')
        elif f['ma5_dev'] < -_MA_ABOVE_THRESH:
            labels.append('MA5下回り')

        if f['rise_5'] >= _STRONG_RISE_5:
            labels.append(f"5日+{f['rise_5']:.1f}%")
        elif f['rise_5'] <= -_STRONG_RISE_5:
            labels.append(f"5日{f['rise_5']:.1f}%")

        if f['consec_up'] >= 3:
            labels.append(f"{f['consec_up']}連続上昇")
        elif f['consec_down'] >= 3:
            labels.append(f"{f['consec_down']}連続下落")

        return ' / '.join(labels) if labels else '標準的な動き'
