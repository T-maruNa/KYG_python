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
        'role': 'テクニカル担当',
        'personality': '落ち着いたテクニカル分析派の女性。敬語で話す。冷静だがたまにドヤる。',
    },
    'mirai': {
        'name_jp': '桜庭 みらい',
        'role': 'ファンダメンタル担当',
        'personality': '明るくポジティブな女性。話題性・雰囲気重視。カフェが好き。',
    },
    'ritu': {
        'name_jp': '一ノ瀬 律',
        'role': '直感担当',
        'personality': '豪快な金髪ギャル。敬語は使わない。勘で投資する。結果は二の次。',
    },
}

FORBIDDEN_PHRASES = [
    '絶対', '確実', '必ず上がる', '買うべき', '儲かる', '保証', '推奨銘柄',
]

DISCLAIMER = (
    '<div class="disclaimer-box">'
    'この記事はAIキャラクターによる仮想投資シミュレーションです。<br>'
    '実際の売買を推奨するものではありません。<br>'
    '投資判断はご自身の責任で行ってください。'
    '</div>'
)

BATTLE_CSS = '''<style>
.battle-article{max-width:860px;margin:0 auto;color:#3f3446;line-height:1.8;font-family:sans-serif;}
.battle-hero{background:linear-gradient(135deg,#fff7fb,#f3f8ff);border:1px solid #f0ddea;border-radius:28px;padding:28px 24px;margin-bottom:28px;box-shadow:0 10px 30px rgba(120,80,120,.08);}
.battle-label{display:inline-block;font-size:.82rem;letter-spacing:.08em;color:#9b6b88;background:rgba(255,255,255,.8);border-radius:999px;padding:4px 12px;margin-bottom:8px;}
.battle-lead{margin:.4em 0 0;color:#7a6b80;font-size:.95rem;}
.battle-article h1{color:#4b3b57;margin:.2em 0;}
.battle-article h2{color:#4b3b57;border-bottom:none;margin-top:2.2em;padding-left:.2em;}
.battle-article h2::before{content:"✦ ";color:#e6a6c8;}
.battle-article h3{color:#4b3b57;margin:.6em 0 .3em;}
.sim-notice{font-size:.9em;color:#666;background:#f9f9f9;border-left:4px solid #e6a6c8;padding:.6em 1em;border-radius:0 8px 8px 0;margin-bottom:1.5em;}
.character-card{border-radius:24px;padding:20px;margin:18px 0;box-shadow:0 10px 28px rgba(80,60,90,.08);border:1px solid rgba(255,255,255,.9);}
.character-rei{background:#f1f7ff;}
.character-mirai{background:#fff3f7;}
.character-ritu{background:#fffde8;}
.character-header{display:flex;gap:14px;align-items:center;margin-bottom:12px;}
.character-avatar{width:92px;height:92px;border-radius:50%;background:rgba(255,255,255,.75);display:flex;align-items:center;justify-content:center;overflow:hidden;border:3px solid rgba(255,255,255,.9);flex-shrink:0;}
.character-avatar img{width:100%;height:100%;object-fit:cover;}
.character-avatar-placeholder{width:100%;height:100%;display:flex;flex-direction:column;align-items:center;justify-content:center;font-size:.65rem;color:#999;text-align:center;padding:4px;}
.character-role{margin:0;font-size:.88rem;color:#7a6b80;}
.result-score{font-size:1.9rem;font-weight:800;margin:10px 0 2px;}
.result-score.plus{color:#d85f8b;}
.result-score.minus{color:#5c7fc4;}
.result-meta{margin:0 0 12px;color:#6f6372;font-size:.92rem;}
.character-balloon{position:relative;background:rgba(255,255,255,.88);border-radius:18px;padding:14px 16px;margin-top:10px;font-size:.95rem;}
.ranking-card{display:flex;align-items:center;gap:12px;background:#fff;border-radius:18px;padding:12px 14px;margin:10px 0;box-shadow:0 6px 18px rgba(80,60,90,.06);}
.rank-badge{width:38px;height:38px;border-radius:50%;display:inline-flex;align-items:center;justify-content:center;font-weight:800;font-size:1.1rem;flex-shrink:0;}
.rank-badge-1{background:#ffe8a3;}
.rank-badge-2{background:#e8e8e8;}
.rank-badge-3{background:#f4d9c6;}
.rank-badge-n{background:#f0eef4;font-size:.9rem;}
.ranking-inline{display:flex;align-items:flex-start;gap:10px;margin:10px 0;}
.ranking-inline .character-avatar{width:56px;height:56px;}
.character-inline{display:flex;align-items:flex-start;gap:10px;margin:10px 0;}
.character-inline .character-avatar{width:56px;height:56px;}
.battle-table{width:100%;border-collapse:separate;border-spacing:0;overflow:hidden;border-radius:18px;background:#fff;box-shadow:0 8px 22px rgba(80,60,90,.06);margin:.8em 0;}
.battle-table th{background:#f6e8f0;color:#5f4a62;padding:10px 12px;text-align:left;}
.battle-table td{border:none;border-top:1px solid #f0e7ee;padding:10px 12px;}
.entry-total{text-align:right;font-size:.88rem;color:#9b6b88;margin:.2em 0 .8em;}
.cumulative-card{background:#fff;border-radius:18px;padding:14px 18px;margin:8px 0;box-shadow:0 4px 14px rgba(80,60,90,.06);display:flex;align-items:center;gap:10px;}
.mvp-count{font-size:.85rem;color:#7a6b80;}
.disclaimer-box{font-size:.86rem;color:#7a7280;background:#fafafa;border-radius:16px;padding:14px 16px;margin-top:32px;border:1px solid #eee;}
@media(max-width:640px){
  .battle-hero{padding:20px 16px;border-radius:20px;}
  .character-card{padding:16px;}
  .character-avatar{width:74px;height:74px;}
  .result-score{font-size:1.5rem;}
  .battle-table{display:block;overflow-x:auto;}
  .ranking-card{padding:10px 12px;}
}
</style>'''

# プロジェクトルート（batch/）からの相対パス
_ASSET_BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), '..', 'assets', 'characters')


def _image_url(analyst_name: str, expression: str) -> str:
    """表情差分があればそのパス、なければ基本画像パスを返す"""
    variant = os.path.join(_ASSET_BASE, analyst_name, f'{expression}.png')
    if os.path.exists(variant):
        return f'assets/characters/{analyst_name}/{expression}.png'
    return f'assets/characters/{analyst_name}.png'


def _avatar_html(analyst_name: str, expression: str, size: str = '') -> str:
    """アバター div を返す。画像ファイルがなければプレースホルダー表示"""
    style = f' style="width:{size};height:{size};"' if size else ''
    img_path = _image_url(analyst_name, expression)
    profile = ANALYST_PROFILES.get(analyst_name, {'name_jp': analyst_name})
    # ファイルが実際に存在するか確認
    variant = os.path.join(_ASSET_BASE, analyst_name, f'{expression}.png')
    base = os.path.join(_ASSET_BASE, f'{analyst_name}.png')
    has_image = os.path.exists(variant) or os.path.exists(base)

    inner = (
        f'<img src="{img_path}" alt="{profile["name_jp"]}">'
        if has_image else
        f'<div class="character-avatar-placeholder">🖼️<br>{profile["name_jp"]}<br>'
        f'<span style="font-size:.6rem;">※結果により変動</span></div>'
    )
    return f'<div class="character-avatar"{style}>{inner}</div>'


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


_RANK_BADGE_CLASS = {1: 'rank-badge-1', 2: 'rank-badge-2', 3: 'rank-badge-3'}
_RANK_MEDAL = {1: '🥇', 2: '🥈', 3: '🥉'}


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

        hero = (
            f'<div class="battle-hero">'
            f'<p class="battle-label">AI Virtual Investment Battle</p>'
            f'<h1>【AI投資バトル】{trade_date} 今日の結果発表</h1>'
            f'<p class="battle-lead">3人のAIキャラクターが、今日もシミュレーションで投資バトル。</p>'
            f'</div>'
        )
        notice = (
            '<p class="sim-notice">この記事は、AIキャラクターによる投資シミュレーション企画です。'
            '実際の売買を行ったものではありません。</p>'
        )

        sections = [
            BATTLE_CSS,
            '<section class="battle-article">',
            hero,
            notice,
            self._section_result(result_date, daily, prev_entries, ranking_by_analyst),
            self._section_ranking(ranking or [], year_month),
            self._section_today_entry(trade_date, today_entries),
            self._section_cumulative(cumulative_mvp),
            DISCLAIMER,
            '</section>',
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

        hero = (
            f'<div class="battle-hero">'
            f'<p class="battle-label">AI Virtual Investment Battle</p>'
            f'<h1>【AI投資バトル】{year_month} 月間まとめ</h1>'
            f'<p class="battle-lead">今月のシミュレーション投資バトル、最終結果を振り返ります。</p>'
            f'</div>'
        )
        sections = [
            BATTLE_CSS,
            '<section class="battle-article">',
            hero,
            self._section_monthly_ranking(monthly, year_month),
            self._section_monthly_best_worst(year_month),
            self._section_cumulative(cumulative_mvp),
            DISCLAIMER,
            '</section>',
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
            return f'<h2>{result_date} 今日の成績</h2><p>データがありません。</p>'

        html = f'<h2>今日の成績 <span style="font-size:.8em;font-weight:normal;">{result_date}</span></h2>\n'
        for d in daily:
            name = d['analyst_name']
            profile = ANALYST_PROFILES.get(name, {'name_jp': name, 'personality': '', 'role': ''})
            profit = d['total_profit_loss']
            balance = d['current_balance']
            win = d['win_count']
            lose = d['lose_count']
            sign = '+' if profit >= 0 else ''
            score_class = 'plus' if profit >= 0 else 'minus'

            pl_rates = [
                e['profit_loss_rate'] for e in entries
                if e.get('analyst_name') == name and e.get('profit_loss_rate') is not None
            ]
            avg_rate = sum(pl_rates) / len(pl_rates) if pl_rates else 0
            expression = get_expression(avg_rate)
            ri = (ranking_by_analyst or {}).get(name)
            comment = self._character_comment(name, profile['personality'], profit, win, lose, ri)

            html += (
                f'<div class="character-card character-{name}">\n'
                f'  <div class="character-header">\n'
                f'    {_avatar_html(name, expression)}\n'
                f'    <div>\n'
                f'      <h3 style="margin:0 0 2px;">{profile["name_jp"]}</h3>\n'
                f'      <p class="character-role">{profile.get("role", "")}</p>\n'
                f'    </div>\n'
                f'  </div>\n'
                f'  <div class="result-score {score_class}">{sign}{profit:,}円</div>\n'
                f'  <p class="result-meta">{win}勝{lose}敗 / 現在資産 {balance:,}円</p>\n'
                f'  <div class="character-balloon">{comment}</div>\n'
                f'</div>\n'
            )
        return html

    def _section_ranking(self, ranking: List[Dict], year_month: str) -> str:
        html = f'<h2>今月の資産ランキング</h2>\n'
        total = len(ranking)
        first_balance = ranking[0]['current_balance'] if ranking else 0

        for i, r in enumerate(ranking):
            name = r['analyst_name']
            profile = ANALYST_PROFILES.get(name, {'name_jp': name, 'personality': ''})
            diff = r['current_balance'] - r['initial_balance']
            sign = '+' if diff >= 0 else ''
            rank = i + 1
            badge_class = _RANK_BADGE_CLASS.get(rank, 'rank-badge-n')
            medal = _RANK_MEDAL.get(rank, str(rank))
            avatar = _avatar_html(name, 'happy', '48px')
            html += (
                f'<div class="ranking-card">\n'
                f'  <span class="rank-badge {badge_class}">{medal}</span>\n'
                f'  {avatar}\n'
                f'  <div>\n'
                f'    <strong>{profile["name_jp"]}</strong><br>\n'
                f'    <span style="font-size:1.05em;font-weight:700;">{r["current_balance"]:,}円</span>'
                f'    <span style="font-size:.88em;color:#888;"> ({sign}{diff:,}円)</span>\n'
                f'  </div>\n'
                f'</div>\n'
            )

        for i, r in enumerate(ranking):
            name = r['analyst_name']
            profile = ANALYST_PROFILES.get(name, {'name_jp': name, 'personality': ''})
            gap = first_balance - r['current_balance']
            comment = self._ranking_comment(name, profile['personality'], i + 1, total, gap)
            avatar = _avatar_html(name, 'happy', '56px')
            html += (
                f'<div class="ranking-inline">\n'
                f'  {avatar}\n'
                f'  <div class="character-balloon" style="flex:1;">'
                f'<strong>{profile["name_jp"]}</strong>：{comment}</div>\n'
                f'</div>\n'
            )
        return html

    def _section_today_entry(self, trade_date: str, entries: List[Dict]) -> str:
        if not entries:
            return f'<h2>今日のエントリー <span style="font-size:.8em;font-weight:normal;">{trade_date}</span></h2><p>エントリーなし</p>'

        html = f'<h2>今日のエントリー <span style="font-size:.8em;font-weight:normal;">{trade_date}</span></h2>\n'
        for analyst_name, profile in ANALYST_PROFILES.items():
            ae = [e for e in entries if e.get('analyst_name') == analyst_name]
            if not ae:
                continue
            html += f'<h3>{profile["name_jp"]}</h3>\n'
            html += '<table class="battle-table"><tr><th>銘柄コード</th><th>銘柄名</th><th>投資額</th><th>選定理由</th></tr>\n'
            total = 0
            for e in ae:
                approx_man = round(e.get('buy_amount', 0) / 10000)
                total += e.get('buy_amount', 0)
                html += (
                    f'<tr><td>{e["stock_code"]}</td>'
                    f'<td>{e["stock_name"]}</td>'
                    f'<td>約{approx_man}万円</td>'
                    f'<td>{e.get("prediction_reason", "")}</td></tr>\n'
                )
            html += f'</table>\n<p class="entry-total">合計　約{round(total / 10000)}万円</p>\n'

            stock_names = [e['stock_name'] for e in ae]
            comment = self._entry_comment(analyst_name, profile['personality'], stock_names)
            avatar = _avatar_html(analyst_name, 'happy', '56px')
            html += (
                f'<div class="character-inline">\n'
                f'  {avatar}\n'
                f'  <div class="character-balloon" style="flex:1;">{comment}</div>\n'
                f'</div>\n'
            )
        return html

    def _section_cumulative(self, cumulative_mvp: List[Dict]) -> str:
        if not cumulative_mvp:
            return ''
        html = '<h2>累計MVP記録</h2>\n'
        for i, r in enumerate(cumulative_mvp):
            name = r['analyst_name']
            profile = ANALYST_PROFILES.get(name, {'name_jp': name})
            medal = _RANK_MEDAL.get(i + 1, '🏅')
            html += (
                f'<div class="cumulative-card">\n'
                f'  <span style="font-size:1.4rem;">{medal}</span>\n'
                f'  <div>\n'
                f'    <strong>{profile["name_jp"]}</strong><br>\n'
                f'    <span class="mvp-count">MVP {r["mvp_count"]}回 / '
                f'月間優勝 {r["win_count"]}回 / '
                f'累計損益 {r["cumulative_profit_loss"]:+,}円</span>\n'
                f'  </div>\n'
                f'</div>\n'
            )
        return html

    def _section_monthly_ranking(self, monthly: List[Dict], year_month: str) -> str:
        html = f'<h2>{year_month} 月間ランキング</h2>\n'
        for r in monthly:
            name = r['analyst_name']
            profile = ANALYST_PROFILES.get(name, {'name_jp': name})
            mvp_mark = ' 👑' if r['is_mvp'] else ''
            win_rate = (
                round(r['win_count'] / (r['win_count'] + r['lose_count']) * 100, 1)
                if (r['win_count'] + r['lose_count']) > 0 else 0
            )
            rank = r['rank']
            badge_class = _RANK_BADGE_CLASS.get(rank, 'rank-badge-n')
            medal = _RANK_MEDAL.get(rank, str(rank))
            html += (
                f'<div class="ranking-card">\n'
                f'  <span class="rank-badge {badge_class}">{medal}</span>\n'
                f'  <div>\n'
                f'    <strong>{profile["name_jp"]}{mvp_mark}</strong><br>\n'
                f'    <span style="font-size:1.05em;font-weight:700;">{r["final_balance"]:,}円</span>'
                f'    <span style="font-size:.88em;color:#888;"> ({r["total_profit_loss"]:+,}円) '
                f'勝率{win_rate}%</span>\n'
                f'  </div>\n'
                f'</div>\n'
            )
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
                f'<div class="ranking-card">'
                f'<span style="font-size:1.4rem;">📈</span>'
                f'<div><strong>最大利益</strong>：{best[1]}（{best[0]}）<br>'
                f'<span style="color:#d85f8b;font-weight:700;">{best[3]:+,}円</span>'
                f' ({best[4]:+.1f}%) — {profile["name_jp"]}</div>'
                f'</div>\n'
            )
        if worst:
            profile = ANALYST_PROFILES.get(worst[2], {'name_jp': worst[2]})
            html += (
                f'<div class="ranking-card">'
                f'<span style="font-size:1.4rem;">📉</span>'
                f'<div><strong>最大損失</strong>：{worst[1]}（{worst[0]}）<br>'
                f'<span style="color:#5c7fc4;font-weight:700;">{worst[3]:+,}円</span>'
                f' ({worst[4]:+.1f}%) — {profile["name_jp"]}</div>'
                f'</div>\n'
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
