import pandas as pd
from typing import List, Dict
from src.characters import get_analysts
from src.ai_clients.openai_client import OpenAIClient
from src.ai_clients.gemini_client import GeminiClient
from src.database.t_stock_predict_manager import TStockPredictManager
from src.database.m_stock_manager import MStockManager
from src.database.t_stock_actual_manager import TStockActualManager
from src.characters.ichinose import IchinoseRitu
import csv
import io
import random
import ast
import math
from datetime import datetime
import json

class StockPredictor:
    def __init__(self):
        self.analysts = get_analysts()
        self.openai_client = OpenAIClient()
        self.gemini_client = GeminiClient()
        self.predict_manager = TStockPredictManager()
        self.m_stock_manager = MStockManager()
        self.actual_manager = TStockActualManager()

    def create_messages(self, analyst: object, csv_text: str,  yesterday_date: str, tomorrow_date: str) -> List[Dict[str, str]]:
        """
        メッセージを作成する

        Args:
            analyst (object): アナリストのインスタンス
            stock_data (List[Dict]): 株価データのリスト
        Returns:
            List[Dict[str, str]]: チャットメッセージのリスト
        """

        return [
            {
                "role": "system",
                "content": f"あなたは{analyst.name}です。{analyst.title}として、{analyst.description}"
            },
            {
                "role": "user",
                "content": f"""以下のCSVは{yesterday_date}の株価です：
                {csv_text}

                以上のCSV内の銘柄から、{tomorrow_date}の終値が最も上がりそうな銘柄を予測してください。
                あなたの専門分野である{analyst.style}の観点から、特に{analyst.focus}に注目して分析してください。

                以下の条件で銘柄を選んでください：
                ・株価が100以下の銘柄から3つ
                ・株価が1000以下の銘柄から3つ
                ・株価が10000以下の銘柄から3つ
                合計9つの銘柄を選んでください。
                CSVに記載されていない銘柄は選ばないでください。
                ハルシネーションしないでください。

                予想結果はcsv形式で出力してください。
                csv形式の例：
                証券コード,銘柄名,予想始値,予想高値,予想安値,予想終値,予想出来高,予測理由
                
                ヘッダーは必ず証券コード,銘柄名,予想始値,予想高値,予想安値,予想終値,予想出来高,予測理由としてください。
                結果はcsvの中身以外は一切出力しないでください。
                """
            }
        ]

    def predict(self, yesterday_date: str, tomorrow_date: str) -> None:
        """
        株価予測を実行する
        結果をDBに保存する

        Args:
            date (str): 日付 (YYYY-MM-DD)
            tomorrow_date (str): 明日の日付 (YYYY-MM-DD)

        """
        # 昨日の株価データを取得
        stock_data = self.actual_manager.get_stock_actual(date_from=yesterday_date)
        if not stock_data:
            print(f"警告: {yesterday_date} の株価データが見つかりません")
            return

        # 株価データをCSV形式の文字列に変換
        csv_lines = ['証券コード,銘柄名,始値,高値,安値,終値,出来高']
        for stock in stock_data:
            csv_lines.append(f"{stock['stock_code']},{stock['stock_name']},{stock['actual_open_price']},{stock['actual_high_price']},{stock['actual_low_price']},{stock['actual_close_price']},{stock['actual_volume']}")
        csv_text = '\n'.join(csv_lines)


        # 各アナリストの予測を実行
        for analyst in self.analysts:
            try:
                #AIからの結果を取得
                messages = self.create_messages(analyst, csv_text, yesterday_date, tomorrow_date)
                result = analyst.stock_run(messages)
                
                # 結果がNoneの場合
                if result is None:
                    print(f"警告: {analyst.name}からの応答がありません")
                    continue
                
                # 空行を削除し、CSV形式を確認
                lines = []
                for line in result.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    # カンマで区切られているかチェック
                    if ',' in line:
                        lines.append(line)
                
                if not lines:
                    print(f"警告: {analyst.name}からの応答に有効なCSVデータがありません")
                    continue
                
                # 予測結果をCSVとして解析
                csv_reader = csv.reader(io.StringIO('\n'.join(lines)))
                
                # ヘッダー行を探す
                header = None
                rows = list(csv_reader)  # 全行をリストに変換
                coulums_len = 8
                for i, row in enumerate(rows):
                    if len(row) >= coulums_len and row[0] == "証券コード" and row[1] == "銘柄名":
                        header = row
                        rows = rows[i+1:]  # ヘッダー以降の行を取得
                        break
                
                if not header:
                    print(f"警告: {analyst.name}からの応答に正しいヘッダーが見つかりません")
                    continue
                
                # 予測結果をデータベースに保存
                for row in rows:
                    if len(row) >= coulums_len:  # 必要な列が存在することを確認
                        try:
                            stock_code, stock_name, predicted_open_price, predicted_high_price, predicted_low_price, predicted_close_price, predicted_volume, predicted_reason = row
                            predicted_open_price = float(predicted_open_price)
                            predicted_high_price = float(predicted_high_price)
                            predicted_low_price = float(predicted_low_price)
                            predicted_close_price = float(predicted_close_price)
                            predicted_volume = float(predicted_volume)
                            
                            # 株価の範囲を設定
                            if predicted_open_price <= 100:
                                range = 100
                            elif predicted_open_price <= 1000:
                                range = 1000
                            elif predicted_open_price <= 10000:
                                range = 10000
                            else:
                                range = 100000

                            # 株名をマスタから取得
                            stock_name = self.m_stock_manager.get_stock_name(stock_code)
                            if stock_name is None:
                                stock_name = "不明"
                                print(f"警告: 銘柄名が見つかりません: {stock_code}")

                            # 予想データベースに保存
                            self.predict_manager.insert_prediction(
                                predicted_date=tomorrow_date,
                                analyst_name=analyst.name,
                                stock_code=stock_code,
                                stock_name=stock_name,
                                range=range,
                                predicted_open_price=predicted_open_price,
                                predicted_high_price=predicted_high_price,
                                predicted_low_price=predicted_low_price,
                                predicted_close_price=predicted_close_price,
                                predicted_volume=predicted_volume,
                                prediction_reason=predicted_reason
                            )
                        except ValueError:
                            print(f"警告: 無効なデータ形式をスキップしました: {row}")
                            continue
            except Exception as e:
                print(f"エラー: {analyst.name}の処理中にエラーが発生しました: {str(e)}")
                continue 

        #一ノ瀬メソッド発動
        try:
            ritu = IchinoseRitu()
            ritu_messages = [
                {
                    "role": "system",
                    "content": f"あなたは{ritu.name}です。{ritu.title}。{ritu.description}"
                },
                {
                    "role": "user",
                    "content": f"""勘で選んだわ！今日はお腹が減ってたから！の様な判断材料になっていない事9個いって
                    セリフ以外はいりません。
                    毎回言う事は変えてください。
                    結果は、配列形式でください。
                    """
                }
            ]
            # 一ノ瀬の理由を取得
            ritu_reason = ritu.stock_run(ritu_messages)

            # 文字列の場合は配列に変換
            if isinstance(ritu_reason, str):
                # 改行で分割して配列形式の行を探す
                lines = ritu_reason.split('\n')
                
                # コードブロック内の配列を探す
                in_code_block = False
                array_content = []
                for line in lines:
                    line = line.strip()
                    if line.startswith('```'):
                        in_code_block = not in_code_block
                        continue
                    if in_code_block and line.startswith('['):
                        array_content.append(line)
                    elif in_code_block and line.endswith(']'):
                        array_content.append(line)
                    elif in_code_block and array_content:
                        array_content.append(line)
                
                if array_content:
                    try:
                        # 配列の内容を結合
                        array_str = ''.join(array_content)
                        # 配列の中身だけを抽出
                        array_str = array_str.strip('[]')
                        # 各行を配列に変換
                        reasons = [reason.strip().strip('"') for reason in array_str.split(',')]
                        ritu_reason = reasons
                    except Exception as e:
                        print(f"エラー: {str(e)}")
                        ritu_reason = []
                else:
                    ritu_reason = []
            # 配列でない場合は空配列に変換
            elif not isinstance(ritu_reason, list):
                ritu_reason = []
            
            # 理由が空の場合はデフォルトの理由を使用
            if not ritu_reason:
                ritu_reason = ["お腹が減った", "眠い", "疲れた", "暇だった", "気分が良かった", 
                             "天気が良かった", "運が良かった", "勘が冴えていた", "直感が当たった"]
            
            # 9個になるまで理由を繰り返し
            original_reasons = ritu_reason.copy()  # 元の理由を保存
            while len(ritu_reason) < 9:
                ritu_reason.append(original_reasons[len(ritu_reason) % len(original_reasons)])
            
            # 9個に制限
            ritu_reason = ritu_reason[:9]

            # 株価範囲ごとに銘柄を抽出
            stocks_100 = [{'stock_code': stock['stock_code'], 'stock_name': stock['stock_name'], 'actual_open_price': stock['actual_open_price'], 'range': 100} 
                         for stock in stock_data if stock['actual_open_price'] <= 100]
            stocks_1000 = [{'stock_code': stock['stock_code'], 'stock_name': stock['stock_name'], 'actual_open_price': stock['actual_open_price'], 'range': 1000} 
                          for stock in stock_data if 100 < stock['actual_open_price'] <= 1000]
            stocks_10000 = [{'stock_code': stock['stock_code'], 'stock_name': stock['stock_name'], 'actual_open_price': stock['actual_open_price'], 'range': 10000} 
                           for stock in stock_data if 1000 < stock['actual_open_price'] <= 10000]

            # 各範囲から3つずつランダムに選択
            selected_stocks = (
                random.sample(stocks_100, min(3, len(stocks_100))) +
                random.sample(stocks_1000, min(3, len(stocks_1000))) +
                random.sample(stocks_10000, min(3, len(stocks_10000)))
            )

            for i, stock in enumerate(selected_stocks):
                # 乱数を予測値とする
                current_price = stock['actual_open_price']
                predicted_open_price = math.floor(current_price * random.uniform(1.001, 1.5))
                predicted_low_price = math.floor(current_price * random.uniform(1.001, 1.5))
                predicted_close_price = math.floor(current_price * random.uniform(1.001, 1.5))
                predicted_volume = math.floor(current_price * random.uniform(1.001, 1.5))

                if predicted_open_price > predicted_close_price :
                    high_price = predicted_open_price
                    low_price = predicted_close_price
                else :
                    high_price = predicted_close_price
                    low_price = predicted_open_price

                predicted_high_price = math.floor(high_price * random.uniform(1.001, 1.5))
                predicted_low_price = math.floor(low_price * random.uniform(1.000, 0.6))

                self.predict_manager.insert_prediction(
                    predicted_date=tomorrow_date,
                    analyst_name=ritu.name,
                    stock_code=stock['stock_code'],
                    stock_name=stock['stock_name'],
                    range=stock['range'],
                    predicted_open_price=predicted_open_price,
                    predicted_high_price=predicted_high_price,
                    predicted_low_price=predicted_low_price,
                    predicted_close_price=predicted_close_price,
                    predicted_volume=predicted_volume,
                    prediction_reason=ritu_reason[i]
                )
        except Exception as e:
            print(f"エラー: {ritu.name}の処理中にエラーが発生しました: {str(e)}")
