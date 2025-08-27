import yfinance as yf
import pandas as pd
from datetime import date, datetime, timedelta
from src.database.m_stock_manager import MStockManager
from src.database.t_stock_actual_full_manager import TStockActualFullManager
import math
import time

class StockYFinanceFull:
    def __init__(self):
        self.m_stock_manager = MStockManager()
        self.actual_full_manager = TStockActualFullManager()

    def set_stock_prices(self, formatted_pre_date: str):
        """
        yfinanceを使用して株価を取得し、t_stock_actual_fullテーブルに保存する
        """
        today = date.today()
        formatted_date = today.strftime("%Y-%m-%d")

        try:
            # 銘柄一覧を取得
            stocks = self.m_stock_manager.get_stock_all()
            if not stocks:
                print("エラー: 銘柄データが見つかりません。")
                return
            
            print(f"銘柄の数: {len(stocks)}")
            # 株価データを格納するリスト
            stock_prices = []

            # 各銘柄の株価を取得
            for stock in stocks:
                try:
                    # 銘柄コードを取得（タプルの場合と辞書の場合に対応）
                    stock_code = stock['stock_code']
                    if self.actual_full_manager.exists_stock_actual_full(stock_code,formatted_pre_date):
                        print(f"銘柄コード {stock_code} は既に存在します。:{formatted_pre_date}")
                        continue

                    # 銘柄コードを4桁に整形（例：1234.T）
                    code = f"{str(stock_code).zfill(4)}.T"
                    
                    # yfinanceで株価を取得
                    ticker = yf.Ticker(code)
                    hist = ticker.history(period='1d',start=formatted_pre_date,end=formatted_date)
                    # API制限を考慮して少し待機
                    time.sleep(2)
                    print(hist)
                    if not hist.empty:
                        # 最新の株価データを取得
                        # 株名をマスタから取得
                        stock_name = self.m_stock_manager.get_stock_name(stock_code)
                        if stock_name is None:
                            stock_name = "不明"
                            print(f"警告: 銘柄名が見つかりません: {stock_code}")
                    else:
                        print(f"エラー: 銘柄コード {stock_code} の株価取得に失敗: {str(e)}")
                        continue
                    
                except Exception as e:
                    print(f"エラー: 銘柄コード {stock_code} の株価取得に失敗: {str(e)}")
                    continue

                # 株価データを辞書に追加
                stock_prices = {
                    'date': formatted_pre_date, # 前日の株価しかとれないので前日の日付を入れる
                    'stock_code': stock_code,
                    'stock_name': stock_name,
                    'actual_open_price': math.trunc(int(hist['Open'].iloc[-1])),
                    'actual_high_price': math.trunc(int(hist['High'].iloc[-1])),
                    'actual_low_price': math.trunc(int(hist['Low'].iloc[-1])),
                    'actual_close_price': math.trunc(int(hist['Close'].iloc[-1])),
                    'actual_volume': math.trunc(int(hist['Volume'].iloc[-1]))
                }

                # 株価データをデータベースに保存
                if stock_prices:
                    if self.actual_full_manager.insert_stock_actual(stock_prices, 'SYSTEM'):
                        print(f"成功: {stock_code}:{stock_name}株価データを保存しました。:{datetime.now()}")
                    else:
                        print(f"エラー: {stock_code}:{stock_name}株価データの保存に失敗しました。:{datetime.now()}")
                else:
                    print("警告: 保存する株価データがありません。")

        except Exception as e:
            print(f"エラー: 株価取得中にエラーが発生しました: {str(e)}")
            # デバッグ用：スタックトレースを表示
            import traceback
            print(traceback.format_exc())

if __name__ == "__main__":
    StockYFinanceFull().get_stock_prices() 
