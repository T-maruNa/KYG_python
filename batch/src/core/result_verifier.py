from typing import List, Dict
from src.database.t_investment_history_manager import TInvestmentHistoryManager
from src.database.t_character_asset_manager import TCharacterAssetManager
from src.database.t_daily_result_manager import TDailyResultManager
from src.database.t_stock_actual_manager import TStockActualManager
from src.characters import get_analysts
from src.characters.ichinose import IchinoseRitu

ALL_ANALYSTS = [a.name for a in get_analysts()] + [IchinoseRitu().name]


class ResultVerifier:
    def __init__(self):
        self.history_manager = TInvestmentHistoryManager()
        self.asset_manager = TCharacterAssetManager()
        self.daily_manager = TDailyResultManager()
        self.actual_manager = TStockActualManager()

    def verify(self, trade_date: str, year_month: str) -> bool:
        """
        trade_date の実際の終値を参照して損益を確定し、資産を更新する。
        t_stock_actual に trade_date のデータが存在することが前提。
        """
        if self.daily_manager.exists(trade_date):
            print(f"スキップ: {trade_date} の結果は確定済み")
            return True

        # 実際の株価を取得（{stock_code: close_price} マップを構築）
        actual_prices = self._build_price_map(trade_date)
        if not actual_prices:
            print(f"警告: {trade_date} の実株価データがありません")
            return False

        pending = self.history_manager.get_pending(trade_date)
        if not pending:
            print(f"警告: {trade_date} の未確定エントリーがありません")
            return False

        # アナリストごとに損益を集計
        analyst_results: Dict[str, Dict] = {}
        for entry in pending:
            analyst_name = entry['analyst_name']
            stock_code = entry['stock_code']
            price_range = entry['price_range']

            sell_price = actual_prices.get(stock_code)
            if not sell_price:
                print(f"警告: {stock_code} の実株価が見つかりません")
                continue

            result = self.history_manager.fill_result(
                trade_date, analyst_name, price_range, sell_price
            )
            if not result:
                continue

            if analyst_name not in analyst_results:
                analyst_results[analyst_name] = {'profit_loss': 0, 'win': 0, 'lose': 0}

            analyst_results[analyst_name]['profit_loss'] += result['profit_loss']
            if result['is_win']:
                analyst_results[analyst_name]['win'] += 1
            else:
                analyst_results[analyst_name]['lose'] += 1

        # 資産更新・日次結果保存
        for analyst_name, res in analyst_results.items():
            self.asset_manager.update_balance(year_month, analyst_name, res['profit_loss'])
            new_balance = self.asset_manager.get_balance(year_month, analyst_name) or 0
            self.daily_manager.upsert(
                result_date=trade_date,
                analyst_name=analyst_name,
                total_profit_loss=res['profit_loss'],
                current_balance=new_balance,
                win_count=res['win'],
                lose_count=res['lose'],
            )
            sign = '+' if res['profit_loss'] >= 0 else ''
            print(
                f"{analyst_name}: 損益 {sign}{res['profit_loss']:,}円  "
                f"残高 {new_balance:,}円  "
                f"({res['win']}勝{res['lose']}敗)"
            )

        return True

    def _build_price_map(self, target_date: str) -> Dict[str, int]:
        records = self.actual_manager.get_stock_actual(date_from=target_date, date_to=target_date)
        return {r['stock_code']: r['actual_close_price'] for r in records}
