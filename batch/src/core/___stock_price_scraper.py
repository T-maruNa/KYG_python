import os
import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import csv
import math
import re
import time
from src.database.t_stock_actual_manager import TStockActualManager

class StockPriceScraper:
    def __init__(self):
        self.actual_manager = TStockActualManager()
        self.url = "https://minkabu.jp/stock/stocksitemap/25"
        self.param_text = "?page="

    def scrape_stock_prices(self, period: str = "AM") -> None:
        """
        株価をスクレイピングしてDBに保存する

        Args:
            period (str, optional): "AM" または "PM". デフォルトは "AM".
        """
        # 現在の日付を取得
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")

        # 重複チェック用セット
        code_set = set()
        
        # 全件数取得スクレイピング
        req = requests.get(self.url)
        req.encoding = req.apparent_encoding # 日本語の文字化け防止

        # HTMLの解析
        bsObj = BeautifulSoup(req.text,"html.parser")

        # 全件数を取得
        total_count = bsObj.find("p", class_="text-xs").text
        # 全件数からページ数を計算
        page_count = math.ceil(int(re.search('(?<=全)([0-9,]+)(?=件)', total_count).group()) / 20)

        for i in range(1, page_count + 1):
            # ページごとのURLを生成
            page_url = self.url + self.param_text + str(i)
            # スクレイピング
            req2 = requests.get(page_url)
            req2.encoding = req2.apparent_encoding  # 日本語の文字化け防止
            # 読み込みの完了を待つ
            # Minkabuのページは読み込みに時間がかかるため、3秒待機
            time.sleep(3)
            # ページのHTMLを解析
            bsObj2 = BeautifulSoup(req2.text, "html.parser") 
            # 銘柄の行を取得
            rows = bsObj2.find_all("tr", class_="border-b")

            # 各行から抽出
            # 銘柄コード、銘柄名、株価を抽出
            # 取得した行をループ
            for row in rows:
                code = row.find("div", class_="text-xs text-slate-400").text
                name = row.find("a", class_="text-minkabuOldLink").text
                price = re.search('([0-9,]+)', row.find("p").text).group()
                price = price.replace(',', '')
                # 銘柄コード、銘柄名、価格が全て存在し、かつ重複していない場合に出力
                if code and name and price and code not in code_set:
                    # 実際の株価テーブルに保存
                    self.actual_manager.insert_actual(
                        date=today,
                        period=period,
                        stock_code=code,
                        stock_name=name,
                        actual_stock_price=int(price)
                    )
                    code_set.add(code)

if __name__ == "__main__":
    scraper = StockPriceScraper()
    scraper.scrape_stock_prices("test.csv")  # CSV出力
    print("CSVファイルの出力が完了しました。")