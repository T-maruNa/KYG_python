import sqlite3
from typing import Optional, List, Dict, Any
from datetime import datetime
from .db_manager import DBManager

class TStockActualManager(DBManager):
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
                    INSERT INTO t_stock_actual (
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
            

    def get_stock_actual(self, stock_code: str = None, date_from: str = None, date_to: str = None) -> List[Dict[str, Any]]:
        """
        株式実データを取得
        Args:
            stock_code (str, optional): 銘柄コード
            date_from (str, optional): 開始日 (YYYY-MM-DD)
            date_to (str, optional): 終了日 (YYYY-MM-DD)
        Returns:
            List[Dict[str, Any]]: 株式データのリスト
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                query = "SELECT * FROM t_stock_actual WHERE 1=1"
                params = []
                
                if stock_code:
                    query += " AND stock_code = ?"
                    params.append(stock_code)
                
                if date_from:
                    query += " AND date >= ?"
                    params.append(date_from)
                
                if date_to:
                    query += " AND date <= ?"
                    params.append(date_to)
                
                query += " ORDER BY date DESC"
                
                cursor.execute(query, params)
                columns = [description[0] for description in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
                
        except Exception as e:
            print(f"Error fetching stock data: {e}")
            return []