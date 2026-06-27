from typing import Optional, List, Dict, Any
from .db_manager import DBManager


class TStockActualManager(DBManager):
    def __init__(self):
        super().__init__()

    def insert_stock_actual(self, stock_data: Dict[str, Any], user: str) -> bool:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO t_stock_actual (
                        date, stock_code, stock_name,
                        actual_open_price, actual_high_price,
                        actual_low_price, actual_close_price,
                        actual_volume, insert_user, update_user
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (date, stock_code) DO NOTHING
                ''', (
                    stock_data['date'], stock_data['stock_code'], stock_data['stock_name'],
                    stock_data['actual_open_price'], stock_data['actual_high_price'],
                    stock_data['actual_low_price'], stock_data['actual_close_price'],
                    stock_data['actual_volume'], user, user,
                ))
                return cursor.rowcount > 0
        except Exception as e:
            print(f'株価保存エラー: {e}')
            return False

    def get_stock_actual(self, stock_code: str = None, date_from: str = None,
                         date_to: str = None) -> List[Dict[str, Any]]:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                query = 'SELECT * FROM t_stock_actual WHERE 1=1'
                params = []
                if stock_code:
                    query += ' AND stock_code = %s'
                    params.append(stock_code)
                if date_from:
                    query += ' AND date >= %s'
                    params.append(date_from)
                if date_to:
                    query += ' AND date <= %s'
                    params.append(date_to)
                query += ' ORDER BY date DESC'
                cursor.execute(query, params)
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            print(f'株価取得エラー: {e}')
            return []
