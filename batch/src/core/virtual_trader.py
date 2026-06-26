import math
from typing import List, Dict, Optional
from src.database.t_character_asset_manager import TCharacterAssetManager
from src.database.t_investment_history_manager import TInvestmentHistoryManager
from src.database.t_stock_predict_manager import TStockPredictManager
from src.database.t_stock_actual_manager import TStockActualManager
from src.characters import get_analysts
from src.characters.ichinose import IchinoseRitu


# 価格帯ごとの投資上限額
RANGE_LIMIT = {100: 300000, 1000: 300000, 10000: 400000}

ALL_ANALYSTS = [a.name for a in get_analysts()] + [IchinoseRitu().name]


class VirtualTrader:
    def __init__(self):
        self.asset_manager = TCharacterAssetManager()
        self.history_manager = TInvestmentHistoryManager()
        self.predict_manager = TStockPredictManager()
        self.actual_manager = TStockActualManager()

    def initialize_month(self, year_month: str) -> None:
        """月初に全キャラクターの資産を100万円で初期化する"""
        if not self.asset_manager.exists(year_month):
            self.asset_manager.initialize_month(year_month, ALL_ANALYSTS)
            print(f"{year_month} の資産を初期化しました（各100万円）")

    def get_active_ranges(self, analyst_name: str, year_month: str) -> List[int]:
        """
        資金残高に応じて投資可能な価格帯リストを返す。
        残高 >= 60万: [100, 1000, 10000]
        残高 >= 30万: [100, 1000]
        残高 < 30万:  [100]
        """
        balance = self.asset_manager.get_balance(year_month, analyst_name)
        if balance is None:
            return [100, 1000, 10000]
        if balance >= 600000:
            return [100, 1000, 10000]
        if balance >= 300000:
            return [100, 1000]
        return [100]

    def get_active_ranges_all(self, year_month: str) -> Dict[str, List[int]]:
        return {name: self.get_active_ranges(name, year_month) for name in ALL_ANALYSTS}

    def execute_entries(self, trade_date: str, buy_date: str, year_month: str) -> None:
        """
        trade_date の予測データからエントリーを作成して t_investment_history に保存する。

        trade_date: 今日の売買対象日（記事に載せる「今日のエントリー」）
        buy_date:   買値に使う終値の日付（前営業日 = prev_day）
        """
        for analyst_name in ALL_ANALYSTS:
            if self.history_manager.exists_entry(trade_date, analyst_name):
                print(f"スキップ: {analyst_name} {trade_date} は登録済み")
                continue

            balance = self.asset_manager.get_balance(year_month, analyst_name) or 1000000
            active_ranges = self.get_active_ranges(analyst_name, year_month)
            remaining = balance  # 枠ごとに減算して残高超過を防ぐ

            predictions = self.predict_manager.get_prediction_by_date(trade_date, analyst_name)

            for pred in predictions:
                price_range = self._classify_range(pred.get('predicted_close_price', 0))
                if price_range not in active_ranges:
                    continue
                if remaining <= 0:
                    break

                stock_code = pred['code']
                reason = pred.get('prediction_reason', '')

                # 買値は buy_date の終値（日付を明示して未来価格の混入を防ぐ）
                buy_price = self._get_buy_price(stock_code, buy_date)
                if not buy_price:
                    print(f"警告: {stock_code} {buy_date} の終値が取得できません")
                    continue

                # 投資可能額 = 価格帯上限 と 残余資金 の小さい方
                invest_limit = min(RANGE_LIMIT.get(price_range, 300000), remaining)
                shares = math.floor(invest_limit / buy_price)
                if shares <= 0:
                    continue

                buy_amount = buy_price * shares
                self.history_manager.insert_entry(
                    trade_date=trade_date,
                    analyst_name=analyst_name,
                    stock_code=stock_code,
                    stock_name=pred['name'],
                    price_range=price_range,
                    buy_price=buy_price,
                    shares=shares,
                    buy_amount=buy_amount,
                    prediction_reason=reason,
                )
                remaining -= buy_amount
                print(
                    f"エントリー: {analyst_name} {stock_code} {shares}株 "
                    f"@{buy_price}円 ({price_range}円帯) 残余資金:{remaining:,}円"
                )

    def _get_buy_price(self, stock_code: str, buy_date: str) -> Optional[int]:
        """t_stock_actual から buy_date 当日の終値を返す"""
        records = self.actual_manager.get_stock_actual(
            stock_code=stock_code,
            date_from=buy_date,
            date_to=buy_date,
        )
        if records:
            return records[0].get('actual_close_price')
        return None

    @staticmethod
    def _classify_range(price: float) -> int:
        if price <= 100:
            return 100
        elif price <= 1000:
            return 1000
        elif price <= 10000:
            return 10000
        return 100000
