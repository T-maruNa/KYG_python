import yfinance as yf
import math
import time
from datetime import date, datetime, timedelta
from src.database.m_stock_manager import MStockManager
from src.database.t_stock_actual_full_manager import TStockActualFullManager


class StockYFinanceFull:
    def __init__(self):
        self.m_stock_manager = MStockManager()
        self.actual_full_manager = TStockActualFullManager()

    def set_stock_prices(self, target_date: str) -> None:
        """指定日の株価を全銘柄分取得して t_stock_actual_full に保存する"""
        today = date.today()
        end_date = (today + timedelta(days=1)).strftime("%Y-%m-%d")
        self._fetch_and_store(target_date, end_date)

    def backfill(self, days: int = 30) -> None:
        """過去 days 日分の株価データを全銘柄分取得して保存する"""
        today = date.today()
        start_date = (today - timedelta(days=days)).strftime("%Y-%m-%d")
        end_date = (today + timedelta(days=1)).strftime("%Y-%m-%d")
        self._fetch_and_store(start_date, end_date)

    def _fetch_and_store(self, start_date: str, end_date: str) -> None:
        stocks = self.m_stock_manager.get_stock_all()
        if not stocks:
            print("エラー: 銘柄データが見つかりません。")
            return

        print(f"銘柄数: {len(stocks)}  取得期間: {start_date} ～ {end_date}")

        for stock in stocks:
            stock_code = stock['stock_code']
            try:
                code = f"{str(stock_code).zfill(4)}.T"
                ticker = yf.Ticker(code)
                hist = ticker.history(start=start_date, end=end_date)
                time.sleep(0.5)

                if hist.empty:
                    print(f"スキップ: {stock_code} データなし")
                    continue

                stock_name = self.m_stock_manager.get_stock_name(stock_code) or "不明"

                for idx_date, row in hist.iterrows():
                    row_date = idx_date.strftime("%Y-%m-%d")
                    if self.actual_full_manager.exists_stock_actual_full(stock_code, row_date):
                        continue
                    stock_data = {
                        'date': row_date,
                        'stock_code': stock_code,
                        'stock_name': stock_name,
                        'actual_open_price': math.trunc(row['Open']),
                        'actual_high_price': math.trunc(row['High']),
                        'actual_low_price': math.trunc(row['Low']),
                        'actual_close_price': math.trunc(row['Close']),
                        'actual_volume': math.trunc(row['Volume']),
                    }
                    if self.actual_full_manager.insert_stock_actual(stock_data, 'SYSTEM'):
                        print(f"保存: {stock_code} {row_date}")
                    else:
                        print(f"保存失敗: {stock_code} {row_date}")

            except Exception as e:
                print(f"エラー: {stock_code} 取得失敗: {e}")
                continue


if __name__ == "__main__":
    StockYFinanceFull().backfill(days=30)
