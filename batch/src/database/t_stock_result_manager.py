from typing import List, Dict
from .db_manager import DBManager


class TStockResultManager(DBManager):
    def __init__(self):
        super().__init__()

    def insert_result(self, date: str, period: str, analyst_name: str, range: int,
                      stock_code: str, stock_name: str, predicted_price: int,
                      actual_price: int, is_up: bool, insert_user: str = 'SYSTEM') -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO t_stock_result
                    (date, period, analyst_name, range, stock_code, stock_name,
                     predicted_price, actual_price, is_up, insert_user, update_user)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (date, period, analyst_name, range, stock_code, stock_name,
                  predicted_price, actual_price, is_up, insert_user, insert_user))

    def get_result_by_date(self, date: str, period: str) -> List[Dict]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT stock_code, stock_name, predicted_price, actual_price
                FROM t_stock_result
                WHERE date = %s AND period = %s
                ORDER BY stock_code
            ''', (date, period))
            return [
                {'code': r['stock_code'], 'name': r['stock_name'],
                 'predicted': r['predicted_price'], 'actual': r['actual_price']}
                for r in cursor.fetchall()
            ]

    def get_accuracy_stats(self, date: str, period: str) -> Dict:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT
                    COUNT(*) AS total,
                    SUM(CASE WHEN actual_price > predicted_price THEN 1 ELSE 0 END) AS up_correct,
                    SUM(CASE WHEN actual_price < predicted_price THEN 1 ELSE 0 END) AS down_correct,
                    AVG(ABS(actual_price - predicted_price) * 100.0 / actual_price) AS avg_error_rate
                FROM t_stock_result
                WHERE date = %s AND period = %s
            ''', (date, period))
            row = cursor.fetchone()
            return {
                'total': row['total'], 'up_correct': row['up_correct'],
                'down_correct': row['down_correct'], 'avg_error_rate': row['avg_error_rate'],
            }

    def get_no_result_date(self) -> List[str]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT DISTINCT sp.predicted_date
                FROM t_stock_predict sp
                INNER JOIN t_stock_actual sa ON sp.predicted_date = sa.date
                WHERE sp.predicted_date NOT IN (SELECT date FROM t_stock_result)
            ''')
            return [row['predicted_date'] for row in cursor.fetchall()]
