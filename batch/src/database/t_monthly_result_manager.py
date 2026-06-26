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
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(year_month, analyst_name) DO UPDATE SET
                        total_profit_loss = excluded.total_profit_loss,
                        final_balance = excluded.final_balance,
                        win_count = excluded.win_count,
                        lose_count = excluded.lose_count,
                        rank = excluded.rank,
                        is_mvp = excluded.is_mvp,
                        update_date = CURRENT_TIMESTAMP
                ''', (year_month, analyst_name, total_profit_loss, final_balance,
                      win_count, lose_count, rank, is_mvp))
                conn.commit()
                return True
        except Exception as e:
            print(f"月次結果保存エラー: {e}")
            return False

    def get_by_month(self, year_month: str) -> List[Dict]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT analyst_name, total_profit_loss, final_balance,
                       win_count, lose_count, rank, is_mvp
                FROM t_monthly_result
                WHERE year_month = ?
                ORDER BY final_balance DESC
            ''', (year_month,))
            return [
                {'analyst_name': r[0], 'total_profit_loss': r[1], 'final_balance': r[2],
                 'win_count': r[3], 'lose_count': r[4], 'rank': r[5], 'is_mvp': r[6]}
                for r in cursor.fetchall()
            ]

    def get_cumulative_mvp(self) -> List[Dict]:
        """累計MVP回数を取得する"""
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
                {'analyst_name': r[0], 'mvp_count': r[1],
                 'win_count': r[2], 'cumulative_profit_loss': r[3]}
                for r in cursor.fetchall()
            ]

    def exists(self, year_month: str) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT COUNT(*) FROM t_monthly_result WHERE year_month = ?
            ''', (year_month,))
            return cursor.fetchone()[0] > 0
