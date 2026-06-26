from typing import Optional, List, Dict
from datetime import datetime
from .db_manager import DBManager


class TCharacterAssetManager(DBManager):
    def __init__(self):
        super().__init__()

    def initialize_month(self, year_month: str, analyst_names: List[str]) -> None:
        """月初に各キャラクターの資産を100万円で初期化する（既存レコードは更新しない）"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            for name in analyst_names:
                cursor.execute('''
                    INSERT OR IGNORE INTO t_character_asset
                        (year_month, analyst_name, initial_balance, current_balance, update_user)
                    VALUES (?, ?, 1000000, 1000000, 'SYSTEM')
                ''', (year_month, name))
            conn.commit()

    def get_balance(self, year_month: str, analyst_name: str) -> Optional[int]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT current_balance FROM t_character_asset
                WHERE year_month = ? AND analyst_name = ?
            ''', (year_month, analyst_name))
            row = cursor.fetchone()
            return row[0] if row else None

    def update_balance(self, year_month: str, analyst_name: str, delta: int) -> bool:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE t_character_asset
                    SET current_balance = current_balance + ?,
                        update_date = CURRENT_TIMESTAMP,
                        update_user = 'SYSTEM'
                    WHERE year_month = ? AND analyst_name = ?
                ''', (delta, year_month, analyst_name))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            print(f"残高更新エラー: {e}")
            return False

    def get_all_balances(self, year_month: str) -> List[Dict]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT analyst_name, initial_balance, current_balance
                FROM t_character_asset
                WHERE year_month = ?
                ORDER BY current_balance DESC
            ''', (year_month,))
            return [
                {'analyst_name': row[0], 'initial_balance': row[1], 'current_balance': row[2]}
                for row in cursor.fetchall()
            ]

    def exists(self, year_month: str) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT COUNT(*) FROM t_character_asset WHERE year_month = ?
            ''', (year_month,))
            return cursor.fetchone()[0] > 0
