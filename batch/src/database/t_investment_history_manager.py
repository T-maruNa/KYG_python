from typing import Optional, List, Dict
from .db_manager import DBManager


class TInvestmentHistoryManager(DBManager):
    def __init__(self):
        super().__init__()

    def insert_entry(self, trade_date: str, analyst_name: str, stock_code: str,
                     stock_name: str, price_range: int, buy_price: int, shares: int,
                     buy_amount: int, prediction_reason: str = '') -> bool:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO t_investment_history
                        (trade_date, analyst_name, stock_code, stock_name, price_range,
                         buy_price, shares, buy_amount, prediction_reason)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (trade_date, analyst_name, price_range) DO NOTHING
                ''', (trade_date, analyst_name, stock_code, stock_name, price_range,
                      buy_price, shares, buy_amount, prediction_reason))
                return cursor.rowcount > 0
        except Exception as e:
            print(f'エントリー登録エラー: {e}')
            return False

    def fill_result(self, trade_date: str, analyst_name: str, price_range: int,
                    sell_price: int) -> Optional[Dict]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT buy_price, shares FROM t_investment_history
                WHERE trade_date = %s AND analyst_name = %s
                  AND price_range = %s AND sell_price IS NULL
            ''', (trade_date, analyst_name, price_range))
            row = cursor.fetchone()
            if not row:
                return None
            buy_price, shares = row['buy_price'], row['shares']
            sell_amount = sell_price * shares
            buy_amount = buy_price * shares
            profit_loss = sell_amount - buy_amount
            profit_loss_rate = (sell_price - buy_price) / buy_price * 100
            is_win = 1 if sell_price > buy_price else 0

            cursor.execute('''
                UPDATE t_investment_history
                SET sell_price = %s, sell_amount = %s, profit_loss = %s,
                    profit_loss_rate = %s, is_win = %s, update_date = CURRENT_TIMESTAMP
                WHERE trade_date = %s AND analyst_name = %s AND price_range = %s
            ''', (sell_price, sell_amount, profit_loss, profit_loss_rate, is_win,
                  trade_date, analyst_name, price_range))
            return {'profit_loss': profit_loss, 'profit_loss_rate': profit_loss_rate, 'is_win': is_win}

    def get_pending(self, trade_date: str) -> List[Dict]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT analyst_name, stock_code, stock_name, price_range, buy_price, shares
                FROM t_investment_history
                WHERE trade_date = %s AND sell_price IS NULL
            ''', (trade_date,))
            return [
                {'analyst_name': r['analyst_name'], 'stock_code': r['stock_code'],
                 'stock_name': r['stock_name'], 'price_range': r['price_range'],
                 'buy_price': r['buy_price'], 'shares': r['shares']}
                for r in cursor.fetchall()
            ]

    def get_by_date(self, trade_date: str, analyst_name: str = None) -> List[Dict]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if analyst_name:
                cursor.execute('''
                    SELECT * FROM t_investment_history
                    WHERE trade_date = %s AND analyst_name = %s
                    ORDER BY price_range
                ''', (trade_date, analyst_name))
            else:
                cursor.execute('''
                    SELECT * FROM t_investment_history
                    WHERE trade_date = %s
                    ORDER BY analyst_name, price_range
                ''', (trade_date,))
            return [dict(r) for r in cursor.fetchall()]

    def exists_entry(self, trade_date: str, analyst_name: str) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT COUNT(*) FROM t_investment_history
                WHERE trade_date = %s AND analyst_name = %s
            ''', (trade_date, analyst_name))
            return cursor.fetchone()['count'] > 0
