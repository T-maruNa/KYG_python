"""
候補銘柄フィルタリング。

企画として不向きな銘柄（出来高ゼロ・異常値・価格帯外など）を除外する。
フィルタ通過後の候補が CandidateScorer のスコアリング対象になる。
律（ritu）はフィルタ通過済み候補からランダム選定されるため、
このフィルタが「最低限まともな候補プール」を保証する役割を担う。
"""
from typing import List, Dict


# ---- フィルタ閾値 ----
MIN_VOLUME       = 10_000   # 最低出来高（これ未満は流動性なし）
MAX_DAY_CHANGE   = 28.0     # 前日比絶対値の上限（%）— ストップ高/安近辺を除外
MAX_RISE_5       = 45.0     # 5日騰落率の絶対値上限（%）
MIN_VOLATILITY   = 0.1      # ボラティリティ最低値（完全に動かない銘柄を除外）


class CandidateFilter:
    """
    FeatureBuilder が返す特徴量 dict を受け取り、不適切な銘柄を除外する。
    """

    def filter(self, features: List[Dict], active_ranges: List[int]) -> List[Dict]:
        """
        特徴量リストをフィルタリングして返す。
        active_ranges: 今日の対象価格帯リスト
        """
        result = []
        rejected = 0
        for f in features:
            reason = self._reject_reason(f, active_ranges)
            if reason:
                rejected += 1
            else:
                result.append(f)
        if rejected:
            print(f'[CandidateFilter] {rejected} 件を除外。残り {len(result)} 件。')
        return result

    def _reject_reason(self, f: Dict, active_ranges: List[int]) -> str:
        """除外する場合は理由文字列を、通過する場合は空文字を返す。"""
        if f['price_range'] not in active_ranges:
            return 'price_range_mismatch'
        if not f['close'] or f['close'] <= 0:
            return 'zero_close'
        if f['volume'] < MIN_VOLUME:
            return 'low_volume'
        if abs(f['day_change_rate']) > MAX_DAY_CHANGE:
            return f"abnormal_day_change:{f['day_change_rate']}"
        if abs(f['rise_5']) > MAX_RISE_5:
            return f"abnormal_rise_5:{f['rise_5']}"
        if f['volatility'] < MIN_VOLATILITY:
            return 'zero_volatility'
        return ''
