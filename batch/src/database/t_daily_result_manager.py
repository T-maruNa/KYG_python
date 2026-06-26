from typing import Optional, List, Dict
from .db_manager import DBManager


class TDailyResultManager(DBManager):
    def __init__(self):
        super().__init__()

    def upsert(self, result_date: str, analyst_name: str, total_profit_loss: int,
               current_balance: int, win_count: int, lose_count: int) -> bool:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO t_daily_result
                        (result_date, analyst_name, total_profit_loss, current_balance,
                         win_count, lose_count)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(result_date, analyst_name) DO UPDATE SET
                        total_profit_loss = excluded.total_profit_loss,
                        current_balance = excluded.current_balance,
                        win_count = excluded.win_count,
                        lose_count = excluded.lose_count
                ''', (result_date, analyst_name, total_profit_loss, current_balance,
                      win_count, lose_count))
                conn.commit()
                return True
        except Exception as e:
            print(f"日次結果保存エラー: {e}")
            return False

    def get_by_date(self, result_date: str) -> List[Dict]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT analyst_name, total_profit_loss, current_balance, win_count, lose_count
                FROM t_daily_result
                WHERE result_date = ?
                ORDER BY current_balance DESC
            ''', (result_date,))
            return [
                {'analyst_name': r[0], 'total_profit_loss': r[1], 'current_balance': r[2],
                 'win_count': r[3], 'lose_count': r[4]}
                for r in cursor.fetchall()
            ]

    def exists(self, result_date: str) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT COUNT(*) FROM t_daily_result WHERE result_date = ?
            ''', (result_date,))
            return cursor.fetchone()[0] > 0
