from typing import List, Dict, Optional
from datetime import datetime, timedelta
from src.database.t_stock_result_manager import TStockResultManager
from src.database.t_stock_predict_manager import TStockPredictManager
from src.database.t_stock_actual_manager import TStockActualManager

class StockResultAnalyzer:
    def __init__(self):
        self.result_manager = TStockResultManager()
        self.predict_manager = TStockPredictManager()
        self.actual_manager = TStockActualManager()

    def insert_prediction_results(self, date: str, period: str) -> Dict:
        """
        予測結果を登録する

        Args:
            date (str): 日付 (YYYY-MM-DD)
            period (str): 期間 (AM/PM)

        Returns:
            Dict: 登録結果
        """
        # 既存の予測結果をチェック
        if self.result_manager.exists_result(date, period):
            return {
                "error": f"{date} {period}の予測結果は既に登録されています"
            }

        # 予想した段階の日付を設定
        period_predict = "PM" if period == "AM" else "AM"
        # AMなら前日のPM、PMなら当日のAM
        date_predict = (datetime.now() + timedelta(days=-1)).strftime("%Y-%m-%d") if period == "AM" else date

        # 予測データを取得
        predictions = self.predict_manager.get_prediction_by_date(date_predict, period_predict)
        if not predictions:
            return {
                "error": f"{date} {period}の予測データが見つかりません"
            }

        # 実際の株価データを取得
        actual_prices = self.actual_manager.get_actual_by_date(date, period)
        if not actual_prices:
            return {
                "error": f"{date} {period}の実際の株価データが見つかりません"
            }

        # 実際の株価を辞書に変換 [{"stock_code": "1234", "stock_price": 1000}]
        actual_price_dict = {price["stock_code"]: price["stock_price"] for price in actual_prices}

        for pred in predictions:
            if pred["stock_code"] in actual_price_dict:
                try:
                    # 予想株価
                    predicted_price = pred["predicted_price"]
                    # 実際の株価
                    actual_price = actual_price_dict[pred["stock_code"]]
                    # 予想株価と実際の株価の差
                    price_diff = actual_price - predicted_price
                    # 予想株価と実際の株価の差が正か負か
                    is_up = True if price_diff > 0 else False

                    # 予測結果を登録
                    self.result_manager.insert_result(
                        date=date,
                        period=period,
                        analyst_name=pred["analyst_name"],
                        range=pred["range"],
                        stock_code=pred["stock_code"],
                        stock_name=pred["stock_name"],
                        predicted_price=predicted_price,
                        actual_price=actual_price,
                        is_up=is_up
                    )

                except Exception as e:
                    print(f"警告: 証券コード {pred['stock_code']} の登録に失敗しました: {str(e)}")

    def insert_prediction_result(self, date: str, period: str, stock_code: str, 
                               stock_name: str, predicted_price: int, actual_price: int) -> Dict:
        """
        単一の予測結果を登録する

        Args:
            date (str): 日付 (YYYY-MM-DD)
            period (str): 期間 (AM/PM)
            stock_code (str): 証券コード
            stock_name (str): 株名
            predicted_price (int): 予測株価
            actual_price (int): 実際の株価

        Returns:
            Dict: 登録結果
        """
        try:
            self.result_manager.insert_result(
                date=date,
                period=period,
                stock_code=stock_code,
                stock_name=stock_name,
                predicted_price=predicted_price,
                actual_price=actual_price
            )
            return {
                "success": True,
                "message": f"証券コード {stock_code} の予測結果を登録しました"
            }
        except Exception as e:
            return {
                "error": f"予測結果の登録に失敗しました: {str(e)}"
            }

    def analyze_prediction_accuracy(self, date: str, period: str) -> Dict:
        """
        予測精度を分析する

        Args:
            date (str): 日付 (YYYY-MM-DD)
            period (str): 期間 (AM/PM)

        Returns:
            Dict: 分析結果
        """
        # 予測結果を取得
        results = self.result_manager.get_result_by_date(date, period)
        if not results:
            return {
                "error": f"{date} {period}の予測結果が見つかりません"
            }

        # 統計情報を取得
        stats = self.result_manager.get_accuracy_stats(date, period)
        
        # 詳細な分析結果を作成
        analysis = {
            "date": date,
            "period": period,
            "total_predictions": stats["total"],
            "up_correct": stats["up_correct"],
            "down_correct": stats["down_correct"],
            "avg_error_rate": round(stats["avg_error_rate"], 2) if stats["avg_error_rate"] else 0,
            "accuracy_rate": round((stats["up_correct"] + stats["down_correct"]) * 100 / stats["total"], 2) if stats["total"] > 0 else 0,
            "details": []
        }

        # 各予測の詳細を追加
        for result in results:
            price_diff = result["actual"] - result["predicted"]
            price_diff_rate = round(price_diff * 100 / result["predicted"], 2)
            
            analysis["details"].append({
                "code": result["code"],
                "name": result["name"],
                "predicted": result["predicted"],
                "actual": result["actual"],
                "price_diff": price_diff,
                "price_diff_rate": price_diff_rate,
                "is_correct": (price_diff > 0 and result["predicted"] > 0) or (price_diff < 0 and result["predicted"] < 0)
            })

        return analysis

    def get_analyst_performance(self, analyst_name: str, start_date: str, end_date: str) -> Dict:
        """
        アナリストの予測パフォーマンスを分析する

        Args:
            analyst_name (str): アナリスト名
            start_date (str): 開始日 (YYYY-MM-DD)
            end_date (str): 終了日 (YYYY-MM-DD)

        Returns:
            Dict: パフォーマンス分析結果
        """
        # アナリストの予測を取得
        predictions = self.predict_manager.get_predictions_by_analyst(analyst_name, start_date, end_date)
        if not predictions:
            return {
                "error": f"{analyst_name}の予測結果が見つかりません"
            }

        # パフォーマンス統計を計算
        total_predictions = len(predictions)
        correct_predictions = 0
        total_error_rate = 0

        for pred in predictions:
            # 実際の株価を取得
            actual_price = self.actual_manager.get_actual_by_date_and_code(
                pred["date"], pred["period"], pred["stock_code"]
            )
            if actual_price:
                price_diff = actual_price["stock_price"] - pred["predicted_price"]
                if (price_diff > 0 and pred["predicted_price"] > 0) or (price_diff < 0 and pred["predicted_price"] < 0):
                    correct_predictions += 1
                total_error_rate += abs(price_diff * 100 / actual_price["stock_price"])

        return {
            "analyst_name": analyst_name,
            "period": f"{start_date} to {end_date}",
            "total_predictions": total_predictions,
            "correct_predictions": correct_predictions,
            "accuracy_rate": round(correct_predictions * 100 / total_predictions, 2) if total_predictions > 0 else 0,
            "avg_error_rate": round(total_error_rate / total_predictions, 2) if total_predictions > 0 else 0
        }

    def compare_analysts(self, start_date: str, end_date: str) -> List[Dict]:
        """
        アナリスト間の予測精度を比較する

        Args:
            start_date (str): 開始日 (YYYY-MM-DD)
            end_date (str): 終了日 (YYYY-MM-DD)

        Returns:
            List[Dict]: アナリスト比較結果のリスト
        """
        # 各アナリストのパフォーマンスを取得
        analysts = ["桜庭 みらい", "鷲見 玲"]
        comparison = []

        for analyst in analysts:
            performance = self.get_analyst_performance(analyst, start_date, end_date)
            if "error" not in performance:
                comparison.append(performance)

        # 精度率でソート
        comparison.sort(key=lambda x: x["accuracy_rate"], reverse=True)
        return comparison 