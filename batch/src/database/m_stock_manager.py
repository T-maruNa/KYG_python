from typing import Optional, List, Dict
from .db_manager import DBManager


class MStockManager(DBManager):
    def __init__(self):
        super().__init__()

    def get_stock_name(self, stock_code: str) -> Optional[str]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT stock_name FROM m_stock WHERE stock_code = %s', (stock_code,))
            row = cursor.fetchone()
            return row['stock_name'] if row else None

    def exists_stock(self, stock_code: str) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM m_stock WHERE stock_code = %s', (stock_code,))
            return cursor.fetchone()['count'] > 0

    def get_stock_by_industry_code_33(self, industry_code_33: str) -> List[Dict]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT stock_code FROM m_stock WHERE industry_code_33 = %s',
                (industry_code_33,)
            )
            return [{'stock_code': row['stock_code']} for row in cursor.fetchall()]

    def get_stock_all(self) -> List[Dict]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT stock_code FROM m_stock WHERE delete_flag = 0')
            return [{'stock_code': row['stock_code']} for row in cursor.fetchall()]
