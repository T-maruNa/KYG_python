from typing import Optional, List, Dict, Any
from .db_manager import DBManager


class TStockActualFullManager(DBManager):
    def __init__(self):
        super().__init__()

    def insert_stock_actual(self, stock_data: Dict[str, Any], user: str) -> bool:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO t_stock_actual_full (
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
            print(f'株価(full)保存エラー: {e}')
            return False

    def exists_stock_actual_full(self, stock_code: str, date: str) -> bool:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT COUNT(*) FROM t_stock_actual_full
                    WHERE stock_code = %s AND date = %s
                ''', (stock_code, date))
                return cursor.fetchone()['count'] > 0
        except Exception as e:
            print(f'株価(full)チェックエラー: {e}')
            return False

    def get_stock_history(self, stock_code: str, date_to: str, limit: int = 25) -> List[Dict[str, Any]]:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT date, actual_open_price, actual_high_price,
                           actual_low_price, actual_close_price, actual_volume
                    FROM t_stock_actual_full
                    WHERE stock_code = %s AND date <= %s
                    ORDER BY date DESC
                    LIMIT %s
                ''', (stock_code, date_to, limit))
                rows = cursor.fetchall()
                return [
                    {'date': r['date'], 'open': r['actual_open_price'], 'high': r['actual_high_price'],
                     'low': r['actual_low_price'], 'close': r['actual_close_price'], 'volume': r['actual_volume']}
                    for r in reversed(rows)
                ]
        except Exception as e:
            print(f'株価履歴取得エラー: {e}')
            return []

    def get_latest_date(self) -> Optional[str]:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT MAX(date) AS max_date FROM t_stock_actual_full')
                row = cursor.fetchone()
                return row['max_date'] if row else None
        except Exception as e:
            print(f'最新日付取得エラー: {e}')
            return None
