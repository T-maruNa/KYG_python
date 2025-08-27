import sqlite3
from typing import Optional, List, Dict
from datetime import datetime
from .db_manager import DBManager

class TStockPredictManager(DBManager):
    def __init__(self):
        super().__init__()

    def insert_prediction(self, predicted_date: str , analyst_name: str, range: int, stock_code: str,
                         stock_name: str, predicted_open_price: float, predicted_high_price: float, predicted_low_price: float, predicted_close_price: float, predicted_volume: float, prediction_reason: str,
                         insert_user: str = "SYSTEM") -> None:
        """
        予測を登録する

        Args:
            predicted_date (str): 日付 (YYYY-MM-DD)
            analyst_name (str): アナリスト名
            range (int): 予想の範囲
            stock_code (str): 証券コード
            stock_name (str): 銘柄名
            predicted_open_price (float): 予想始値
            predicted_high_price (float): 予想高値
            predicted_low_price (float): 予想安値
            predicted_close_price (float): 予想終値
            predicted_volume (float): 予想出来高
            prediction_reason (str): 予測理由
            insert_user (str, optional): 登録ユーザー. デフォルトは "SYSTEM"
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO t_stock_predict 
                (predicted_date, analyst_name, range, stock_code, stock_name, predicted_open_price, predicted_high_price, predicted_low_price, predicted_close_price, predicted_volume, prediction_reason, insert_user)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (predicted_date, analyst_name, range, stock_code, stock_name, predicted_open_price, predicted_high_price, predicted_low_price, predicted_close_price, predicted_volume, prediction_reason, insert_user))
            conn.commit()

    def get_prediction_by_date(self, predicted_date: str, analyst_name: str) -> List[Dict]:
        """
        指定日付の予測を取得する

        Args:
            predicted_date (str): 日付 (YYYY-MM-DD)
            analyst_name (str): アナリスト名

        Returns:
            List[Dict]: 予測のリスト
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT stock_code, stock_name, predicted_open_price, predicted_high_price, predicted_low_price, predicted_close_price, predicted_volume, prediction_reason
                FROM t_stock_predict
                WHERE predicted_date = ? AND analyst_name = ?
                ORDER BY stock_code
            ''', (predicted_date, analyst_name))
            return [{"code": row[0], "name": row[1], "predicted_open_price": row[2], "predicted_high_price": row[3], "predicted_low_price": row[4], "predicted_close_price": row[5], "predicted_volume": row[6], "prediction_reason": row[7]} 
                   for row in cursor.fetchall()]

    def exists_prediction(self, predicted_date: str) -> bool:
        """
        指定日付の予測が存在するかチェックする

        Args:
            date (str): 日付 (YYYY-MM-DD)

        Returns:
            bool: 存在する場合はTrue
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT COUNT(*)
                FROM t_stock_predict
                WHERE predicted_date = ? 
            ''', (predicted_date,))
            return cursor.fetchone()[0] > 0 
    
