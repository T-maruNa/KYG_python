import os
from typing import List, Dict, Optional
from src.database.t_daily_result_manager import TDailyResultManager
from src.database.t_investment_history_manager import TInvestmentHistoryManager
from src.database.t_monthly_result_manager import TMonthlyResultManager
from src.database.t_character_asset_manager import TCharacterAssetManager
from src.core.stats_aggregator import StatsAggregator
from src.ai_clients.gemini_client import GeminiClient
from src.core.ai_budget_guard import AIBudgetGuard

ANALYST_PROFILES = {
    'rei': {
        'name_jp': '鷲見 玲',
        'personality': '落ち着いたテクニカル分析派の女性。敬語で話す。冷静だがたまにドヤる。',
    },
    'mirai': {
        'name_jp': '桜庭 みらい',
        'personality': '明るくポジティブな女性。話題性・雰囲気重視。カフェが好き。',
    },
    'ritu': {
        'name_jp': '一ノ瀬 律',
        'personality': '豪快な金髪ギャル。敬語は使わない。勘で投資する。結果は二の次。',
    },
}

FORBIDDEN_PHRASES = [
    '絶対', '確実', '必ず上がる', '買うべき', '儲かる', '保証', '推奨銘柄',
]

DISCLAIMER = (
    '<p style="font-size:0.85em;color:#888;border-top:1px solid #ddd;'
    'padding-top:1em;margin-top:2em;">'
    'この記事はAIキャラクターによる仮想投資シミュレーションです。<br>'
    '実際の売買を推奨するものではありません。<br>'
    '投資判断はご自身の責任で行ってください。'
    '</p>'
)

# プロジェクトルート（batch/）からの相対パス
_ASSET_BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), '..', 'assets', 'characters')


def _image_url(analyst_name: str, expression: str) -> str:
    """表情差分があればそのパス、なければ基本画像パスを返す"""
    variant = os.path.join(_ASSET_BASE, analyst_name, f'{expression}.png')
    if os.path.exists(variant):
        return f'assets/characters/{analyst_name}/{expression}.png'
    return f'assets/characters/{analyst_name}.png'


def get_expression(profit_loss_rate: float, is_mvp: bool = False) -> str:
    if is_mvp:
        return 'victory'
    if profit_loss_rate >= 5:
        return 'victory'
    if profit_loss_rate >= 0:
        return 'happy'
    if profit_loss_rate >= -5:
        return 'worried'
    return 'defeated'


class BlogGenerator:
    def __init__(self):
        self.daily_manager = TDailyResultManager()
        self.history_manager = TInvestmentHistoryManager()
        self.monthly_manager = TMonthlyResultManager()
        self.asset_manager = TCharacterAssetManager()
        self.stats = StatsAggregator()
        self.gemini = GeminiClient()
        self.guard = AIBudgetGuard()

    # ------------------------------------------------------------------
    # 日次記事
    # ------------------------------------------------------------------

    def generate_daily(self, result_date: str, trade_date: str, year_month: str) -> str:
        """
        result_date: 結果確定日（前営業日の実価格が確定した日）
        trade_date:  本日のエントリー対象日（次営業日）
        year_month:  YYYY-MM
        """
        daily = self.daily_manager.get_by_date(result_date)
        ranking = self.stats.get_ranking(year_month)
        prev_entries = self.history_manager.get_by_date(result_date)
        today_entries = self.history_manager.get_by_date(trade_date)
        cumulative_mvp = self.monthly_manager.get_cumulative_mvp()

        sections = [
            self._section_result(result_date, daily, prev_entries),
            self._section_ranking(ranking, year_month),
            self._section_today_entry(trade_date, today_entries),
            self._section_cumulative(cumulative_mvp),
            DISCLAIMER,
        ]
        return '\n'.join(sections)

    # ------------------------------------------------------------------
    # 月次まとめ記事
    # ------------------------------------------------------------------

    def generate_monthly(self, year_month: str) -> str:
        monthly = self.monthly_manager.get_by_month(year_month)
        cumulative_mvp = self.monthly_manager.get_cumulative_mvp()

        if not monthly:
            return ''

        sections = [
            f'<h1>{year_month} 月間まとめ</h1>',
            self._section_monthly_ranking(monthly, year_month),
            self._section_monthly_best_worst(year_month),
            self._section_cumulative(cumulative_mvp),
            DISCLAIMER,
        ]
        return '\n'.join(sections)

    # ------------------------------------------------------------------
    # 投稿前チェック
    # ------------------------------------------------------------------

    def check(self, content: str, entries: List[Dict]) -> List[str]:
        errors = []
        for phrase in FORBIDDEN_PHRASES:
            if phrase in content:
                errors.append(f'禁止表現: {phrase}')
        if '仮想投資シミュレーション' not in content:
            errors.append('免責文なし')
        if not content.strip():
            errors.append('本文が空')
        for e in entries:
            if not e.get('stock_code', '').strip():
                errors.append(f'銘柄コードが空: {e}')
            if not e.get('stock_name', '').strip():
                errors.append(f'銘柄名が空: {e}')
        return errors

    # ------------------------------------------------------------------
    # 内部セクション
    # ------------------------------------------------------------------

    def _section_result(self, result_date: str, daily: List[Dict],
                        entries: List[Dict]) -> str:
        if not daily:
            return f'<h2>{result_date} の結果</h2><p>データがありません。</p>'

        html = f'<h2>{result_date} の結果発表</h2>\n'
        for d in daily:
            name = d['analyst_name']
            profile = ANALYST_PROFILES.get(name, {'name_jp': name, 'personality': ''})
            profit = d['total_profit_loss']
            balance = d['current_balance']
            win = d['win_count']
            lose = d['lose_count']
            sign = '+' if profit >= 0 else ''

            pl_rates = [
                e['profit_loss_rate'] for e in entries
                if e.get('analyst_name') == name and e.get('profit_loss_rate') is not None
            ]
            avg_rate = sum(pl_rates) / len(pl_rates) if pl_rates else 0
            expression = get_expression(avg_rate)
            img = _image_url(name, expression)
            comment = self._character_comment(name, profile['personality'], profit, win, lose)

            html += (
                f'<div class="character-result">\n'
                f'  <h3>{profile["name_jp"]}</h3>\n'
                f'  <img src="{img}" alt="{profile["name_jp"]}" style="max-width:200px;">\n'
                f'  <p>損益: <strong>{sign}{profit:,}円</strong>（{win}勝{lose}敗）'
                f'　残高: {balance:,}円</p>\n'
                f'  <blockquote>{comment}</blockquote>\n'
                f'</div>\n'
            )
        return html

    def _section_ranking(self, ranking: List[Dict], year_month: str) -> str:
        html = f'<h2>{year_month} 現在資産ランキング</h2>\n<ol>\n'
        for r in ranking:
            name = r['analyst_name']
            profile = ANALYST_PROFILES.get(name, {'name_jp': name})
            diff = r['current_balance'] - r['initial_balance']
            sign = '+' if diff >= 0 else ''
            html += (
                f'  <li>{profile["name_jp"]}: {r["current_balance"]:,}円 '
                f'({sign}{diff:,}円)</li>\n'
            )
        html += '</ol>\n'
        return html

    def _section_today_entry(self, trade_date: str, entries: List[Dict]) -> str:
        if not entries:
            return f'<h2>{trade_date} のエントリー</h2><p>エントリーなし</p>'

        html = f'<h2>{trade_date} のエントリー銘柄</h2>\n'
        for analyst_name, profile in ANALYST_PROFILES.items():
            ae = [e for e in entries if e.get('analyst_name') == analyst_name]
            if not ae:
                continue
            html += (
                f'<h3>{profile["name_jp"]}</h3>\n'
                f'<table><tr><th>銘柄コード</th><th>銘柄名</th><th>購入金額</th><th>予想理由</th></tr>\n'
            )
            for e in ae:
                approx_man = round(e.get("buy_amount", 0) / 10000)
                html += (
                    f'<tr><td>{e["stock_code"]}</td>'
                    f'<td>{e["stock_name"]}</td>'
                    f'<td>約{approx_man}万円</td>'
                    f'<td>{e.get("prediction_reason", "")}</td></tr>\n'
                )
            html += '</table>\n'
        return html

    def _section_cumulative(self, cumulative_mvp: List[Dict]) -> str:
        if not cumulative_mvp:
            return ''
        html = '<h2>累計MVP記録</h2>\n<ol>\n'
        for r in cumulative_mvp:
            name = r['analyst_name']
            profile = ANALYST_PROFILES.get(name, {'name_jp': name})
            html += (
                f'  <li>{profile["name_jp"]}: MVP {r["mvp_count"]}回 / '
                f'月間優勝 {r["win_count"]}回 / '
                f'累計損益 {r["cumulative_profit_loss"]:+,}円</li>\n'
            )
        html += '</ol>\n'
        return html

    def _section_monthly_ranking(self, monthly: List[Dict], year_month: str) -> str:
        html = f'<h2>{year_month} 月間ランキング</h2>\n<ol>\n'
        for r in monthly:
            name = r['analyst_name']
            profile = ANALYST_PROFILES.get(name, {'name_jp': name})
            mvp_mark = ' 👑MVP' if r['is_mvp'] else ''
            win_rate = (
                round(r['win_count'] / (r['win_count'] + r['lose_count']) * 100, 1)
                if (r['win_count'] + r['lose_count']) > 0 else 0
            )
            html += (
                f'  <li>{r["rank"]}位 {profile["name_jp"]}{mvp_mark}: '
                f'{r["final_balance"]:,}円 ({r["total_profit_loss"]:+,}円) '
                f'勝率{win_rate}%</li>\n'
            )
        html += '</ol>\n'
        return html

    def _section_monthly_best_worst(self, year_month: str) -> str:
        """月内の最大勝ち/最大負け銘柄"""
        with self.history_manager._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT stock_code, stock_name, analyst_name, profit_loss, profit_loss_rate
                FROM t_investment_history
                WHERE trade_date LIKE ? AND sell_price IS NOT NULL AND profit_loss IS NOT NULL
                ORDER BY profit_loss DESC
                LIMIT 1
            ''', (f'{year_month}%',))
            best = cursor.fetchone()

            cursor.execute('''
                SELECT stock_code, stock_name, analyst_name, profit_loss, profit_loss_rate
                FROM t_investment_history
                WHERE trade_date LIKE ? AND sell_price IS NOT NULL AND profit_loss IS NOT NULL
                ORDER BY profit_loss ASC
                LIMIT 1
            ''', (f'{year_month}%',))
            worst = cursor.fetchone()

        html = '<h2>月間トピックス</h2>\n'
        if best:
            profile = ANALYST_PROFILES.get(best[2], {'name_jp': best[2]})
            html += (
                f'<p>最大利益: {best[1]}（{best[0]}）'
                f' {best[3]:+,}円 ({best[4]:+.1f}%) — {profile["name_jp"]}</p>\n'
            )
        if worst:
            profile = ANALYST_PROFILES.get(worst[2], {'name_jp': worst[2]})
            html += (
                f'<p>最大損失: {worst[1]}（{worst[0]}）'
                f' {worst[3]:+,}円 ({worst[4]:+.1f}%) — {profile["name_jp"]}</p>\n'
            )
        return html

    def _character_comment(self, analyst_name: str, personality: str,
                           profit: int, win: int, lose: int) -> str:
        sign = '+' if profit >= 0 else ''
        try:
            profile = ANALYST_PROFILES.get(analyst_name, {'name_jp': analyst_name})
            messages = [
                {'role': 'system',
                 'content': f'あなたは{profile["name_jp"]}です。{personality}'},
                {'role': 'user',
                 'content': (
                     f'今日の投資結果は{sign}{profit:,}円（{win}勝{lose}敗）でした。'
                     f'キャラクターらしい短いコメントを1〜2文で返してください。'
                     f'投資助言・断言表現は避けてください。'
                 )},
            ]
            result = self.guard.execute(
                self.gemini.execute_chat, messages,
                call_type='character_comment', model='gemini',
            )
            return result.strip() if result else f'今日は{sign}{profit:,}円でした。'
        except Exception:
            return f'今日は{sign}{profit:,}円でした。'
