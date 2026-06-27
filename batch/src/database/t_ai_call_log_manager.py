from typing import Dict
from .db_manager import DBManager


class TAiCallLogManager(DBManager):
    def __init__(self):
        super().__init__()

    def log(self, call_date: str, call_type: str, model: str,
            estimated_cost_jpy: float, success: bool = True) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO t_ai_call_log (call_date, call_type, model, estimated_cost_jpy, success)
                VALUES (%s, %s, %s, %s, %s)
            ''', (call_date, call_type, model, estimated_cost_jpy, 1 if success else 0))

    def count_today(self, call_date: str) -> int:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT COUNT(*) FROM t_ai_call_log
                WHERE call_date = %s AND success = 1
            ''', (call_date,))
            return cursor.fetchone()['count']

    def monthly_cost(self, year_month: str) -> float:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT COALESCE(SUM(estimated_cost_jpy), 0) AS total
                FROM t_ai_call_log
                WHERE call_date LIKE %s AND success = 1
            ''', (f'{year_month}%',))
            return cursor.fetchone()['total']

    def daily_stats(self, call_date: str) -> Dict:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT COUNT(*) AS cnt, COALESCE(SUM(estimated_cost_jpy), 0) AS cost
                FROM t_ai_call_log
                WHERE call_date = %s
            ''', (call_date,))
            row = cursor.fetchone()
            return {'count': row['cnt'], 'cost': row['cost']}
