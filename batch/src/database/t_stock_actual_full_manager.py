import sqlite3
from typing import Optional, List, Dict, Any
from datetime import datetime
from .db_manager import DBManager

class TStockActualFullManager(DBManager):
    def __init__(self):
        super().__init__()

    def insert_stock_actual(self, stock_data: Dict[str, Any], user: str) -> bool:
        """
        株式実データを挿入
        Args:
            stock_data (Dict[str, Any]): 株式データ
                {
                    'date': '2024-03-20',
                    'stock_code': '0000',
                    'stock_name': '株式名',
                    'actual_open_price': 1000,
                    'actual_high_price': 1100,
                    'actual_low_price': 900,
                    'actual_close_price': 1050,
                    'actual_volume': 10000
                }
            user (str): 操作ユーザー名
        Returns:
            bool: 挿入成功でTrue
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO t_stock_actual_full (
                        date, stock_code, stock_name,
                        actual_open_price, actual_high_price,
                        actual_low_price, actual_close_price,
                        actual_volume,
                        insert_user, update_user
                    ) VALUES (
                        ?, ?, ?,
                        ?, ?, ?,
                        ?, ?,
                        ?, ?
                    )
                """, (
                    stock_data['date'],
                    stock_data['stock_code'],
                    stock_data['stock_name'],
                    stock_data['actual_open_price'],
                    stock_data['actual_high_price'],
                    stock_data['actual_low_price'],
                    stock_data['actual_close_price'],
                    stock_data['actual_volume'],
                    user, user
                ))
                conn.commit()
                return True
        except Exception as e:
            print(f"Error inserting stock data: {e}")
            return False
            
    
    def exists_stock_actual_full(self, stock_code: str, date: str) -> bool:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT COUNT(*) FROM t_stock_actual_full
                    WHERE stock_code = ? AND date = ?
                ''', (stock_code, date))
                return cursor.fetchone()[0] > 0
        except Exception as e:
            print(f"Error checking stock data: {e}")
            return False

    def get_stock_history(self, stock_code: str, date_to: str, limit: int = 25) -> List[Dict[str, Any]]:
        """直近 limit 件の履歴を古い順で返す"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT date, actual_open_price, actual_high_price,
                           actual_low_price, actual_close_price, actual_volume
                    FROM t_stock_actual_full
                    WHERE stock_code = ? AND date <= ?
                    ORDER BY date DESC
                    LIMIT ?
                ''', (stock_code, date_to, limit))
                rows = cursor.fetchall()
                return [
                    {'date': r[0], 'open': r[1], 'high': r[2],
                     'low': r[3], 'close': r[4], 'volume': r[5]}
                    for r in reversed(rows)
                ]
        except Exception as e:
            print(f"Error fetching stock history: {e}")
            return []

    def get_latest_date(self) -> Optional[str]:
        """t_stock_actual_full の最新日付を返す"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT MAX(date) FROM t_stock_actual_full')
                row = cursor.fetchone()
                return row[0] if row else None
        except Exception as e:
            print(f"Error fetching latest date: {e}")
            return None