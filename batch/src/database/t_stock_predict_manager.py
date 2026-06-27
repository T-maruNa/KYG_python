from typing import Optional, List, Dict
from .db_manager import DBManager


class TStockPredictManager(DBManager):
    def __init__(self):
        super().__init__()

    def insert_prediction(self, predicted_date: str, analyst_name: str, range: int,
                          stock_code: str, stock_name: str, predicted_open_price: float,
                          predicted_high_price: float, predicted_low_price: float,
                          predicted_close_price: float, predicted_volume: float,
                          prediction_reason: str, insert_user: str = 'SYSTEM') -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO t_stock_predict
                    (predicted_date, analyst_name, range, stock_code, stock_name,
                     predicted_open_price, predicted_high_price, predicted_low_price,
                     predicted_close_price, predicted_volume, prediction_reason, insert_user)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (predicted_date, analyst_name, range, stock_code, stock_name,
                  predicted_open_price, predicted_high_price, predicted_low_price,
                  predicted_close_price, predicted_volume, prediction_reason, insert_user))

    def get_prediction_by_date(self, predicted_date: str, analyst_name: str) -> List[Dict]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT stock_code, stock_name, predicted_open_price, predicted_high_price,
                       predicted_low_price, predicted_close_price, predicted_volume,
                       prediction_reason, range
                FROM t_stock_predict
                WHERE predicted_date = %s AND analyst_name = %s
                ORDER BY stock_code
            ''', (predicted_date, analyst_name))
            return [
                {'code': r['stock_code'], 'name': r['stock_name'],
                 'predicted_open_price': r['predicted_open_price'],
                 'predicted_high_price': r['predicted_high_price'],
                 'predicted_low_price': r['predicted_low_price'],
                 'predicted_close_price': r['predicted_close_price'],
                 'predicted_volume': r['predicted_volume'],
                 'prediction_reason': r['prediction_reason'],
                 'range': r['range']}
                for r in cursor.fetchall()
            ]

    def exists_prediction(self, predicted_date: str) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT COUNT(*) FROM t_stock_predict WHERE predicted_date = %s',
                (predicted_date,)
            )
            return cursor.fetchone()['count'] > 0
