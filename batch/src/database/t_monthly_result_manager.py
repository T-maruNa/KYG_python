from typing import Optional, List, Dict
from .db_manager import DBManager


class TMonthlyResultManager(DBManager):
    def __init__(self):
        super().__init__()

    def upsert(self, year_month: str, analyst_name: str, total_profit_loss: int,
               final_balance: int, win_count: int, lose_count: int,
               rank: int = None, is_mvp: int = 0) -> bool:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO t_monthly_result
                        (year_month, analyst_name, total_profit_loss, final_balance,
                         win_count, lose_count, rank, is_mvp)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (year_month, analyst_name) DO UPDATE SET
                        total_profit_loss = EXCLUDED.total_profit_loss,
                        final_balance     = EXCLUDED.final_balance,
                        win_count         = EXCLUDED.win_count,
                        lose_count        = EXCLUDED.lose_count,
                        rank              = EXCLUDED.rank,
                        is_mvp            = EXCLUDED.is_mvp,
                        update_date       = CURRENT_TIMESTAMP
                ''', (year_month, analyst_name, total_profit_loss, final_balance,
                      win_count, lose_count, rank, is_mvp))
                return True
        except Exception as e:
            print(f'月次結果保存エラー: {e}')
            return False

    def get_by_month(self, year_month: str) -> List[Dict]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT analyst_name, total_profit_loss, final_balance,
                       win_count, lose_count, rank, is_mvp
                FROM t_monthly_result
                WHERE year_month = %s
                ORDER BY final_balance DESC
            ''', (year_month,))
            return [
                {'analyst_name': r['analyst_name'], 'total_profit_loss': r['total_profit_loss'],
                 'final_balance': r['final_balance'], 'win_count': r['win_count'],
                 'lose_count': r['lose_count'], 'rank': r['rank'], 'is_mvp': r['is_mvp']}
                for r in cursor.fetchall()
            ]

    def get_cumulative_mvp(self) -> List[Dict]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT analyst_name,
                       SUM(is_mvp) AS mvp_count,
                       SUM(CASE WHEN rank = 1 THEN 1 ELSE 0 END) AS win_count,
                       SUM(total_profit_loss) AS cumulative_profit_loss
                FROM t_monthly_result
                GROUP BY analyst_name
                ORDER BY mvp_count DESC, win_count DESC
            ''')
            return [
                {'analyst_name': r['analyst_name'], 'mvp_count': r['mvp_count'],
                 'win_count': r['win_count'], 'cumulative_profit_loss': r['cumulative_profit_loss']}
                for r in cursor.fetchall()
            ]

    def exists(self, year_month: str) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM t_monthly_result WHERE year_month = %s', (year_month,))
            return cursor.fetchone()['count'] > 0
