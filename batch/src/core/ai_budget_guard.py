"""
AI API呼び出しのリトライ制御・日次上限・月次予算ガード。

使い方:
    guard = AIBudgetGuard()
    result = guard.execute(client.execute_chat, messages, call_type='prediction', model='gemini')
"""
import time
from datetime import date
from typing import Callable, Any, Optional

from config.config import config
from src.database.t_ai_call_log_manager import TAiCallLogManager


class BudgetExceededError(Exception):
    pass


class AIBudgetGuard:
    def __init__(self):
        self.log_manager = TAiCallLogManager()

    def execute(self, func: Callable, *args,
                call_type: str = 'unknown', model: str = 'unknown',
                **kwargs) -> Optional[Any]:
        """
        func を呼び出す。
        - 日次上限チェック → 超えたら None を返す
        - 月次予算チェック → 超えたら None を返す
        - 失敗時は AI_RETRY_LIMIT 回までリトライ
        """
        today = date.today().strftime('%Y-%m-%d')
        year_month = date.today().strftime('%Y-%m')

        # 日次上限チェック
        daily_count = self.log_manager.count_today(today)
        if daily_count >= config.DAILY_AI_CALL_LIMIT:
            print(f'[予算ガード] 日次上限到達 ({daily_count}/{config.DAILY_AI_CALL_LIMIT}回)。スキップします。')
            return None

        # 月次予算チェック
        monthly_cost = self.log_manager.monthly_cost(year_month)
        if monthly_cost >= config.MONTHLY_AI_BUDGET_JPY:
            print(
                f'[予算ガード] 月次予算上限到達 ({monthly_cost:.0f}/{config.MONTHLY_AI_BUDGET_JPY}円)。'
                f'スキップします。'
            )
            return None

        # 実行（リトライ付き）
        last_error = None
        for attempt in range(1, config.AI_RETRY_LIMIT + 2):  # +2 = 初回 + リトライ回数
            try:
                result = func(*args, **kwargs)
                self.log_manager.log(
                    call_date=today,
                    call_type=call_type,
                    model=model,
                    estimated_cost_jpy=config.ESTIMATED_COST_PER_CALL_JPY,
                    success=True,
                )
                return result
            except Exception as e:
                last_error = e
                if attempt <= config.AI_RETRY_LIMIT:
                    wait = 2 ** attempt
                    print(f'[予算ガード] {call_type} 失敗 (試行{attempt}/{config.AI_RETRY_LIMIT + 1}): {e} — {wait}秒後リトライ')
                    time.sleep(wait)
                else:
                    print(f'[予算ガード] {call_type} リトライ上限到達: {e}')

        self.log_manager.log(
            call_date=today,
            call_type=call_type,
            model=model,
            estimated_cost_jpy=0,
            success=False,
        )
        return None

    def remaining_calls_today(self) -> int:
        today = date.today().strftime('%Y-%m-%d')
        used = self.log_manager.count_today(today)
        return max(0, config.DAILY_AI_CALL_LIMIT - used)

    def remaining_budget_this_month(self) -> float:
        year_month = date.today().strftime('%Y-%m')
        used = self.log_manager.monthly_cost(year_month)
        return max(0.0, config.MONTHLY_AI_BUDGET_JPY - used)
