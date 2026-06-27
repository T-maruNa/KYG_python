from typing import Optional, List, Dict
from .db_manager import DBManager


class TCharacterAssetManager(DBManager):
    def __init__(self):
        super().__init__()

    def initialize_month(self, year_month: str, analyst_names: List[str]) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            for name in analyst_names:
                cursor.execute('''
                    INSERT INTO t_character_asset
                        (year_month, analyst_name, initial_balance, current_balance, update_user)
                    VALUES (%s, %s, 1000000, 1000000, 'SYSTEM')
                    ON CONFLICT (year_month, analyst_name) DO NOTHING
                ''', (year_month, name))

    def get_balance(self, year_month: str, analyst_name: str) -> Optional[int]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT current_balance FROM t_character_asset
                WHERE year_month = %s AND analyst_name = %s
            ''', (year_month, analyst_name))
            row = cursor.fetchone()
            return row['current_balance'] if row else None

    def update_balance(self, year_month: str, analyst_name: str, delta: int) -> bool:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE t_character_asset
                    SET current_balance = current_balance + %s,
                        update_date = CURRENT_TIMESTAMP,
                        update_user = 'SYSTEM'
                    WHERE year_month = %s AND analyst_name = %s
                ''', (delta, year_month, analyst_name))
                return cursor.rowcount > 0
        except Exception as e:
            print(f'残高更新エラー: {e}')
            return False

    def get_all_balances(self, year_month: str) -> List[Dict]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT analyst_name, initial_balance, current_balance
                FROM t_character_asset
                WHERE year_month = %s
                ORDER BY current_balance DESC
            ''', (year_month,))
            return [
                {'analyst_name': r['analyst_name'], 'initial_balance': r['initial_balance'],
                 'current_balance': r['current_balance']}
                for r in cursor.fetchall()
            ]

    def exists(self, year_month: str) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT COUNT(*) FROM t_character_asset WHERE year_month = %s',
                (year_month,)
            )
            return cursor.fetchone()['count'] > 0
