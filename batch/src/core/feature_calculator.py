import math
from typing import List, Dict, Optional
from src.database.t_stock_actual_full_manager import TStockActualFullManager
from src.database.m_stock_manager import MStockManager


class FeatureCalculator:
    def __init__(self):
        self.actual_full_manager = TStockActualFullManager()
        self.m_stock_manager = MStockManager()

    def build_feature_csv(self, target_date: str) -> str:
        """
        target_date の株価を基準に特徴量CSVを生成する。
        t_stock_actual_full から直近25日分の履歴を使って計算する。
        """
        stocks = self.m_stock_manager.get_stock_all()
        if not stocks:
            return ""

        header = (
            "証券コード,銘柄名,終値,前日比,前日比率,"
            "5日騰落率,20日騰落率,出来高変化率,"
            "5日移動平均,20日移動平均,ボラティリティ,"
            "直近高値更新,直近安値更新"
        )
        rows = [header]

        for stock in stocks:
            stock_code = stock['stock_code']
            history = self.actual_full_manager.get_stock_history(stock_code, target_date, limit=25)
            if len(history) < 2:
                continue

            latest = history[-1]
            if latest['date'] != target_date:
                continue

            stock_name = self.m_stock_manager.get_stock_name(stock_code) or "不明"
            row = self._calc_features(stock_code, stock_name, history)
            if row:
                rows.append(row)

        return "\n".join(rows)

    def _calc_features(self, stock_code: str, stock_name: str, history: List[Dict]) -> Optional[str]:
        closes = [h['close'] for h in history]
        volumes = [h['volume'] for h in history]
        highs = [h['high'] for h in history]
        lows = [h['low'] for h in history]

        latest_close = closes[-1]
        prev_close = closes[-2]

        day_change = latest_close - prev_close
        day_change_rate = round(day_change / prev_close * 100, 2) if prev_close else 0

        def rise_rate(n: int) -> float:
            if len(closes) < n + 1:
                return 0.0
            base = closes[-(n + 1)]
            return round((latest_close - base) / base * 100, 2) if base else 0.0

        rise_5 = rise_rate(5)
        rise_20 = rise_rate(20)

        vol_change = 0.0
        if len(volumes) >= 2 and volumes[-2]:
            vol_change = round((volumes[-1] - volumes[-2]) / volumes[-2] * 100, 2)

        def ma(n: int) -> float:
            if len(closes) < n:
                return 0.0
            return round(sum(closes[-n:]) / n, 1)

        ma5 = ma(5)
        ma20 = ma(20)

        # 直近20日内の最高値・最安値更新
        window_highs = highs[-20:] if len(highs) >= 20 else highs
        window_lows = lows[-20:] if len(lows) >= 20 else lows
        is_new_high = 1 if highs[-1] >= max(window_highs) else 0
        is_new_low = 1 if lows[-1] <= min(window_lows) else 0

        # ボラティリティ（直近5日の終値標準偏差 / 平均）
        if len(closes) >= 5:
            c5 = closes[-5:]
            avg5 = sum(c5) / 5
            variance = sum((c - avg5) ** 2 for c in c5) / 5
            vol = round(math.sqrt(variance) / avg5 * 100, 2) if avg5 else 0.0
        else:
            vol = 0.0

        return (
            f"{stock_code},{stock_name},{latest_close},{day_change},{day_change_rate},"
            f"{rise_5},{rise_20},{vol_change},"
            f"{ma5},{ma20},{vol},"
            f"{is_new_high},{is_new_low}"
        )
