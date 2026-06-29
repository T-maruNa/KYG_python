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
        指定日の株価を情報通信業の銘柄分だけ取得して t_stock_actual に保存する。
        end は target_date の翌日に固定して target_date 分だけを取得する。
        """
        target_dt = date.fromisoformat(target_date)
        end_date = (target_dt + timedelta(days=1)).strftime("%Y-%m-%d")

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

                    # target_date の行だけを使う（複数日返った場合の誤保存を防ぐ）
                    if target_date in hist.index.strftime("%Y-%m-%d"):
                        row = hist.loc[hist.index.strftime("%Y-%m-%d") == target_date].iloc[0]
                    else:
                        print(f"スキップ: {stock_code} {target_date} のデータなし（最新={hist.index[-1].strftime('%Y-%m-%d')}）")
                        continue

                    stock_name = self.m_stock_manager.get_stock_name(stock_code) or "不明"
                    stock_data = {
                        'date': target_date,
                        'stock_code': stock_code,
                        'stock_name': stock_name,
                        'actual_open_price': math.trunc(row['Open']),
                        'actual_high_price': math.trunc(row['High']),
                        'actual_low_price': math.trunc(row['Low']),
                        'actual_close_price': math.trunc(row['Close']),
                        'actual_volume': math.trunc(row['Volume']),
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
