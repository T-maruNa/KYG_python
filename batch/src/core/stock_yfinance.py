import yfinance as yf
import math
import time
from datetime import date, timedelta
from src.database.m_stock_manager import MStockManager
from src.database.t_stock_actual_manager import TStockActualManager


class StockYFinance:
    def __init__(self):
        self.m_stock_manager = MStockManager()
        self.actual_manager = TStockActualManager()
        self.industry_code_33 = '5250'  # 情報・通信業

    def set_stock_prices(self, target_date: str) -> None:
        """
        指定日の株価を情報通信業の銘柄分だけ取得して t_stock_actual に保存する
        """
        today = date.today()
        end_date = (today + timedelta(days=1)).strftime("%Y-%m-%d")

        try:
            stocks = self.m_stock_manager.get_stock_by_industry_code_33(self.industry_code_33)
            if not stocks:
                print("エラー: 銘柄データが見つかりません。")
                return

            print(f"銘柄数: {len(stocks)}")

            for stock in stocks:
                stock_code = stock['stock_code']
                try:
                    code = f"{str(stock_code).zfill(4)}.T"
                    ticker = yf.Ticker(code)
                    hist = ticker.history(start=target_date, end=end_date)
                    time.sleep(1)

                    if hist.empty:
                        print(f"スキップ: {stock_code} データなし")
                        continue

                    stock_name = self.m_stock_manager.get_stock_name(stock_code) or "不明"
                    stock_data = {
                        'date': target_date,
                        'stock_code': stock_code,
                        'stock_name': stock_name,
                        'actual_open_price': math.trunc(hist['Open'].iloc[-1]),
                        'actual_high_price': math.trunc(hist['High'].iloc[-1]),
                        'actual_low_price': math.trunc(hist['Low'].iloc[-1]),
                        'actual_close_price': math.trunc(hist['Close'].iloc[-1]),
                        'actual_volume': math.trunc(hist['Volume'].iloc[-1]),
                    }

                    if self.actual_manager.insert_stock_actual(stock_data, 'SYSTEM'):
                        print(f"保存: {stock_code}:{stock_name}")
                    else:
                        print(f"保存失敗: {stock_code}:{stock_name}")

                except Exception as e:
                    print(f"エラー: {stock_code} 取得失敗: {e}")
                    continue

        except Exception as e:
            import traceback
            print(f"エラー: 株価取得中にエラーが発生しました: {e}")
            print(traceback.format_exc())
