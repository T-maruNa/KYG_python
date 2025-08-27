import sqlite3
from typing import Optional, List, Dict
from datetime import datetime
from .db_manager import DBManager

class TStockResultManager(DBManager):
    def __init__(self):
        super().__init__()

    def insert_result(self, date: str, period: str, analyst_name: str, range: int, stock_code: str,
                     stock_name: str, predicted_price: int, actual_price: int, is_up: bool,
                     insert_user: str = "SYSTEM") -> None:
        """
        予測結果を登録する

        Args:
            date (str): 日付 (YYYY-MM-DD)
            period (str): 期間 (AM/PM)
            analyst_name (str): アナリスト名
            range (int): 予想の範囲
            stock_code (str): 証券コード
            stock_name (str): 株名
            predicted_price (int): 予測株価
            actual_price (int): 実際の株価
            is_up (bool): 予想が上がったかどうか
            insert_user (str, optional): 登録ユーザー. デフォルトは "SYSTEM"
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO t_stock_result 
                (date, period, analyst_name, range, stock_code, stock_name, predicted_price, actual_price, is_up, insert_user)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (date, period, analyst_name, range, stock_code, stock_name, predicted_price, actual_price, is_up, insert_user))
            conn.commit()

    def get_result_by_date(self, date: str, period: str) -> List[Dict]:
        """
        指定日付の予測結果を取得する

        Args:
            date (str): 日付 (YYYY-MM-DD)
            period (str): 期間 (AM/PM)

        Returns:
            List[Dict]: 予測結果のリスト
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT stock_code, stock_name, predicted_price, actual_price
                FROM t_stock_result
                WHERE date = ? AND period = ?
                ORDER BY stock_code
            ''', (date, period))
            return [{"code": row[0], "name": row[1], "predicted": row[2], "actual": row[3]} 
                   for row in cursor.fetchall()]

    def get_accuracy_stats(self, date: str, period: str) -> Dict:
        """
        指定日付の予測精度統計を取得する

        Args:
            date (str): 日付 (YYYY-MM-DD)
            period (str): 期間 (AM/PM)

        Returns:
            Dict: 予測精度の統計情報
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN actual_price > predicted_price THEN 1 ELSE 0 END) as up_correct,
                    SUM(CASE WHEN actual_price < predicted_price THEN 1 ELSE 0 END) as down_correct,
                    AVG(ABS(actual_price - predicted_price) * 100.0 / actual_price) as avg_error_rate
                FROM t_stock_result
                WHERE date = ? AND period = ?
            ''', (date, period))
            row = cursor.fetchone()
            return {
                "total": row[0],
                "up_correct": row[1],
                "down_correct": row[2],
                "avg_error_rate": row[3]
            }

    def get_no_result_date(self) -> List[Dict]:
        """
        予想と実データが揃っていて
        結果が存在しない日付を取得する

        Args:
        """ 
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT DISTINCT sp.predicted_date
                FROM t_stock_predict sp
                INNER JOIN t_stock_actual sa 
                           ON sp.predicted_date = sa.date
                WHERE sp.predicted_date NOT IN (SELECT date FROM t_stock_result)
            ''')
            return [row[0] for row in cursor.fetchall()]
