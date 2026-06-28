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

    def generate_daily(self, result_date: str, trade_date: str, year_month: str,
                       ranking: List[Dict] = None) -> str:
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

        ranking_by_analyst = {}
        if ranking:
            total = len(ranking)
            first_balance = ranking[0]['current_balance'] if ranking else 0
            for i, r in enumerate(ranking):
                ranking_by_analyst[r['analyst_name']] = {
                    'rank': i + 1,
                    'total': total,
                    'gap_from_first': first_balance - r['current_balance'],
                }

        sections = [
            self._section_result(result_date, daily, prev_entries, ranking_by_analyst),
            self._section_ranking(ranking or [], year_month),
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
                        entries: List[Dict], ranking_by_analyst: Dict = None) -> str:
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
            ri = (ranking_by_analyst or {}).get(name)
            comment = self._character_comment(name, profile['personality'], profit, win, lose, ri)

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
        total = len(ranking)
        first_balance = ranking[0]['current_balance'] if ranking else 0
        for i, r in enumerate(ranking):
            name = r['analyst_name']
            profile = ANALYST_PROFILES.get(name, {'name_jp': name, 'personality': ''})
            diff = r['current_balance'] - r['initial_balance']
            sign = '+' if diff >= 0 else ''
            html += (
                f'  <li>{profile["name_jp"]}: {r["current_balance"]:,}円 '
                f'({sign}{diff:,}円)</li>\n'
            )
        html += '</ol>\n'

        for i, r in enumerate(ranking):
            name = r['analyst_name']
            profile = ANALYST_PROFILES.get(name, {'name_jp': name, 'personality': ''})
            gap = first_balance - r['current_balance']
            rank_info = {'rank': i + 1, 'total': total, 'gap_from_first': gap}
            comment = self._ranking_comment(name, profile['personality'], i + 1, total, gap)
            html += f'<p><strong>{profile["name_jp"]}</strong>：{comment}</p>\n'

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
            total = 0
            for e in ae:
                approx_man = round(e.get("buy_amount", 0) / 10000)
                total += e.get("buy_amount", 0)
                html += (
                    f'<tr><td>{e["stock_code"]}</td>'
                    f'<td>{e["stock_name"]}</td>'
                    f'<td>約{approx_man}万円</td>'
                    f'<td>{e.get("prediction_reason", "")}</td></tr>\n'
                )
            html += f'</table>\n<p>合計　約{round(total / 10000)}万円</p>\n'

            stock_names = [e['stock_name'] for e in ae]
            comment = self._entry_comment(analyst_name, profile['personality'], stock_names)
            html += f'<blockquote>{comment}</blockquote>\n'

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
                WHERE trade_date LIKE %s AND sell_price IS NOT NULL AND profit_loss IS NOT NULL
                ORDER BY profit_loss DESC
                LIMIT 1
            ''', (f'{year_month}%',))
            best = cursor.fetchone()

            cursor.execute('''
                SELECT stock_code, stock_name, analyst_name, profit_loss, profit_loss_rate
                FROM t_investment_history
                WHERE trade_date LIKE %s AND sell_price IS NOT NULL AND profit_loss IS NOT NULL
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
                           profit: int, win: int, lose: int,
                           ranking_info: Dict = None) -> str:
        sign = '+' if profit >= 0 else ''
        try:
            profile = ANALYST_PROFILES.get(analyst_name, {'name_jp': analyst_name})

            rank_context = ''
            if ranking_info:
                rank = ranking_info.get('rank', 1)
                total = ranking_info.get('total', 1)
                gap = ranking_info.get('gap_from_first', 0)
                if rank == 1:
                    rank_context = f'現在ランキング1位です。'
                else:
                    rank_context = f'現在ランキング{rank}位（1位との差：{gap:,}円）です。'

            messages = [
                {'role': 'system',
                 'content': f'あなたは{profile["name_jp"]}です。{personality}'},
                {'role': 'user',
                 'content': (
                     f'今日の投資結果は{sign}{profit:,}円（{win}勝{lose}敗）でした。'
                     f'{rank_context}'
                     f'キャラクターらしい短いコメントを1〜2文で返してください。'
                     f'順位についても触れてください。'
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

    def _ranking_comment(self, analyst_name: str, personality: str,
                         rank: int, total: int, gap_from_first: int) -> str:
        try:
            profile = ANALYST_PROFILES.get(analyst_name, {'name_jp': analyst_name})
            if rank == 1:
                rank_context = f'現在{total}人中1位です。'
            else:
                rank_context = f'現在{total}人中{rank}位で、1位との差は{gap_from_first:,}円です。'
            messages = [
                {'role': 'system',
                 'content': f'あなたは{profile["name_jp"]}です。{personality}'},
                {'role': 'user',
                 'content': (
                     f'{rank_context}'
                     f'現在の順位についてキャラクターらしい一言コメントを1文で返してください。'
                     f'投資助言・断言表現は避けてください。'
                 )},
            ]
            result = self.guard.execute(
                self.gemini.execute_chat, messages,
                call_type='ranking_comment', model='gemini',
            )
            return result.strip() if result else rank_context
        except Exception:
            return f'{rank}位です。'

    def _entry_comment(self, analyst_name: str, personality: str,
                       stock_names: List[str]) -> str:
        try:
            profile = ANALYST_PROFILES.get(analyst_name, {'name_jp': analyst_name})
            stocks_str = '、'.join(stock_names)
            messages = [
                {'role': 'system',
                 'content': f'あなたは{profile["name_jp"]}です。{personality}'},
                {'role': 'user',
                 'content': (
                     f'今日のエントリー銘柄は{stocks_str}です。'
                     f'選んだ理由や意気込みをキャラクターらしく1〜2文で話してください。'
                     f'投資助言・断言表現は避けてください。'
                 )},
            ]
            result = self.guard.execute(
                self.gemini.execute_chat, messages,
                call_type='entry_comment', model='gemini',
            )
            return result.strip() if result else f'今日は{stocks_str}に注目しています。'
        except Exception:
            return f'今日の注目銘柄は{", ".join(stock_names)}です。'
