import sqlite3
from typing import Optional, List, Dict
from datetime import datetime
from .db_manager import DBManager

class MStockManager(DBManager):
    def __init__(self):
        super().__init__()

    def get_stock_name(self, stock_code: str) -> Optional[str]:
        """
        証券コードから株名を取得する

        Args:
            stock_code (str): 証券コード

        Returns:
            Optional[str]: 株名
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT stock_name
                FROM m_stock
                WHERE stock_code = ?
            ''', (stock_code,))
            row = cursor.fetchone()
            return row[0] if row else None


    def exists_stock(self, stock_code: str) -> bool:
        """
        証券コードが存在するかチェックする

        Args:
            stock_code (str): 証券コード

        Returns:
            bool: 存在する場合はTrue
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT COUNT(*)
                FROM m_stock
                WHERE stock_code = ?
            ''', (stock_code,))
            return cursor.fetchone()[0] > 0

    def get_all_stocks(self) -> List[Dict]:
        """
        全ての有効な株情報を取得する

        Returns:
            List[Dict]: 株情報のリスト
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT CODE, NAME 
                FROM m_stock 
                WHERE DELETE_FLAG = 0 
                ORDER BY CODE
            ''')
            return [{"code": row[0], "name": row[1]} for row in cursor.fetchall()]

    def get_stock_by_industry_code_33(self, industry_code_33: str) -> Optional[str]:
        """
        33業種コードから証券コードを取得する

        Args:
            industry_code_33 (str): 33業種コード

        Returns:
            Optional[str]: 株名
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT stock_code
                FROM m_stock
                WHERE industry_code_33 = ?
            ''', (industry_code_33,))
            return [{"stock_code": row[0]} for row in cursor.fetchall()]
    
    def get_stock_all(self) -> Optional[str]:
        """
        33業種コードから証券コードを取得する

        Args:
            industry_code_33 (str): 33業種コード

        Returns:
            Optional[str]: 株名
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT stock_code
                FROM m_stock
                WHERE DELETE_FLAG = 0
            ''')
            return [{"stock_code": row[0]} for row in cursor.fetchall()]