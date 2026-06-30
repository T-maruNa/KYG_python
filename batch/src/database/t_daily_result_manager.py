from typing import List, Dict
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
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (result_date, analyst_name) DO UPDATE SET
                        total_profit_loss = EXCLUDED.total_profit_loss,
                        current_balance   = EXCLUDED.current_balance,
                        win_count         = EXCLUDED.win_count,
                        lose_count        = EXCLUDED.lose_count
                ''', (result_date, analyst_name, total_profit_loss, current_balance,
                      win_count, lose_count))
                return True
        except Exception as e:
            print(f'日次結果保存エラー: {e}')
            return False

    def get_by_date(self, result_date: str) -> List[Dict]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT analyst_name, total_profit_loss, current_balance, win_count, lose_count
                FROM t_daily_result
                WHERE result_date = %s
                ORDER BY current_balance DESC
            ''', (result_date,))
            return [
                {'analyst_name': r['analyst_name'], 'total_profit_loss': r['total_profit_loss'],
                 'current_balance': r['current_balance'], 'win_count': r['win_count'],
                 'lose_count': r['lose_count']}
                for r in cursor.fetchall()
            ]

    def get_latest(self, before_date: str) -> List[Dict]:
        """指定日より前の直近営業日の結果を返す。前日データ表示用。"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT analyst_name, total_profit_loss, current_balance, win_count, lose_count
                FROM t_daily_result
                WHERE result_date < %s
                ORDER BY result_date DESC, current_balance DESC
                LIMIT 3
            ''', (before_date,))
            return [
                {'analyst_name': r['analyst_name'], 'total_profit_loss': r['total_profit_loss'],
                 'current_balance': r['current_balance'], 'win_count': r['win_count'],
                 'lose_count': r['lose_count']}
                for r in cursor.fetchall()
            ]

    def exists(self, result_date: str) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM t_daily_result WHERE result_date = %s', (result_date,))
            return cursor.fetchone()['count'] > 0
