from typing import List, Dict, Optional
from src.database.t_character_asset_manager import TCharacterAssetManager
from src.database.t_daily_result_manager import TDailyResultManager
from src.database.t_monthly_result_manager import TMonthlyResultManager
from src.database.t_investment_history_manager import TInvestmentHistoryManager
from src.characters import get_analysts
from src.characters.ichinose import IchinoseRitu

ALL_ANALYSTS = [a.name for a in get_analysts()] + [IchinoseRitu().name]


class StatsAggregator:
    def __init__(self):
        self.asset_manager = TCharacterAssetManager()
        self.daily_manager = TDailyResultManager()
        self.monthly_manager = TMonthlyResultManager()
        self.history_manager = TInvestmentHistoryManager()

    def get_ranking(self, year_month: str) -> List[Dict]:
        """現在の資産ランキングを返す"""
        return self.asset_manager.get_all_balances(year_month)

    def get_daily_summary(self, result_date: str) -> List[Dict]:
        return self.daily_manager.get_by_date(result_date)

    def finalize_month(self, year_month: str) -> None:
        """月末に月次成績を確定してDBに保存する"""
        balances = self.asset_manager.get_all_balances(year_month)
        if not balances:
            print(f"警告: {year_month} の資産データがありません")
            return

        # 月内の日次損益を集計
        for rank, b in enumerate(balances, start=1):
            analyst_name = b['analyst_name']
            profit_loss = b['current_balance'] - b['initial_balance']
            win, lose = self._count_wins(analyst_name, year_month)
            self.monthly_manager.upsert(
                year_month=year_month,
                analyst_name=analyst_name,
                total_profit_loss=profit_loss,
                final_balance=b['current_balance'],
                win_count=win,
                lose_count=lose,
                rank=rank,
                is_mvp=1 if rank == 1 else 0,
            )
            print(f"{rank}位 {analyst_name}: {b['current_balance']:,}円 ({profit_loss:+,}円)")

    def get_cumulative_mvp(self) -> List[Dict]:
        return self.monthly_manager.get_cumulative_mvp()

    def _count_wins(self, analyst_name: str, year_month: str) -> tuple:
        """月内の勝敗数を t_investment_history から集計する"""
        month_prefix = year_month  # YYYY-MM
        with self.history_manager._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT
                    SUM(CASE WHEN is_win = 1 THEN 1 ELSE 0 END),
                    SUM(CASE WHEN is_win = 0 THEN 1 ELSE 0 END)
                FROM t_investment_history
                WHERE analyst_name = ?
                  AND trade_date LIKE ?
                  AND sell_price IS NOT NULL
            ''', (analyst_name, f'{month_prefix}%'))
            row = cursor.fetchone()
            return (row[0] or 0, row[1] or 0)

    def get_win_rate_by_range(self, analyst_name: str) -> Dict[int, float]:
        """価格帯別の累計勝率を返す"""
        with self.history_manager._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT price_range,
                       COUNT(*) as total,
                       SUM(CASE WHEN is_win = 1 THEN 1 ELSE 0 END) as wins
                FROM t_investment_history
                WHERE analyst_name = ? AND sell_price IS NOT NULL
                GROUP BY price_range
            ''', (analyst_name,))
            result = {}
            for row in cursor.fetchall():
                price_range, total, wins = row
                result[price_range] = round(wins / total * 100, 1) if total else 0.0
            return result
