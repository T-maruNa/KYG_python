import json
import os
import re
from typing import List, Dict, Optional, Tuple
try:
    from src.image_generation.image_generation_service import ImageGenerationService
    _IMAGE_GENERATION_AVAILABLE = True
except Exception:
    _IMAGE_GENERATION_AVAILABLE = False

from src.database.t_daily_result_manager import TDailyResultManager
from src.database.t_investment_history_manager import TInvestmentHistoryManager
from src.database.t_monthly_result_manager import TMonthlyResultManager
from src.database.t_character_asset_manager import TCharacterAssetManager
from src.core.stats_aggregator import StatsAggregator
from src.ai_clients.gemini_client import GeminiClient
from src.core.ai_budget_guard import AIBudgetGuard
from src.core.prompt_loader import PromptLoader
from config.config import config

ANALYST_PROFILES = {
    'rei': {
        'name_jp': '鷲見 玲',
        'name_short': '玲',
        'role': 'テクニカル担当',
        'personality': (
            'メガネをかけた落ち着いた大人女子。テクニカル分析派。敬語で話す。冷静だがたまにドヤる。'
            '負けても取り乱さず次の分析に切り替える。「分析ノートを閉じる」「メガネを直す」「静かに微笑む」'
            '「流れを拾う」が口癖。勝つと少しだけ嬉しさが漏れる。'
        ),
        'visual': 'メガネ、大人女子、知的、静かに強い',
    },
    'mirai': {
        'name_jp': '桜庭 みらい',
        'name_short': 'みらい',
        'role': 'ファンダメンタル担当',
        'personality': (
            '背が低めのリクルートスーツ姿の新社会人。明るくポジティブ。話題性・雰囲気重視。'
            '外すと「えー、なんでー？」とあせり笑いする。読者との距離が近い。'
            '小柄だけど一生懸命で背伸びして頑張る。カフェでスマホや雑誌を見ながら情報収集する。'
        ),
        'visual': '背が低い、リクルートスーツ、新社会人感、初々しい',
    },
    'ritu': {
        'name_jp': '一ノ瀬 律',
        'name_short': '律',
        'role': '直感担当',
        'personality': (
            '金髪ギャル。敬語は使わない。勘で投資する。勝つと一番派手に喜ぶ。'
            '負けるとしょんぼりするが立ち直りも早い。「きたきたきた！」が口癖。'
            'アゲアゲ系で場を盛り上げる。サイコロネタが好き。'
        ),
        'visual': '金髪ギャル、ネイル、アクセサリー',
    },
}

CHAR_IMAGES = {
    'rei':   lambda: config.IMG_REI,
    'mirai': lambda: config.IMG_MIRAI,
    'ritu':  lambda: config.IMG_RITU,
}

def _scene_image_html(url: str, alt: str, css_class: str = 'scene-image',
                      image_type: str = '') -> str:
    if url:
        return f'<div class="{css_class}"><img src="{url}" alt="{alt}"></div>\n'
    label = {
        'morning_scene':         '☀️ 朝の作戦会議 3人集合画像（自動生成）',
        'morning_sub_scene':     '💬 今朝の3人 サブ画像（自動生成）',
        'hero_scene':            '⭐ 今日の主役キャラ画像（自動生成）',
        'night_reflection_scene':'🌙 今日の反省会 3人集合画像（自動生成）',
        'highlight_scene':       '✨ 今日の名場面 挿絵（自動生成）',
    }.get(image_type, f'🖼️ {alt}（自動生成）')
    return (
        f'<div class="{css_class} scene-image-placeholder">'
        f'<span class="scene-placeholder-label">{label}</span>'
        f'</div>\n'
    )

FORBIDDEN_PHRASES = [
    '絶対', '確実', '必ず上がる', '買うべき', '儲かる', '保証', '推奨銘柄',
    '狙い目', '今が買い', 'おすすめ銘柄', '仕込み時', '勝てる銘柄',
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
.battle-label,.section-label{display:inline-block;font-size:.82rem;letter-spacing:.08em;color:#9b6b88;background:rgba(255,255,255,.8);border-radius:999px;padding:4px 12px;margin-bottom:8px;border:1px solid #f0ddea;}
.battle-lead{margin:.4em 0 0;color:#7a6b80;font-size:.95rem;}
.battle-article h1{color:#4b3b57;margin:.2em 0;}
.battle-article h2{color:#4b3b57;border-bottom:none;margin-top:2.2em;padding-left:.2em;}
.battle-article h2::before{content:"✦ ";color:#e6a6c8;}
.battle-article h3{color:#4b3b57;margin:.6em 0 .3em;}
.sim-notice{font-size:.9em;color:#666;background:#f9f9f9;border-left:4px solid #e6a6c8;padding:.6em 1em;border-radius:0 8px 8px 0;margin-bottom:1.5em;}
/* 今日の主役 */
.today-hero{border-radius:24px;padding:22px 20px;margin:18px 0;box-shadow:0 10px 28px rgba(80,60,90,.09);}
.today-hero.character-rei{background:linear-gradient(135deg,#e8f2ff,#f1f7ff);}
.today-hero.character-mirai{background:linear-gradient(135deg,#ffe8f2,#fff3f7);}
.today-hero.character-ritu{background:linear-gradient(135deg,#fff8d0,#fffde8);}
.today-hero h2{margin-top:.3em;}
.today-hero h2::before{content:"⭐ ";}
/* キャラカード */
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
/* ランキング */
.ranking-card{display:flex;align-items:center;gap:12px;background:#fff;border-radius:18px;padding:12px 14px;margin:10px 0;box-shadow:0 6px 18px rgba(80,60,90,.06);}
.rank-badge{width:38px;height:38px;border-radius:50%;display:inline-flex;align-items:center;justify-content:center;font-weight:800;font-size:1.1rem;flex-shrink:0;}
.rank-badge-1{background:#ffe8a3;}
.rank-badge-2{background:#e8e8e8;}
.rank-badge-3{background:#f4d9c6;}
.rank-badge-n{background:#f0eef4;font-size:.9rem;}
.ranking-inline,.character-inline{display:flex;align-items:flex-start;gap:10px;margin:10px 0;}
.ranking-inline .character-avatar,.character-inline .character-avatar{width:56px;height:56px;}
/* テーブル */
.battle-table{width:100%;border-collapse:separate;border-spacing:0;overflow:hidden;border-radius:18px;background:#fff;box-shadow:0 8px 22px rgba(80,60,90,.06);margin:.8em 0;}
.battle-table th{background:#f6e8f0;color:#5f4a62;padding:10px 12px;text-align:left;}
.battle-table td{border:none;border-top:1px solid #f0e7ee;padding:10px 12px;}
.entry-total{text-align:right;font-size:.88rem;color:#9b6b88;margin:.2em 0 .8em;}
/* 反省会 */
.girls-talk{background:#fff;border-radius:24px;padding:20px 22px;margin:24px 0;box-shadow:0 8px 22px rgba(80,60,90,.07);}
.girls-talk h2::before{content:"💬 ";font-style:normal;}
.talk-line{border-radius:14px;padding:10px 14px;margin:8px 0;font-size:.95rem;}
.talk-line.rei{background:#e8f2ff;border-left:4px solid #7aabdf;}
.talk-line.mirai{background:#fff0f5;border-left:4px solid #f0a0c0;}
.talk-line.ritu{background:#fffadb;border-left:4px solid #f5cc50;}
/* 明日へ */
.next-hook{background:linear-gradient(135deg,#fff7fb,#f3f8ff);border-radius:18px;padding:16px 20px;margin:24px 0;font-size:.95rem;color:#4b3b57;border:1px solid #f0ddea;text-align:center;}
/* 累計 */
.cumulative-card{background:#fff;border-radius:18px;padding:14px 18px;margin:8px 0;box-shadow:0 4px 14px rgba(80,60,90,.06);display:flex;align-items:center;gap:10px;}
.mvp-count{font-size:.85rem;color:#7a6b80;}
/* 免責 */
.disclaimer-box{font-size:.86rem;color:#7a7280;background:#fafafa;border-radius:16px;padding:14px 16px;margin-top:32px;border:1px solid #eee;}
/* 朝記事 */
.strategy-talk{background:#fff;border-radius:24px;padding:20px 22px;margin:24px 0;box-shadow:0 8px 22px rgba(80,60,90,.07);}
.scene-image{margin:14px 0;border-radius:18px;overflow:hidden;box-shadow:0 8px 24px rgba(80,60,90,.10);}
.scene-image img{width:100%;height:auto;display:block;}
.scene-image-main{margin:16px 0 20px;}
.scene-image-sub{margin:10px 0 16px;}
.hero-image{margin:12px 0 16px;max-width:420px;}
.hero-image img{border-radius:16px;}
.scene-image-placeholder{display:flex;align-items:center;justify-content:center;min-height:80px;background:repeating-linear-gradient(45deg,#f8f4fc,#f8f4fc 8px,#f2edf8 8px,#f2edf8 16px);border:2px dashed #d8c8e8;border-radius:16px;box-shadow:none;}
.scene-placeholder-label{font-size:.82rem;color:#a088b0;letter-spacing:.04em;}
.strategy-talk h2::before{content:"☀️ ";font-style:normal;}
.spotlight-card{background:linear-gradient(135deg,#fff7fb,#f3f8ff);border-radius:18px;padding:16px 20px;margin:16px 0;border:1px solid #f0ddea;}
.spotlight-card h3::before{content:"👀 ";}
.result-teaser{background:linear-gradient(135deg,#f3f8ff,#fff7fb);border-radius:18px;padding:16px 20px;margin:24px 0;text-align:center;border:1px solid #e0e8f5;font-size:.95rem;color:#4b3b57;}
/* 夜記事 */
.push-points{background:#fff;border-radius:24px;padding:20px 22px;margin:24px 0;box-shadow:0 8px 22px rgba(80,60,90,.07);}
.push-points h2::before{content:"💕 ";font-style:normal;}
.push-item{border-radius:14px;padding:10px 14px;margin:8px 0;font-size:.95rem;}
.push-item.rei{background:#e8f2ff;border-left:4px solid #7aabdf;}
.push-item.mirai{background:#fff0f5;border-left:4px solid #f0a0c0;}
.push-item.ritu{background:#fffadb;border-left:4px solid #f5cc50;}
.morning-link{background:#f5f5f5;border-radius:14px;padding:12px 16px;margin:16px 0;font-size:.88rem;color:#666;text-align:center;}
@media(max-width:640px){
  .battle-hero{padding:20px 16px;border-radius:20px;}
  .character-card,.today-hero,.girls-talk{padding:16px;}
  .character-avatar{width:74px;height:74px;}
  .result-score{font-size:1.5rem;}
  .battle-table{display:block;overflow-x:auto;}
}
</style>'''

_ASSET_BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), '..', 'assets', 'characters')

_RANK_BADGE_CLASS = {1: 'rank-badge-1', 2: 'rank-badge-2', 3: 'rank-badge-3'}
_RANK_MEDAL = {1: '🥇', 2: '🥈', 3: '🥉'}


def _image_url(analyst_name: str, expression: str) -> str:
    variant = os.path.join(_ASSET_BASE, analyst_name, f'{expression}.png')
    if os.path.exists(variant):
        return f'assets/characters/{analyst_name}/{expression}.png'
    return f'assets/characters/{analyst_name}.png'


def _avatar_html(analyst_name: str, expression: str, size: str = '') -> str:
    style = f' style="width:{size};height:{size};"' if size else ''
    img_path = _image_url(analyst_name, expression)
    profile = ANALYST_PROFILES.get(analyst_name, {'name_jp': analyst_name})
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


def _get_today_hero(daily: List[Dict]) -> Optional[Dict]:
    """最も絶対損益が大きいキャラを今日の主役とする"""
    if not daily:
        return None
    return max(daily, key=lambda d: abs(d.get('total_profit_loss', 0)))


class BlogGenerator:
    def __init__(self):
        self.daily_manager = TDailyResultManager()
        self.history_manager = TInvestmentHistoryManager()
        self.monthly_manager = TMonthlyResultManager()
        self.asset_manager = TCharacterAssetManager()
        self.stats = StatsAggregator()
        self.gemini = GeminiClient()
        self.guard = AIBudgetGuard()
        if _IMAGE_GENERATION_AVAILABLE:
            try:
                self.image_service = ImageGenerationService()
            except Exception:
                self.image_service = None
        else:
            self.image_service = None

    # ------------------------------------------------------------------
    # 朝記事
    # ------------------------------------------------------------------

    def generate_prediction(self, trade_date: str, today_entries: List[Dict],
                            ranking: List[Dict] = None) -> Tuple[str, str]:
        """朝8時の作戦会議記事を生成する。"""
        ranking = ranking or []

        opening = self._generate_morning_opening(today_entries, ranking)
        subtitle = opening.get('subtitle', '今日の3人のエントリー')
        lead = opening.get('lead', '今日も3人の勝負が始まります。')
        talk_lines = opening.get('talk_lines', [
            {'name': 'rei',   'line': '流れを拾っていきます。'},
            {'name': 'mirai', 'line': '今日もいけそうな気がする！'},
            {'name': 'ritu',  'line': 'きたきたきた！今日もノリで行くよ！'},
        ])

        morning_three = self._generate_morning_three(today_entries, ranking)

        # 画像生成（失敗しても記事生成は継続）
        img_morning_scene = ''
        img_morning_sub = ''
        if self.image_service:
            try:
                img_morning_scene = self.image_service.generate_morning_scene(trade_date, {}) or ''
            except Exception as e:
                print(f'[BlogGenerator] morning_scene 生成失敗: {e}')
            try:
                img_morning_sub = self.image_service.generate_morning_sub_scene(trade_date, {}) or ''
            except Exception as e:
                print(f'[BlogGenerator] morning_sub_scene 生成失敗: {e}')

        title = f'【AI投資バトル】{trade_date} 朝の作戦会議｜{subtitle}'

        hero_html = (
            f'<div class="battle-hero">'
            f'<p class="battle-label">AI Virtual Investment Battle</p>'
            f'<h1>{title}</h1>'
            f'<p class="battle-lead">{lead}</p>'
            f'</div>'
        )
        notice = (
            '<p class="sim-notice">この記事は、AIキャラクターによる投資シミュレーション企画です。'
            '実際の売買を行ったものではありません。</p>'
        )

        sections = [
            BATTLE_CSS,
            '<section class="battle-article">',
            hero_html,
            notice,
            self._section_strategy_talk(talk_lines, image_url=img_morning_scene),
            self._section_morning_entry(trade_date, today_entries),
            self._section_morning_three(morning_three, image_url=img_morning_sub),
            self._section_result_teaser(trade_date),
            DISCLAIMER,
            '</section>',
        ]
        content = '\n'.join(sections)
        return title, content

    # ------------------------------------------------------------------
    # 夜記事
    # ------------------------------------------------------------------

    def generate_result(self, result_date: str, trade_date: str, year_month: str,
                        ranking: List[Dict] = None,
                        morning_post_url: str = None) -> Tuple[str, str]:
        """夜22時の結果発表記事を生成する。"""
        daily = self.daily_manager.get_by_date(result_date)
        ranking = ranking or self.stats.get_ranking(year_month)
        cumulative_mvp = self.monthly_manager.get_cumulative_mvp()

        ranking_by_analyst = {}
        if ranking:
            first_balance = ranking[0]['current_balance']
            for i, r in enumerate(ranking):
                ranking_by_analyst[r['analyst_name']] = {
                    'rank': i + 1,
                    'total': len(ranking),
                    'gap_from_first': first_balance - r['current_balance'],
                }

        hero_char = _get_today_hero(daily)

        opening = self._generate_result_opening(daily, ranking)
        drama_subtitle = opening.get('subtitle', '今日の結果発表')
        lead = opening.get('lead', '今日の勝負結果をお伝えします。')

        girls_talk_lines = self._generate_girls_talk(daily, ranking)
        push_points = self._generate_push_points(daily)
        next_hook = self._generate_next_hook(daily, ranking)

        # 画像生成（失敗しても記事生成は継続）
        img_hero = ''
        img_night = ''
        img_highlight = ''
        if self.image_service:
            try:
                if hero_char:
                    hero_name = hero_char['analyst_name']
                    hero_profit = hero_char['total_profit_loss']
                    hero_expression = get_expression(hero_profit)
                    img_hero = self.image_service.generate_hero_scene(
                        result_date, hero_name, hero_expression, {}
                    ) or ''
            except Exception as e:
                print(f'[BlogGenerator] hero_scene 生成失敗: {e}')
            try:
                img_night = self.image_service.generate_night_reflection_scene(result_date, {}) or ''
            except Exception as e:
                print(f'[BlogGenerator] night_reflection_scene 生成失敗: {e}')
            try:
                highlight_desc = push_points[0].get('point', '') if push_points else ''
                img_highlight = self.image_service.generate_highlight_scene(result_date, highlight_desc) or ''
            except Exception as e:
                print(f'[BlogGenerator] highlight_scene 生成失敗: {e}')

        title = f'【AI投資バトル】{result_date} 結果発表｜{drama_subtitle}'

        hero_html = (
            f'<div class="battle-hero">'
            f'<p class="battle-label">AI Virtual Investment Battle</p>'
            f'<h1>{title}</h1>'
            f'<p class="battle-lead">{lead}</p>'
            f'</div>'
        )
        notice = (
            '<p class="sim-notice">この記事は、AIキャラクターによる投資シミュレーション企画です。'
            '実際の売買を行ったものではありません。</p>'
        )

        ranking_narrative = self._generate_ranking_narrative(ranking)

        sections = [
            BATTLE_CSS,
            '<section class="battle-article">',
            self._section_morning_link(morning_post_url),
            hero_html,
            notice,
            self._section_today_hero(hero_char, daily, image_url=img_hero),
            self._section_result(result_date, daily, [], ranking_by_analyst),
            self._section_girls_talk(girls_talk_lines, daily, image_url=img_night),
            self._section_ranking(ranking, year_month, narrative=ranking_narrative),
            self._section_push_points(push_points, image_url=img_highlight),
            f'<p class="next-hook">{next_hook}</p>',
            self._section_cumulative(cumulative_mvp),
            DISCLAIMER,
            '</section>',
        ]
        content = '\n'.join(sections)
        return title, content

    # ------------------------------------------------------------------
    # 後方互換エイリアス
    # ------------------------------------------------------------------

    def generate_daily(self, result_date: str, trade_date: str, year_month: str,
                       ranking: List[Dict] = None) -> str:
        """後方互換エイリアス。generate_result() を呼び出して本文文字列を返す。"""
        _, content = self.generate_result(
            result_date=result_date,
            trade_date=trade_date,
            year_month=year_month,
            ranking=ranking,
        )
        return content

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
    # 内部セクション — 朝記事
    # ------------------------------------------------------------------

    def _section_strategy_talk(self, talk_lines: List[Dict], image_url: str = '') -> str:
        if not talk_lines:
            return ''
        html = (
            '<section class="strategy-talk">\n'
            '<h2>☀️ 今日の作戦会議</h2>\n'
        )
        html += _scene_image_html(image_url or config.IMG_MORNING_SCENE, '朝の作戦会議をする3人', 'scene-image scene-image-main', 'morning_scene')
        for line in talk_lines:
            name = line.get('name', '')
            text = line.get('line', '')
            profile = ANALYST_PROFILES.get(name, {'name_short': name})
            short = profile.get('name_short', name)
            html += f'<div class="talk-line {name}">{short}「{text}」</div>\n'
        html += '</section>\n'
        return html

    def _section_morning_entry(self, trade_date: str, entries: List[Dict]) -> str:
        return self._section_today_entry(trade_date, entries)

    def _section_morning_three(self, talk_lines: List[Dict], image_url: str = '') -> str:
        """朝記事: 今朝の3人（順位・選択・関係性セリフ）"""
        if not talk_lines:
            return ''
        html = '<section class="strategy-talk morning-three">\n<h2>💬 今朝の3人</h2>\n'
        html += _scene_image_html(image_url, '今朝の3人', 'scene-image scene-image-sub', 'morning_sub_scene')
        for line in talk_lines:
            name = line.get('name', '')
            text = line.get('line', '')
            profile = ANALYST_PROFILES.get(name, {'name_short': name})
            short = profile.get('name_short', name)
            html += f'<div class="talk-line {name}">{short}「{text}」</div>\n'
        html += '</section>\n'
        return html

    def _section_result_teaser(self, trade_date: str) -> str:
        return (
            '<div class="result-teaser">'
            'この勝負の結果は、今夜22時ごろに発表予定です。<br>'
            'お楽しみに！'
            '</div>\n'
        )

    def _section_morning_link(self, url: str = None) -> str:
        if not url:
            return ''
        return (
            f'<div class="morning-link">📋 <a href="{url}">朝の作戦会議はこちら</a></div>\n'
        )

    # ------------------------------------------------------------------
    # 内部セクション — 夜記事
    # ------------------------------------------------------------------

    def _section_push_points(self, push_points: List[Dict], image_url: str = '') -> str:
        if not push_points:
            return ''
        html = (
            '<section class="push-points">\n'
            '<h2>✨ 今日の名場面</h2>\n'
        )
        html += _scene_image_html(image_url, '今日の名場面', 'scene-image scene-image-sub', 'highlight_scene')
        for item in push_points:
            name = item.get('name', '')
            point = item.get('point', '')
            profile = ANALYST_PROFILES.get(name, {'name_short': name})
            short = profile.get('name_short', name)
            html += f'<div class="push-item {name}">{short}：{point}</div>\n'
        html += '</section>\n'
        return html

    # ------------------------------------------------------------------
    # 内部セクション — 共通
    # ------------------------------------------------------------------

    def _section_today_hero(self, hero_char: Optional[Dict], daily: List[Dict], image_url: str = '') -> str:
        if not hero_char:
            return ''
        name = hero_char['analyst_name']
        profile = ANALYST_PROFILES.get(name, {'name_jp': name, 'name_short': name, 'personality': ''})
        profit = hero_char['total_profit_loss']
        sign = '+' if profit >= 0 else ''
        win = hero_char['win_count']
        lose = hero_char['lose_count']

        intro = self._generate_hero_intro(name, profile['personality'], profit, win, lose)

        hero_img_url = image_url or CHAR_IMAGES.get(name, lambda: '')()
        hero_img = _scene_image_html(hero_img_url, f'{profile["name_short"]}', 'scene-image hero-image', 'hero_scene')
        return (
            f'<section class="today-hero character-{name}">\n'
            f'  <p class="section-label">今日の主役</p>\n'
            f'  <h2>{profile["name_short"]}が今日の主役！</h2>\n'
            f'{hero_img}'
            f'  <p>{intro}</p>\n'
            f'</section>\n'
        )

    def _section_result(self, result_date: str, daily: List[Dict],
                        entries: List[Dict], ranking_by_analyst: Dict = None) -> str:
        if not daily:
            return f'<h2>🏁 今日の勝負結果</h2><p>データがありません。</p>'

        html = f'<h2>🏁 今日の勝負結果 <span style="font-size:.8em;font-weight:normal;">{result_date}</span></h2>\n'
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
                f'  <p class="result-meta">{win}勝{lose}敗 / 現在の資産 {balance:,}円</p>\n'
                f'  <div class="character-balloon">{comment}</div>\n'
                f'</div>\n'
            )
        return html

    def _section_ranking(self, ranking: List[Dict], year_month: str,
                         narrative: str = None) -> str:
        html = '<h2>🏆 今月のランキング</h2>\n'
        if narrative:
            html += f'<p style="color:#7a6b80;font-size:.95rem;">{narrative}</p>\n'
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
            html += (
                f'<div class="ranking-card">\n'
                f'  <span class="rank-badge {badge_class}">{medal}</span>\n'
                f'  {_avatar_html(name, "happy", "48px")}\n'
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
            html += (
                f'<div class="ranking-inline">\n'
                f'  {_avatar_html(name, "happy", "56px")}\n'
                f'  <div class="character-balloon" style="flex:1;">'
                f'<strong>{profile["name_jp"]}</strong>：{comment}</div>\n'
                f'</div>\n'
            )
        return html

    def _section_today_entry(self, trade_date: str, entries: List[Dict]) -> str:
        _AVATAR_ICONS = {'rei': '👓', 'mirai': '🌸', 'ritu': '🎲'}
        if not entries:
            return (
                f'<h2>📒 今日の作戦ノート <span style="font-size:.8em;font-weight:normal;">{trade_date}</span></h2>'
                f'<p>エントリーなし</p>'
            )

        html = f'<h2>📒 今日の作戦ノート <span style="font-size:.8em;font-weight:normal;">{trade_date}</span></h2>\n'
        for analyst_name, profile in ANALYST_PROFILES.items():
            ae = [e for e in entries if e.get('analyst_name') == analyst_name]
            if not ae:
                continue
            icon = _AVATAR_ICONS.get(analyst_name, '👤')
            short = profile.get('name_short', analyst_name)
            name_jp = profile['name_jp']
            role = profile.get('role', '')
            html += (
                f'<section class="strategy-card character-{analyst_name}">\n'
                f'  <div class="strategy-card-header">\n'
                f'    <div class="character-avatar placeholder-{analyst_name}">\n'
                f'      <span class="avatar-icon">{icon}</span>\n'
                f'      <span class="avatar-name">{short}</span>\n'
                f'    </div>\n'
                f'    <div>\n'
                f'      <h3 class="character-name">{name_jp}の作戦ノート</h3>\n'
                f'      <p class="character-role">{role}</p>\n'
                f'    </div>\n'
                f'  </div>\n'
                f'  <div class="entry-chip-list">\n'
            )
            total = 0
            reasons = []
            for e in ae:
                approx_man = round(e.get('buy_amount', 0) / 10000)
                total += e.get('buy_amount', 0)
                code = e.get('stock_code', '')
                name = e.get('stock_name', '')
                html += (
                    f'    <div class="entry-chip">'
                    f'<span class="stock-code">{code}</span>'
                    f'<strong>{name}</strong>'
                    f'<span class="amount">約{approx_man}万円</span>'
                    f'</div>\n'
                )
                reasons.append(e.get('prediction_reason', ''))
            html += f'  </div>\n'
            total_man = round(total / 10000)
            html += f'  <div class="strategy-total">今日の作戦予算：<strong>合計 約{total_man}万円</strong></div>\n'
            reason_text = '／'.join(r for r in reasons if r)
            if reason_text:
                html += f'  <div class="strategy-reason">{reason_text}</div>\n'

            stock_names = [e['stock_name'] for e in ae]
            comment = self._entry_comment(analyst_name, profile['personality'], stock_names)
            html += (
                f'  <div class="character-balloon">{comment}</div>\n'
                f'</section>\n'
            )
        return html

    def _section_girls_talk(self, talk_lines: List[Dict], daily: List[Dict], image_url: str = '') -> str:
        if not talk_lines:
            return ''
        html = (
            '<section class="girls-talk">\n'
            '<h2>🌙 今日の反省会</h2>\n'
        )
        html += _scene_image_html(image_url or config.IMG_EVENING_SCENE, '夜の反省会をする3人', 'scene-image scene-image-main', 'night_reflection_scene')
        for line in talk_lines:
            name = line.get('name', '')
            text = line.get('line', '')
            profile = ANALYST_PROFILES.get(name, {'name_short': name})
            short = profile.get('name_short', name)
            html += f'<div class="talk-line {name}">{short}「{text}」</div>\n'
        html += '</section>\n'
        return html

    def _section_cumulative(self, cumulative_mvp: List[Dict]) -> str:
        if not cumulative_mvp:
            return ''
        html = '<h2>これまでのMVP記録</h2>\n'
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
        with self.history_manager._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT stock_code, stock_name, analyst_name, profit_loss, profit_loss_rate
                FROM t_investment_history
                WHERE trade_date LIKE %s AND sell_price IS NOT NULL AND profit_loss IS NOT NULL
                ORDER BY profit_loss DESC LIMIT 1
            ''', (f'{year_month}%',))
            best = cursor.fetchone()
            cursor.execute('''
                SELECT stock_code, stock_name, analyst_name, profit_loss, profit_loss_rate
                FROM t_investment_history
                WHERE trade_date LIKE %s AND sell_price IS NOT NULL AND profit_loss IS NOT NULL
                ORDER BY profit_loss ASC LIMIT 1
            ''', (f'{year_month}%',))
            worst = cursor.fetchone()

        html = '<h2>月間トピックス</h2>\n'
        if best:
            profile = ANALYST_PROFILES.get(best[2], {'name_jp': best[2]})
            html += (
                f'<div class="ranking-card"><span style="font-size:1.4rem;">📈</span>'
                f'<div><strong>最大利益</strong>：{best[1]}（{best[0]}）<br>'
                f'<span style="color:#d85f8b;font-weight:700;">{best[3]:+,}円</span>'
                f' ({best[4]:+.1f}%) — {profile["name_jp"]}</div></div>\n'
            )
        if worst:
            profile = ANALYST_PROFILES.get(worst[2], {'name_jp': worst[2]})
            html += (
                f'<div class="ranking-card"><span style="font-size:1.4rem;">📉</span>'
                f'<div><strong>最大損失</strong>：{worst[1]}（{worst[0]}）<br>'
                f'<span style="color:#5c7fc4;font-weight:700;">{worst[3]:+,}円</span>'
                f' ({worst[4]:+.1f}%) — {profile["name_jp"]}</div></div>\n'
            )
        return html

    # ------------------------------------------------------------------
    # AI生成: 朝記事
    # ------------------------------------------------------------------

    def _generate_morning_opening(self, today_entries: List[Dict],
                                  ranking: List[Dict]) -> Dict:
        """朝記事用オープニング（subtitle/lead/talk_lines）を1回のAIコールで生成する。"""
        fallback = {
            'subtitle': '今日の3人のエントリー',
            'lead': '今日も3人の勝負が始まります。',
            'talk_lines': [
                {'name': 'rei',   'line': '流れを拾っていきます。'},
                {'name': 'mirai', 'line': '今日もいけそうな気がする！'},
                {'name': 'ritu',  'line': 'きたきたきた！今日もノリで行くよ！'},
            ],
        }

        entries_summary = '\n'.join(
            f'{ANALYST_PROFILES.get(e["analyst_name"], {}).get("name_jp", e["analyst_name"])}: '
            f'{e.get("stock_name", "")}（{e.get("stock_code", "")}）{e.get("prediction_reason", "")}'
            for e in today_entries
        ) if today_entries else 'エントリーなし'

        ranking_txt = ', '.join(
            f'{i+1}位: {ANALYST_PROFILES.get(r["analyst_name"], {}).get("name_short", r["analyst_name"])}'
            f'（{r["current_balance"]:,}円）'
            for i, r in enumerate(ranking)
        ) if ranking else ''

        try:
            messages = [
                {'role': 'system', 'content': PromptLoader.base_system()
                    + f'\n\n## 記事ガイドライン\n\n{PromptLoader.prediction_article()}'
                    + f'\n\n## 会話生成ガイドライン\n\n{PromptLoader.talk()}'},
                {'role': 'user', 'content': (
                    f'今日のエントリー：\n{entries_summary}\n'
                    f'現在の順位：{ranking_txt}\n\n'
                    f'朝の作戦会議記事用のオープニングコンテンツを作ってください。\n'
                    f'以下のJSON形式で返してください（他の文字は不要）：\n'
                    f'{{"subtitle":"玲は堅実、律は今日もノリ勝負（例）","lead":"リード文1〜2文",'
                    f'"talk_lines":[{{"name":"rei","line":"..."}},{{"name":"mirai","line":"..."}},{{"name":"ritu","line":"..."}}]}}'
                )},
            ]
            raw = self.guard.execute(
                self.gemini.execute_chat, messages, call_type='morning_opening', model='gemini',
            )
            if raw:
                m = re.search(r'\{.*\}', raw, re.DOTALL)
                if m:
                    parsed = json.loads(m.group())
                    if isinstance(parsed, dict) and 'subtitle' in parsed:
                        return parsed
        except Exception:
            pass
        return fallback

    def _generate_morning_three(self, today_entries: List[Dict], ranking: List[Dict]) -> List[Dict]:
        """朝記事「今朝の3人」セクション用のセリフ一覧を生成する。"""
        fallback = [
            {'name': 'rei',   'line': 'テクニカルで流れを拾っていきます。'},
            {'name': 'mirai', 'line': '今日もいい銘柄見つけたよ！'},
            {'name': 'ritu',  'line': 'きたきたきた！今日もノリで行くよ！'},
        ]
        if not today_entries:
            return fallback

        entries_summary = '\n'.join(
            f'{ANALYST_PROFILES.get(e["analyst_name"], {}).get("name_jp", e["analyst_name"])}: '
            f'{e.get("stock_name", "")}（{e.get("stock_code", "")}）'
            for e in today_entries
        )
        ranking_txt = ', '.join(
            f'{i+1}位: {ANALYST_PROFILES.get(r["analyst_name"], {}).get("name_short", r["analyst_name"])}'
            f'（{r["current_balance"]:,}円）'
            for i, r in enumerate(ranking)
        ) if ranking else ''

        try:
            messages = [
                {'role': 'system', 'content': PromptLoader.base_system()
                    + f'\n\n## 会話生成ガイドライン\n\n{PromptLoader.talk()}'},
                {'role': 'user', 'content': (
                    f'今日のエントリー：\n{entries_summary}\n'
                    f'現在の順位：{ranking_txt}\n\n'
                    f'「今朝の3人」コーナー用のセリフを生成してください。'
                    f'各キャラが現在の順位・自分の選択・他2人の選択への反応を踏まえて一言ずつ話します。\n'
                    f'以下のJSON配列形式で返してください（他の文字は不要）：\n'
                    f'[{{"name":"rei","line":"..."}},{{"name":"mirai","line":"..."}},{{"name":"ritu","line":"..."}}]'
                )},
            ]
            raw = self.guard.execute(
                self.gemini.execute_chat, messages, call_type='morning_three', model='gemini',
            )
            if raw:
                m = re.search(r'\[.*?\]', raw, re.DOTALL)
                if m:
                    parsed = json.loads(m.group())
                    if isinstance(parsed, list) and len(parsed) == 3:
                        return parsed
        except Exception:
            pass
        return fallback

    # ------------------------------------------------------------------
    # AI生成: 夜記事
    # ------------------------------------------------------------------

    def _generate_result_opening(self, daily: List[Dict], ranking: List[Dict]) -> Dict:
        """夜記事用オープニング（subtitle/lead）を1回のAIコールで生成する。"""
        fallback = {
            'subtitle': '今日の結果発表',
            'lead': '今日の勝負結果をお伝えします。',
        }
        if not daily:
            return fallback

        summary = '\n'.join(
            f'{ANALYST_PROFILES.get(d["analyst_name"], {}).get("name_jp", d["analyst_name"])}: '
            f'{"+" if d["total_profit_loss"] >= 0 else ""}{d["total_profit_loss"]:,}円 '
            f'({d["win_count"]}勝{d["lose_count"]}敗)'
            for d in daily
        )
        ranking_txt = ', '.join(
            f'{i+1}位: {ANALYST_PROFILES.get(r["analyst_name"], {}).get("name_short", r["analyst_name"])}'
            for i, r in enumerate(ranking)
        ) if ranking else ''

        try:
            messages = [
                {'role': 'system', 'content': PromptLoader.base_system()
                    + f'\n\n## 記事ガイドライン\n\n{PromptLoader.result_article()}'},
                {'role': 'user', 'content': (
                    f'今日の仮想投資結果：\n{summary}\n'
                    f'順位：{ranking_txt}\n\n'
                    f'夜の結果発表記事用のオープニングを作ってください。\n'
                    f'subtitleはキャラクターのドラマが伝わるような短いフレーズ（例：律が大暴れ、みらいは反省会へ）にしてください。\n'
                    f'以下のJSON形式で返してください（他の文字は不要）：\n'
                    f'{{"subtitle":"律が大暴れ、みらいは反省会へ（例）","lead":"リード文1〜2文"}}'
                )},
            ]
            raw = self.guard.execute(
                self.gemini.execute_chat, messages, call_type='result_opening', model='gemini',
            )
            if raw:
                m = re.search(r'\{.*\}', raw, re.DOTALL)
                if m:
                    parsed = json.loads(m.group())
                    if isinstance(parsed, dict) and 'subtitle' in parsed:
                        return parsed
        except Exception:
            pass
        return fallback

    def _generate_push_points(self, daily: List[Dict]) -> List[Dict]:
        """各キャラの今日の推しポイントを1回のAIコールで生成する。"""
        fallback = [
            {'name': 'rei',   'point': 'メガネを直しながら、今日のプラスを静かに確認。'},
            {'name': 'mirai', 'point': '悔しそうにしながらも、明日の巻き返しを口にする。'},
            {'name': 'ritu',  'point': '今日も全力で喜んだり、しょんぼりしたりの一日。'},
        ]
        if not daily:
            return fallback

        summary = '\n'.join(
            f'{ANALYST_PROFILES.get(d["analyst_name"], {}).get("name_jp", d["analyst_name"])}: '
            f'{"+" if d["total_profit_loss"] >= 0 else ""}{d["total_profit_loss"]:,}円 '
            f'({d["win_count"]}勝{d["lose_count"]}敗)'
            for d in daily
        )

        try:
            messages = [
                {'role': 'system', 'content': PromptLoader.base_system()
                    + f'\n\n## 会話・推しポイント生成ガイドライン\n\n{PromptLoader.talk()}'},
                {'role': 'user', 'content': (
                    f'今日の仮想投資結果：\n{summary}\n\n'
                    f'今日のキャラクターそれぞれの「ハイライト」を1文ずつ書いてください。'
                    f'その日の名場面・情景を自然な一文で切り取ってください（推し説明ではなくシーン描写）。\n'
                    f'以下のJSON配列形式で返してください（他の文字は不要）：\n'
                    f'[{{"name":"rei","point":"..."}},{{"name":"mirai","point":"..."}},{{"name":"ritu","point":"..."}}]'
                )},
            ]
            raw = self.guard.execute(
                self.gemini.execute_chat, messages, call_type='push_points', model='gemini',
            )
            if raw:
                m = re.search(r'\[.*?\]', raw, re.DOTALL)
                if m:
                    parsed = json.loads(m.group())
                    if isinstance(parsed, list) and len(parsed) == 3:
                        return parsed
        except Exception:
            pass
        return fallback

    def _generate_ranking_narrative(self, ranking: List[Dict]) -> str:
        """ランキングセクション上のナレーション行を生成する。"""
        if not ranking:
            return ''
        first = ANALYST_PROFILES.get(ranking[0]['analyst_name'], {}).get('name_short', '')
        try:
            messages = [
                {'role': 'system', 'content': PromptLoader.base_system('投資シミュレーションブログの編集者')},
                {'role': 'user', 'content': (
                    f'現在1位は{first}。'
                    f'ランキングセクションの冒頭に添える、短い1文のナレーションを書いてください。'
                )},
            ]
            result = self.guard.execute(
                self.gemini.execute_chat, messages, call_type='ranking_narrative', model='gemini',
            )
            return result.strip() if result else ''
        except Exception:
            return ''

    # ------------------------------------------------------------------
    # AI生成: ナレーション系
    # ------------------------------------------------------------------

    def _generate_lead(self, daily: List[Dict], ranking: List[Dict]) -> str:
        """記事冒頭のリード文を生成する"""
        if not daily:
            return '今日もシミュレーション投資バトル、スタートです。'
        summary = ', '.join(
            f'{ANALYST_PROFILES.get(d["analyst_name"], {}).get("name_short", d["analyst_name"])}が'
            f'{"+" if d["total_profit_loss"] >= 0 else ""}{d["total_profit_loss"]:,}円'
            for d in daily
        )
        try:
            messages = [
                {'role': 'system', 'content': PromptLoader.base_system('投資シミュレーションブログの編集者')},
                {'role': 'user', 'content': (
                    f'今日の仮想投資バトルの結果は以下でした：{summary}。\n'
                    f'読者が「今日もドラマあったな」と感じるような、1〜2文のリード文を書いてください。\n'
                    f'キャラクターの名前を入れてください。'
                )},
            ]
            result = self.guard.execute(
                self.gemini.execute_chat, messages, call_type='lead', model='gemini',
            )
            return result.strip() if result else summary
        except Exception:
            return summary

    def _generate_hero_intro(self, analyst_name: str, personality: str,
                             profit: int, win: int, lose: int) -> str:
        """今日の主役の紹介文を生成する"""
        sign = '+' if profit >= 0 else ''
        profile = ANALYST_PROFILES.get(analyst_name, {'name_jp': analyst_name})
        try:
            messages = [
                {'role': 'system', 'content': PromptLoader.character_system(analyst_name, profile['name_jp'])},
                {'role': 'user', 'content': (
                    f'今日の成績は{sign}{profit:,}円（{win}勝{lose}敗）でした。'
                    f'今日の主役として紹介される1文のコメントを返してください。'
                )},
            ]
            result = self.guard.execute(
                self.gemini.execute_chat, messages, call_type='hero_intro', model='gemini',
            )
            return result.strip() if result else f'今日は{sign}{profit:,}円。{win}勝{lose}敗でした。'
        except Exception:
            return f'今日は{sign}{profit:,}円。{win}勝{lose}敗でした。'

    def _generate_girls_talk(self, daily: List[Dict], ranking: List[Dict]) -> List[Dict]:
        """3人の反省会トークを生成する（JSON配列形式で取得）"""
        if not daily:
            return []

        summary = '\n'.join(
            f'{ANALYST_PROFILES.get(d["analyst_name"], {}).get("name_jp", d["analyst_name"])}: '
            f'{"+" if d["total_profit_loss"] >= 0 else ""}{d["total_profit_loss"]:,}円 '
            f'({d["win_count"]}勝{d["lose_count"]}敗)'
            for d in daily
        )
        ranking_txt = ', '.join(
            f'{i+1}位: {ANALYST_PROFILES.get(r["analyst_name"], {}).get("name_short", r["analyst_name"])}'
            for i, r in enumerate(ranking)
        ) if ranking else ''

        fallback = [
            {'name': 'rei',   'line': '今日も精一杯やりました。'},
            {'name': 'mirai', 'line': '明日はもっとうまくやれる気がする！'},
            {'name': 'ritu',  'line': '今日は今日！明日は明日！'},
        ]
        try:
            messages = [
                {'role': 'system', 'content': PromptLoader.base_system()
                    + f'\n\n## 会話生成ガイドライン\n\n{PromptLoader.talk()}'},
                {'role': 'user', 'content': (
                    f'今日の仮想投資結果：\n{summary}\n'
                    f'順位：{ranking_txt}\n\n'
                    f'3人が今日の結果について1行ずつ会話する「反省会」シーンを書いてください。\n'
                    f'各キャラが自分の成績だけでなく、他2人の成績と比較しながら話すようにしてください。\n'
                    f'（例：勝ったキャラは負けたキャラをいじる、負けたキャラは勝ったキャラに悔しがる）\n'
                    f'以下のJSON配列形式で返してください（他の文字は不要）：\n'
                    f'[{{"name":"rei","line":"..."}},{{"name":"mirai","line":"..."}},{{"name":"ritu","line":"..."}}]'
                )},
            ]
            raw = self.guard.execute(
                self.gemini.execute_chat, messages, call_type='girls_talk', model='gemini',
            )
            if raw:
                m = re.search(r'\[.*?\]', raw, re.DOTALL)
                if m:
                    parsed = json.loads(m.group())
                    if isinstance(parsed, list) and len(parsed) == 3:
                        return parsed
        except Exception:
            pass
        return fallback

    def _generate_next_hook(self, daily: List[Dict], ranking: List[Dict]) -> str:
        """明日へのひとことを生成する"""
        if not ranking:
            return '明日も3人の勝負を、ゆるく見守ってください。'
        first = ANALYST_PROFILES.get(ranking[0]['analyst_name'], {}).get('name_short', '')
        last = ANALYST_PROFILES.get(ranking[-1]['analyst_name'], {}).get('name_short', '') if len(ranking) > 1 else ''
        try:
            messages = [
                {'role': 'system', 'content': PromptLoader.base_system('投資シミュレーションブログの編集者')},
                {'role': 'user', 'content': (
                    f'現在の順位: {", ".join(ANALYST_PROFILES.get(r["analyst_name"],{}).get("name_short","") for r in ranking)}の順。\n'
                    f'読者が明日も見に来たくなるような、1文の締めの文章を書いてください。\n'
                    f'キャラ名を入れて、連載感を出してください。'
                )},
            ]
            result = self.guard.execute(
                self.gemini.execute_chat, messages, call_type='next_hook', model='gemini',
            )
            return result.strip() if result else f'明日は{last}が巻き返すのか、{first}がこのまま走るのか。次回もゆるく見守ってください。'
        except Exception:
            return f'明日も3人の勝負を、ゆるく見守ってください。'

    # ------------------------------------------------------------------
    # AI生成: キャラクターコメント系
    # ------------------------------------------------------------------

    def _character_comment(self, analyst_name: str, personality: str,
                           profit: int, win: int, lose: int,
                           ranking_info: Dict = None) -> str:
        sign = '+' if profit >= 0 else ''
        profile = ANALYST_PROFILES.get(analyst_name, {'name_jp': analyst_name})
        rank_context = ''
        if ranking_info:
            rank = ranking_info.get('rank', 1)
            gap = ranking_info.get('gap_from_first', 0)
            rank_context = '現在1位です。' if rank == 1 else f'現在{rank}位（1位との差：{gap:,}円）です。'
        try:
            messages = [
                {'role': 'system', 'content': PromptLoader.character_system(analyst_name, profile['name_jp'])},
                {'role': 'user', 'content': (
                    f'今日の結果は{sign}{profit:,}円（{win}勝{lose}敗）でした。{rank_context}'
                    f'キャラクターらしい短いコメントを1〜2文で。順位にも触れてください。'
                )},
            ]
            result = self.guard.execute(
                self.gemini.execute_chat, messages, call_type='character_comment', model='gemini',
            )
            return result.strip() if result else f'今日は{sign}{profit:,}円でした。'
        except Exception:
            return f'今日は{sign}{profit:,}円でした。'

    def _ranking_comment(self, analyst_name: str, personality: str,
                         rank: int, total: int, gap_from_first: int) -> str:
        profile = ANALYST_PROFILES.get(analyst_name, {'name_jp': analyst_name})
        rank_ctx = f'{total}人中1位です。' if rank == 1 else f'{total}人中{rank}位で、1位との差は{gap_from_first:,}円です。'
        try:
            messages = [
                {'role': 'system', 'content': PromptLoader.character_system(analyst_name, profile['name_jp'])},
                {'role': 'user', 'content': (
                    f'{rank_ctx}順位についてキャラクターらしい一言を1文で。'
                )},
            ]
            result = self.guard.execute(
                self.gemini.execute_chat, messages, call_type='ranking_comment', model='gemini',
            )
            return result.strip() if result else rank_ctx
        except Exception:
            return f'{rank}位です。'

    def _entry_comment(self, analyst_name: str, personality: str,
                       stock_names: List[str]) -> str:
        profile = ANALYST_PROFILES.get(analyst_name, {'name_jp': analyst_name})
        stocks_str = '、'.join(stock_names)
        try:
            messages = [
                {'role': 'system', 'content': PromptLoader.character_system(analyst_name, profile['name_jp'])},
                {'role': 'user', 'content': (
                    f'今日のエントリー銘柄は{stocks_str}です。'
                    f'選んだ理由や意気込みをキャラクターらしく1〜2文で。'
                )},
            ]
            result = self.guard.execute(
                self.gemini.execute_chat, messages, call_type='entry_comment', model='gemini',
            )
            return result.strip() if result else f'今日は{stocks_str}に注目しています。'
        except Exception:
            return f'今日の注目銘柄は{", ".join(stock_names)}です。'
