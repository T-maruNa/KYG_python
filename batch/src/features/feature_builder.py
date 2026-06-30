"""
株価データから特徴量を計算する。

FeatureBuilder は構造化データ（List[Dict]）を返す。
内部の特徴量は Python 側スコアリング・フィルタリング・AI 入力整形に使うが、
ブログ本文には詳細数値を大量表示しない。

FeatureCalculator（既存）は AI 向け CSV 生成専用として残す。
FeatureBuilder はその上位互換として、より多くの特徴量を構造化 dict で返す。
"""
import math
from typing import List, Dict, Optional
from src.database.t_stock_actual_full_manager import TStockActualFullManager
from src.database.m_stock_manager import MStockManager

PRICE_RANGES = {
    100:   lambda c: c <= 100,
    1000:  lambda c: 100 < c <= 1000,
    10000: lambda c: 1000 < c <= 10000,
}

PRICE_RANGE_LABELS = {
    100:   '小型株',
    1000:  '中型株',
    10000: '大型株',
}


class FeatureBuilder:
    """
    株価履歴データから特徴量を計算し、構造化 dict のリストを返す。
    """

    MIN_HISTORY = 21  # 20日特徴量の計算に必要な最低履歴日数

    def __init__(self):
        self._full_mgr = TStockActualFullManager()
        self._stock_mgr = MStockManager()

    def build(self, target_date: str, active_ranges: List[int] = None) -> List[Dict]:
        """
        target_date を基準に全銘柄の特徴量を計算して返す。
        active_ranges: 含める価格帯。None なら全価格帯。
        """
        active_ranges = active_ranges or list(PRICE_RANGES.keys())
        stocks = self._stock_mgr.get_stock_all()
        result = []
        for stock in stocks:
            code = stock['stock_code']
            history = self._full_mgr.get_stock_history(code, target_date, limit=30)
            if len(history) < self.MIN_HISTORY:
                continue
            if history[-1]['date'] != target_date:
                continue
            name = self._stock_mgr.get_stock_name(code) or '不明'
            f = self._calc(code, name, history, active_ranges)
            if f:
                result.append(f)
        return result

    def _calc(self, code: str, name: str,
              history: List[Dict], active_ranges: List[int]) -> Optional[Dict]:
        closes  = [h['close']  for h in history]
        opens   = [h['open']   for h in history]
        highs   = [h['high']   for h in history]
        lows    = [h['low']    for h in history]
        volumes = [h['volume'] for h in history]

        c = closes[-1]
        if not c or c <= 0:
            return None

        # 価格帯判定
        price_range = None
        for r, cond in PRICE_RANGES.items():
            if r in active_ranges and cond(c):
                price_range = r
                break
        if price_range is None:
            return None

        prev_c = closes[-2] if len(closes) >= 2 and closes[-2] else c
        cur_o  = opens[-1]  if opens[-1]  else c

        # ---- 騰落系 ----
        day_change      = round(c - prev_c, 2)
        day_change_rate = round((c - prev_c) / prev_c * 100, 2) if prev_c else 0.0

        def rise_rate(n: int) -> float:
            if len(closes) < n + 1:
                return 0.0
            base = closes[-(n + 1)]
            return round((c - base) / base * 100, 2) if base else 0.0

        rise_5  = rise_rate(5)
        rise_20 = rise_rate(20)

        # ---- 出来高系 ----
        vol_prev      = volumes[-2] if len(volumes) >= 2 and volumes[-2] else 0
        vol_change_rate = round((volumes[-1] - vol_prev) / vol_prev * 100, 2) if vol_prev else 0.0
        vol_ma5       = round(sum(volumes[-5:]) / 5, 0) if len(volumes) >= 5 else 0
        vol_ma5_ratio = round(volumes[-1] / vol_ma5, 2) if vol_ma5 else 0.0

        # ---- 移動平均 ----
        def ma(n: int) -> float:
            if len(closes) < n:
                return 0.0
            return round(sum(closes[-n:]) / n, 2)

        ma5  = ma(5)
        ma20 = ma(20)
        ma5_dev  = round((c - ma5)  / ma5  * 100, 2) if ma5  else 0.0
        ma20_dev = round((c - ma20) / ma20 * 100, 2) if ma20 else 0.0

        # ---- ボラティリティ（直近5日終値の標準偏差/平均） ----
        c5   = closes[-5:] if len(closes) >= 5 else closes
        avg5 = sum(c5) / len(c5) if c5 else c
        variance   = sum((x - avg5) ** 2 for x in c5) / len(c5) if c5 else 0
        volatility = round(math.sqrt(variance) / avg5 * 100, 2) if avg5 else 0.0

        # ---- 当日レンジ率・ギャップ率 ----
        h = highs[-1] or c
        l = lows[-1]  or c
        range_rate = round((h - l) / c * 100, 2) if c else 0.0
        gap_rate   = round((cur_o - prev_c) / prev_c * 100, 2) if prev_c else 0.0

        # ---- 陽線 / 陰線 ----
        is_bullish = 1 if c >= cur_o else 0

        # ---- 連続上昇・連続下落日数 ----
        def _consecutive() -> tuple:
            up = down = 0
            cs = closes[-10:] if len(closes) >= 10 else closes
            for i in range(len(cs) - 1, 0, -1):
                if cs[i] > cs[i - 1]:
                    if down == 0:
                        up += 1
                    else:
                        break
                elif cs[i] < cs[i - 1]:
                    if up == 0:
                        down += 1
                    else:
                        break
                else:
                    break
            return up, down

        consec_up, consec_down = _consecutive()

        # ---- 直近高値更新 / 安値割れ ----
        w5_h  = max(highs[-5:])  if len(highs) >= 5  else h
        w20_h = max(highs[-20:]) if len(highs) >= 20 else h
        w5_l  = min(lows[-5:])   if len(lows) >= 5   else l
        w20_l = min(lows[-20:])  if len(lows) >= 20  else l

        return {
            'stock_code':   code,
            'stock_name':   name,
            'price_range':  price_range,
            'close':        c,
            'volume':       volumes[-1],
            # 騰落
            'day_change':       day_change,
            'day_change_rate':  day_change_rate,
            'rise_5':           rise_5,
            'rise_20':          rise_20,
            # 出来高
            'vol_change_rate':  vol_change_rate,
            'vol_ma5_ratio':    vol_ma5_ratio,
            # 移動平均
            'ma5':      ma5,
            'ma20':     ma20,
            'ma5_dev':  ma5_dev,
            'ma20_dev': ma20_dev,
            # リスク・勢い
            'volatility':  volatility,
            'range_rate':  range_rate,
            'gap_rate':    gap_rate,
            'is_bullish':  is_bullish,
            'consec_up':   consec_up,
            'consec_down': consec_down,
            # 高値・安値更新フラグ
            'new_high_5':  1 if h >= w5_h  else 0,
            'new_high_20': 1 if h >= w20_h else 0,
            'new_low_5':   1 if l <= w5_l  else 0,
            'new_low_20':  1 if l <= w20_l else 0,
        }
