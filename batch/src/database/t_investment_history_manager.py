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
                    INSERT OR IGNORE INTO t_investment_history
                        (trade_date, analyst_name, stock_code, stock_name, price_range,
                         buy_price, shares, buy_amount, prediction_reason)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (trade_date, analyst_name, stock_code, stock_name, price_range,
                      buy_price, shares, buy_amount, prediction_reason))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            print(f"エントリー登録エラー: {e}")
            return False

    def fill_result(self, trade_date: str, analyst_name: str, price_range: int,
                    sell_price: int) -> Optional[Dict]:
        """売値を記録し損益を計算して返す"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT buy_price, shares FROM t_investment_history
                WHERE trade_date = ? AND analyst_name = ? AND price_range = ? AND sell_price IS NULL
            ''', (trade_date, analyst_name, price_range))
            row = cursor.fetchone()
            if not row:
                return None
            buy_price, shares = row
            sell_amount = sell_price * shares
            buy_amount = buy_price * shares
            profit_loss = sell_amount - buy_amount
            profit_loss_rate = (sell_price - buy_price) / buy_price * 100
            is_win = 1 if sell_price > buy_price else 0

            cursor.execute('''
                UPDATE t_investment_history
                SET sell_price = ?, sell_amount = ?, profit_loss = ?,
                    profit_loss_rate = ?, is_win = ?, update_date = CURRENT_TIMESTAMP
                WHERE trade_date = ? AND analyst_name = ? AND price_range = ?
            ''', (sell_price, sell_amount, profit_loss, profit_loss_rate, is_win,
                  trade_date, analyst_name, price_range))
            conn.commit()
            return {
                'profit_loss': profit_loss,
                'profit_loss_rate': profit_loss_rate,
                'is_win': is_win,
                'stock_code': None,
            }

    def get_pending(self, trade_date: str) -> List[Dict]:
        """売値未確定のエントリーを取得する"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT analyst_name, stock_code, stock_name, price_range, buy_price, shares
                FROM t_investment_history
                WHERE trade_date = ? AND sell_price IS NULL
            ''', (trade_date,))
            return [
                {'analyst_name': r[0], 'stock_code': r[1], 'stock_name': r[2],
                 'price_range': r[3], 'buy_price': r[4], 'shares': r[5]}
                for r in cursor.fetchall()
            ]

    def get_by_date(self, trade_date: str, analyst_name: str = None) -> List[Dict]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if analyst_name:
                cursor.execute('''
                    SELECT * FROM t_investment_history
                    WHERE trade_date = ? AND analyst_name = ?
                    ORDER BY price_range
                ''', (trade_date, analyst_name))
            else:
                cursor.execute('''
                    SELECT * FROM t_investment_history
                    WHERE trade_date = ?
                    ORDER BY analyst_name, price_range
                ''', (trade_date,))
            cols = [d[0] for d in cursor.description]
            return [dict(zip(cols, row)) for row in cursor.fetchall()]

    def exists_entry(self, trade_date: str, analyst_name: str) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT COUNT(*) FROM t_investment_history
                WHERE trade_date = ? AND analyst_name = ?
            ''', (trade_date, analyst_name))
            return cursor.fetchone()[0] > 0
