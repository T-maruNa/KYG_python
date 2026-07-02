from typing import List, Dict
from .db_manager import DBManager


class TDailyResultManager(DBManager):
    def __init__(self):
        super().__init__()

    def upsert(self, result_date: str, analyst_name: str, total_profit_loss: int,
               current_balance: int, win_count: int, lose_count: int) -> bool:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO t_daily_result
                        (result_date, analyst_name, total_profit_loss, current_balance,
                         win_count, lose_count)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (result_date, analyst_name) DO UPDATE SET
                        total_profit_loss = EXCLUDED.total_profit_loss,
                        current_balance   = EXCLUDED.current_balance,
                        win_count         = EXCLUDED.win_count,
                        lose_count        = EXCLUDED.lose_count
                ''', (result_date, analyst_name, total_profit_loss, current_balance,
                      win_count, lose_count))
                return True
        except Exception as e:
            print(f'日次結果保存エラー: {e}')
            return False

    def get_by_date(self, result_date: str) -> List[Dict]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT analyst_name, total_profit_loss, current_balance, win_count, lose_count
                FROM t_daily_result
                WHERE result_date = %s
                ORDER BY current_balance DESC
            ''', (result_date,))
            return [
                {'analyst_name': r['analyst_name'], 'total_profit_loss': r['total_profit_loss'],
                 'current_balance': r['current_balance'], 'win_count': r['win_count'],
                 'lose_count': r['lose_count']}
                for r in cursor.fetchall()
            ]

    def get_latest(self, before_date: str) -> List[Dict]:
        """指定日より前の直近営業日の結果を返す。前日データ表示用。"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT analyst_name, total_profit_loss, current_balance, win_count, lose_count
                FROM t_daily_result
                WHERE result_date < %s
                ORDER BY result_date DESC, current_balance DESC
                LIMIT 3
            ''', (before_date,))
            return [
                {'analyst_name': r['analyst_name'], 'total_profit_loss': r['total_profit_loss'],
                 'current_balance': r['current_balance'], 'win_count': r['win_count'],
                 'lose_count': r['lose_count']}
                for r in cursor.fetchall()
            ]

    def get_last_week_top(self, date_str: str) -> str:
        """
        指定日の前週（月〜土）で週間損益合計が最大のキャラ名を返す。
        日曜ナレーター決定用。データなし・同率はランダムで解決する。
        """
        import random
        from datetime import date as _date, timedelta
        try:
            d = _date.fromisoformat(date_str)
            # 前週の月曜〜土曜を算出（日曜=weekday 6 を基準に -6〜-1 日）
            last_sun = d - timedelta(days=d.weekday() + 1)  # 直前の土曜
            last_mon = last_sun - timedelta(days=5)          # その週の月曜
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT analyst_name, SUM(total_profit_loss) AS weekly_pl
                    FROM t_daily_result
                    WHERE result_date BETWEEN %s AND %s
                    GROUP BY analyst_name
                    ORDER BY weekly_pl DESC
                ''', (str(last_mon), str(last_sun)))
                rows = cursor.fetchall()
            if not rows:
                return random.choice(['rei', 'mirai', 'ritu'])
            top_pl = rows[0]['weekly_pl']
            # 同率1位は全員からランダム選択
            tops = [r['analyst_name'] for r in rows if r['weekly_pl'] == top_pl]
            return random.choice(tops)
        except Exception:
            return random.choice(['rei', 'mirai', 'ritu'])

    def get_weekly_summary(self, week_start: str, week_end: str) -> List[Dict]:
        """指定週の週間損益合計・勝利数をキャラごとに集計して返す（降順）。"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT analyst_name,
                       SUM(total_profit_loss) AS weekly_profit_loss,
                       SUM(win_count)         AS weekly_win_count,
                       MAX(current_balance)   AS current_balance
                FROM t_daily_result
                WHERE result_date BETWEEN %s AND %s
                GROUP BY analyst_name
                ORDER BY weekly_profit_loss DESC
            ''', (week_start, week_end))
            rows = cursor.fetchall()
        result = []
        for i, r in enumerate(rows):
            result.append({
                'rank':                i + 1,
                'analyst_name':        r['analyst_name'],
                'weekly_profit_loss':  r['weekly_profit_loss'],
                'weekly_win_count':    r['weekly_win_count'],
                'current_balance':     r['current_balance'],
            })
        return result

    def exists(self, result_date: str) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM t_daily_result WHERE result_date = %s', (result_date,))
            return cursor.fetchone()['count'] > 0
