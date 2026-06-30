"""
ブログプレビュー生成スクリプト

DBや予算ガードを使わず、サンプルデータ＋Gemini APIで
実際のブログHTMLを生成して blog_preview.html に出力する。

朝記事（作戦会議）と夜記事（結果発表）の両方を1ファイルに出力する。

GEMINI_STOCK_API_KEY が未設定の場合はAIコメントをプレースホルダーで代替。

Usage:
    cd tests
    python generate_blog_preview.py
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'batch'))

from src.core.prompt_loader import PromptLoader

# blog_generator.py と同定義（インポートすると psycopg2 等が連鎖ロードされるため直接定義）
# 日曜（6）は前週1位キャラを使うため呼び出し側で解決する
_WEEKDAY_NARRATOR = {0: 'rei', 1: 'mirai', 2: 'rei', 3: 'mirai', 4: 'ritu', 5: 'ritu'}
_NARRATOR_TONE = {
    'rei': (
        '鷲見 玲（rei）の口調で書いてください。'
        '週の始まりや中間整理の担当。冷静で落ち着いている。敬語ベースだが固くなりすぎない。'
        '前営業日の流れや順位を静かに整理して、読者を自然に記事へ引き込む語り口。'
        'ドヤりは控えめ。文末は「〜します」「〜確認します」程度の落ち着いた締め方。'
    ),
    'mirai': (
        '桜庭 みらい（mirai）の口調で書いてください。'
        '週前半・週後半を前向きに進める担当。明るくポジティブ、一生懸命。'
        '少しくだけた話し言葉でもOK。負けていても「ここから」と前を向く。'
        '感情が少し出てよいが、泣かせすぎない。文末は「〜しましょう」「〜始めます」くらい。'
    ),
    'ritu': (
        '一ノ瀬 律（ritu）の口調で書いてください。'
        '金曜・週末担当。週末前の開放感を少し出してよい。ノリが軽い。敬語は使わない。'
        '勝ったら喜ぶ、負けても「切り替えよ！週末あるし」くらいの軽さ。'
        'でも勝負はちゃんと見ている。文末は「〜じゃん？」「〜行くよ！」程度のカジュアルな締め。'
    ),
}

def get_weekday_narrator(date_str: str, sunday_narrator: str = 'rei') -> str:
    from datetime import date as _date
    try:
        d = _date.fromisoformat(date_str)
        if d.weekday() == 6:
            return sunday_narrator
        return _WEEKDAY_NARRATOR.get(d.weekday(), 'rei')
    except Exception:
        return 'rei'

def _narrator_tone_hint(narrator: str) -> str:
    return _NARRATOR_TONE.get(narrator, _NARRATOR_TONE['rei'])

# ---------------------------------------------------------------------------
# サンプルデータ
# ---------------------------------------------------------------------------
SAMPLE_DATE = '2026-06-28'
SAMPLE_TRADE_DATE = '2026-06-29'
SAMPLE_YEAR_MONTH = '2026-06'

SAMPLE_DAILY = [
    {'analyst_name': 'rei',   'total_profit_loss': 12400,  'current_balance': 1012400, 'win_count': 2, 'lose_count': 1},
    {'analyst_name': 'mirai', 'total_profit_loss': -8200,  'current_balance': 991800,  'win_count': 1, 'lose_count': 2},
    {'analyst_name': 'ritu',  'total_profit_loss': 31000,  'current_balance': 1031000, 'win_count': 3, 'lose_count': 0},
]

SAMPLE_RANKING = [
    {'analyst_name': 'ritu',  'current_balance': 1031000, 'initial_balance': 1000000},
    {'analyst_name': 'rei',   'current_balance': 1012400, 'initial_balance': 1000000},
    {'analyst_name': 'mirai', 'current_balance': 991800,  'initial_balance': 1000000},
]

SAMPLE_PREV_ENTRIES = [
    {'analyst_name': 'rei',   'stock_code': '7203', 'stock_name': 'トヨタ自動車',   'profit_loss_rate': 1.2,  'buy_amount': 298000},
    {'analyst_name': 'rei',   'stock_code': '6758', 'stock_name': 'ソニーグループ', 'profit_loss_rate': 2.8,  'buy_amount': 312000},
    {'analyst_name': 'mirai', 'stock_code': '9984', 'stock_name': 'ソフトバンクG',  'profit_loss_rate': -1.5, 'buy_amount': 285000},
    {'analyst_name': 'ritu',  'stock_code': '2914', 'stock_name': '日本たばこ産業', 'profit_loss_rate': 3.1,  'buy_amount': 276000},
]

SAMPLE_TODAY_ENTRIES = [
    {'analyst_name': 'rei',   'stock_code': '6501', 'stock_name': '日立製作所',    'buy_amount': 290000, 'prediction_reason': 'MACDゴールデンクロス確認。上昇トレンド継続中。'},
    {'analyst_name': 'rei',   'stock_code': '8306', 'stock_name': '三菱UFJ FG',   'buy_amount': 305000, 'prediction_reason': 'ボリンジャーバンド上抜け。出来高増加を確認。'},
    {'analyst_name': 'mirai', 'stock_code': '4689', 'stock_name': 'LINEヤフー',   'buy_amount': 275000, 'prediction_reason': 'SNS利用者数増加トレンド。話題性高い。'},
    {'analyst_name': 'ritu',  'stock_code': '3382', 'stock_name': 'セブン&アイHD', 'buy_amount': 298000, 'prediction_reason': '今日なんか上がりそうな気がした！'},
]

SAMPLE_CUMULATIVE_MVP = [
    {'analyst_name': 'ritu',  'mvp_count': 3, 'win_count': 2, 'cumulative_profit_loss': 85000},
    {'analyst_name': 'rei',   'mvp_count': 2, 'win_count': 3, 'cumulative_profit_loss': 62000},
    {'analyst_name': 'mirai', 'mvp_count': 1, 'win_count': 1, 'cumulative_profit_loss': -12000},
]

SAMPLE_MORNING_POST_URL = 'https://example.com/2026/06/29/morning-strategy/'
# 日曜記事のナレーター：本番では前週1位キャラをDBから取得するが、
# プレビューはサンプルデータの1位キャラを手動で指定する
SAMPLE_SUNDAY_NARRATOR = SAMPLE_RANKING[0]['analyst_name']  # 現在のサンプルでは ritu

# ---------------------------------------------------------------------------
# 画像URL設定（未設定 or 空文字の場合は非表示）
# ---------------------------------------------------------------------------
SCENE_IMAGES = {
    'morning_scene': os.getenv('IMG_MORNING_SCENE', ''),   # 朝の作戦会議 3人集合画像
    'evening_scene': os.getenv('IMG_EVENING_SCENE', ''),   # 夜の反省会 3人集合画像
    'rei':   os.getenv('IMG_REI', ''),                      # 玲のキャラ画像
    'mirai': os.getenv('IMG_MIRAI', ''),                    # みらいのキャラ画像
    'ritu':  os.getenv('IMG_RITU', ''),                     # 律のキャラ画像
}

def _scene_image_html(url: str, alt: str, css_class: str = 'scene-image',
                      image_type: str = '') -> str:
    if url:
        return f'<div class="{css_class}"><img src="{url}" alt="{alt}"></div>\n'
    label = {
        'morning_scene':          '☀️ 朝の作戦会議 3人集合画像（自動生成）',
        'morning_sub_scene':      '💬 今朝の3人 サブ画像（自動生成）',
        'hero_scene':             '⭐ 今日の主役キャラ画像（自動生成）',
        'night_reflection_scene': '🌙 今日の反省会 3人集合画像（自動生成）',
        'highlight_scene':        '✨ 今日の名場面 挿絵（自動生成）',
    }.get(image_type, f'🖼️ {alt}（自動生成）')
    return (
        f'<div class="{css_class} scene-image-placeholder">'
        f'<span class="scene-placeholder-label">{label}</span>'
        f'</div>\n'
    )

# ---------------------------------------------------------------------------
# キャラクター定義（blog_generator.py と同じ）
# ---------------------------------------------------------------------------
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

RANK_MEDAL = {1: '🥇', 2: '🥈', 3: '🥉'}
RANK_BADGE_CLASS = {1: 'rank-badge-1', 2: 'rank-badge-2', 3: 'rank-badge-3'}

DISCLAIMER = (
    '<div class="disclaimer-box">'
    'この記事はAIキャラクターによる仮想投資シミュレーションです。<br>'
    '実際の売買を推奨するものではありません。<br>'
    '投資判断はご自身の責任で行ってください。'
    '</div>'
)

BATTLE_CSS = '''<style>
/* ベース */
.battle-article{max-width:860px;margin:0 auto;color:#3f3446;line-height:1.9;font-family:'Hiragino Kana Gothic Pro','Meiryo',sans-serif;}

/* ノート紙風背景 */
.battle-article{
  background-image: repeating-linear-gradient(transparent, transparent 27px, #f0e8f0 28px);
  background-size: 100% 28px;
  padding: 0 8px;
}

/* ヒーローヘッダー */
.battle-hero{background:linear-gradient(135deg,#fff7fb,#f3f8ff);border:1px solid #f0ddea;border-radius:24px;padding:28px 24px;margin-bottom:28px;box-shadow:0 10px 30px rgba(120,80,120,.08);background-image:none;}
.battle-label{display:inline-block;font-size:.82rem;letter-spacing:.08em;color:#9b6b88;background:rgba(255,255,255,.8);border-radius:999px;padding:4px 12px;margin-bottom:8px;border:1px solid #f0ddea;}
.battle-lead{margin:.4em 0 0;color:#7a6b80;font-size:.95rem;}
.battle-article h1{color:#4b3b57;margin:.2em 0;}

/* 見出し */
.battle-article h2{color:#4b3b57;border-bottom:none;margin-top:2.2em;padding-left:.2em;font-size:1.05rem;}
.battle-article h3{color:#4b3b57;margin:.6em 0 .3em;}
.sim-notice{font-size:.9em;color:#666;background:#f9f9f9;border-left:4px solid #e6a6c8;padding:.6em 1em;border-radius:0 8px 8px 0;margin-bottom:1.5em;}
.preview-notice{font-size:.85em;color:#999;background:#fafafa;border:1px dashed #ddd;border-radius:8px;padding:.5em 1em;margin-bottom:1em;text-align:center;}

/* ステッカー風セクションラベル */
.section-label{display:inline-block;font-size:.78rem;letter-spacing:.06em;color:#9b6b88;background:rgba(255,255,255,.9);border-radius:999px;padding:3px 12px;margin-bottom:6px;border:1px solid #f0ddea;box-shadow:0 2px 6px rgba(120,80,120,.07);}

/* キャラクターカード */
.character-card{border-radius:20px;padding:20px;margin:18px 0;box-shadow:0 8px 24px rgba(80,60,90,.08);border:1px solid rgba(255,255,255,.9);background-image:none;}
.character-rei{background:linear-gradient(135deg,#edf6ff,#f8fbff);border-left:6px solid #8fb8e8;}
.character-mirai{background:linear-gradient(135deg,#fff1f6,#fff9fb);border-left:6px solid #f0a4c2;}
.character-ritu{background:linear-gradient(135deg,#fff8d8,#f8f0ff);border-left:6px solid #f5c84c;}
.character-header{display:flex;gap:14px;align-items:center;margin-bottom:12px;}

/* アバタープレースホルダー */
.character-avatar{width:72px;height:72px;border-radius:50%;display:flex;flex-direction:column;align-items:center;justify-content:center;overflow:hidden;flex-shrink:0;}
.placeholder-rei{background:linear-gradient(135deg,#d6eaff,#eaf3ff);border:3px solid #8fb8e8;}
.placeholder-mirai{background:linear-gradient(135deg,#ffd6e8,#fff0f6);border:3px solid #f0a4c2;}
.placeholder-ritu{background:linear-gradient(135deg,#fff0a0,#f8e8ff);border:3px solid #f5c84c;}
.avatar-icon{font-size:1.6rem;line-height:1;}
.avatar-name{font-size:.65rem;color:#7a6b80;margin-top:2px;}
.character-name::before{margin-right:4px;}
.character-rei .character-name::before{content:"👓";}
.character-mirai .character-name::before{content:"🌸";}
.character-ritu .character-name::before{content:"🎲";}
.character-role{margin:0;font-size:.85rem;color:#7a6b80;}
.result-score{font-size:1.8rem;font-weight:800;margin:10px 0 2px;}
.result-score.plus{color:#d85f8b;}
.result-score.minus{color:#5c7fc4;}
.result-meta{margin:0 0 12px;color:#6f6372;font-size:.9rem;}
.character-balloon{position:relative;background:rgba(255,255,255,.88);border-radius:16px;padding:12px 16px;margin-top:10px;font-size:.93rem;}

/* 今日の主役カード */
.today-hero{border-radius:20px;padding:22px 20px;margin:18px 0;box-shadow:0 10px 28px rgba(80,60,90,.09);}
.today-hero.character-rei{background:linear-gradient(135deg,#ddeeff,#edf6ff);}
.today-hero.character-mirai{background:linear-gradient(135deg,#ffe4f0,#fff5f9);}
.today-hero.character-ritu{background:linear-gradient(135deg,#fff3b0,#fff8e0);}

/* 作戦カード */
.strategy-card{border-radius:20px;padding:20px;margin:18px 0;box-shadow:0 8px 24px rgba(80,60,90,.08);background-image:none;}
.strategy-card-header{display:flex;gap:14px;align-items:center;margin-bottom:14px;}
.entry-chip-list{display:flex;flex-wrap:wrap;gap:8px;margin:10px 0;}
.entry-chip{background:rgba(255,255,255,.85);border-radius:12px;padding:8px 12px;font-size:.88rem;display:flex;align-items:center;gap:8px;box-shadow:0 2px 8px rgba(80,60,90,.06);border:1px solid rgba(200,180,210,.3);}
.stock-code{font-size:.75rem;color:#9b6b88;background:#f6eef6;border-radius:6px;padding:2px 6px;}
.amount{font-size:.78rem;color:#7a6b80;}
.strategy-reason{font-size:.88rem;color:#6a5a72;background:rgba(255,255,255,.6);border-radius:10px;padding:8px 12px;margin:10px 0;border-left:3px solid rgba(180,150,190,.4);}
.strategy-total{display:inline-block;margin:4px 0 8px;padding:4px 10px;border-radius:999px;background:rgba(255,255,255,.82);color:#7a6b80;font-size:.82rem;border:1px solid rgba(200,180,210,.35);box-shadow:0 2px 8px rgba(80,60,90,.04);}
.strategy-total strong{color:#4b3b57;}
/* シーン画像 */
.scene-image{margin:14px 0;border-radius:18px;overflow:hidden;box-shadow:0 8px 24px rgba(80,60,90,.10);}
.scene-image img{width:100%;height:auto;display:block;}
.scene-image-main{margin:16px 0 20px;}
.scene-image-sub{margin:10px 0 16px;}
.hero-image{margin:12px 0 16px;max-width:420px;}
.hero-image img{border-radius:16px;}
.scene-image-placeholder{display:flex;align-items:center;justify-content:center;min-height:80px;background:repeating-linear-gradient(45deg,#f8f4fc,#f8f4fc 8px,#f2edf8 8px,#f2edf8 16px);border:2px dashed #d8c8e8;border-radius:16px;box-shadow:none;}
.scene-placeholder-label{font-size:.82rem;color:#a088b0;letter-spacing:.04em;}

/* ランキング */
.ranking-card{display:flex;align-items:center;gap:12px;background:#fff;border-radius:16px;padding:12px 14px;margin:8px 0;box-shadow:0 4px 14px rgba(80,60,90,.06);background-image:none;}
.rank-badge{width:36px;height:36px;border-radius:50%;display:inline-flex;align-items:center;justify-content:center;font-weight:800;font-size:1rem;flex-shrink:0;}
.rank-badge-1{background:#ffe8a3;}
.rank-badge-2{background:#e8e8e8;}
.rank-badge-3{background:#f4d9c6;}
.ranking-inline,.character-inline{display:flex;align-items:flex-start;gap:10px;margin:10px 0;}
.ranking-inline .character-avatar,.character-inline .character-avatar{width:52px;height:52px;}

/* 作戦会議トーク */
.strategy-talk{background:rgba(255,255,255,.7);border-radius:20px;padding:20px 22px;margin:24px 0;box-shadow:0 6px 20px rgba(80,60,90,.06);background-image:none;}
.girls-talk{background:rgba(255,255,255,.7);border-radius:20px;padding:20px 22px;margin:24px 0;box-shadow:0 6px 20px rgba(80,60,90,.06);background-image:none;}
.talk-line{border-radius:12px;padding:10px 14px;margin:6px 0;font-size:.93rem;}
.talk-line.rei{background:#e4f0ff;border-left:4px solid #8fb8e8;}
.talk-line.mirai{background:#ffe8f2;border-left:4px solid #f0a4c2;}
.talk-line.ritu{background:#fff6cc;border-left:4px solid #f5c84c;}

/* 今日の名場面 */
.push-points{background:rgba(255,255,255,.7);border-radius:20px;padding:20px 22px;margin:24px 0;box-shadow:0 6px 20px rgba(80,60,90,.06);background-image:none;}
.push-item{border-radius:12px;padding:10px 14px;margin:6px 0;font-size:.93rem;}
.push-item.rei{background:#e4f0ff;border-left:4px solid #8fb8e8;}
.push-item.mirai{background:#ffe8f2;border-left:4px solid #f0a4c2;}
.push-item.ritu{background:#fff6cc;border-left:4px solid #f5c84c;}

/* 今朝の3人 */
.strategy-talk.morning-three{background:rgba(255,255,255,.7);}

/* ランキング表 */
.battle-table{width:100%;border-collapse:separate;border-spacing:0;overflow:hidden;border-radius:16px;background:#fff;box-shadow:0 6px 18px rgba(80,60,90,.06);margin:.8em 0;background-image:none;}
.battle-table th{background:#f6e8f0;color:#5f4a62;padding:10px 12px;text-align:left;}
.battle-table td{border:none;border-top:1px solid #f0e7ee;padding:10px 12px;}

/* 導線・次回フック */
.result-teaser{background:linear-gradient(135deg,#f3f8ff,#fff7fb);border-radius:16px;padding:16px 20px;margin:24px 0;text-align:center;border:1px solid #e0e8f5;font-size:.93rem;color:#4b3b57;background-image:none;}
.next-hook{background:linear-gradient(135deg,#fff7fb,#f3f8ff);border-radius:16px;padding:16px 20px;margin:24px 0;font-size:.93rem;color:#4b3b57;border:1px solid #f0ddea;text-align:center;background-image:none;}
.morning-link{background:#f5f0fa;border-radius:12px;padding:10px 16px;margin:14px 0;font-size:.87rem;color:#7a6b80;text-align:center;background-image:none;}

/* MVP記録 */
.cumulative-card{background:#fff;border-radius:16px;padding:12px 16px;margin:8px 0;box-shadow:0 4px 12px rgba(80,60,90,.06);display:flex;align-items:center;gap:10px;background-image:none;}
.mvp-count{font-size:.83rem;color:#7a6b80;}

/* 朝/夜のはじまり */
.day-beginning{border-radius:22px;padding:20px 22px;margin:20px 0;box-shadow:0 6px 18px rgba(80,60,90,.07);background-image:none;}
.morning-beginning{background:linear-gradient(135deg,#fff9ee,#fff3e0);border:1px solid #f5ddb0;}
.night-beginning{background:linear-gradient(135deg,#f0f0ff,#e8eaff);border:1px solid #c8c8f0;}
.beginning-text{color:#4b3b57;line-height:2;margin:.6em 0 0;font-size:.97rem;}
.narrator-header{display:flex;align-items:center;gap:10px;margin-bottom:10px;}
.narrator-name{font-size:.88rem;color:#7a6b80;font-weight:600;}
/* 免責 */
.disclaimer-box{font-size:.85rem;color:#7a7280;background:#fafafa;border-radius:14px;padding:14px 16px;margin-top:32px;border:1px solid #eee;background-image:none;}

/* プレビューナビ */
.preview-nav{max-width:860px;margin:0 auto 32px;display:flex;gap:12px;justify-content:center;font-size:.9rem;}
.preview-nav a{background:#f6e8f0;color:#5f4a62;border-radius:999px;padding:6px 18px;text-decoration:none;border:1px solid #f0ddea;}
.preview-nav a:hover{background:#f0d0e4;}
.article-divider{max-width:860px;margin:48px auto;border:none;border-top:2px dashed #f0ddea;}

@media(max-width:640px){
  .battle-hero{padding:20px 16px;border-radius:16px;}
  .character-card,.today-hero,.girls-talk,.strategy-card{padding:16px;}
  .character-avatar{width:60px;height:60px;}
  .result-score{font-size:1.4rem;}
}
</style>'''

# ---------------------------------------------------------------------------
# Gemini呼び出し
# ---------------------------------------------------------------------------
_gemini_model = None

def _get_gemini():
    global _gemini_model
    api_key = os.getenv('GEMINI_STOCK_API_KEY') or os.getenv('GEMINI_API_KEY')
    if not api_key:
        return None
    if _gemini_model is None:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        _gemini_model = genai.GenerativeModel('gemini-2.0-flash')
    return _gemini_model

def _ai(system: str, user: str, fallback: str) -> str:
    model = _get_gemini()
    if not model:
        return fallback  # キー未設定時はフォールバック文をそのまま使う
    try:
        response = model.generate_content(f'system: {system}\nuser: {user}')
        return response.text.strip()
    except Exception:
        return fallback  # エラー時もフォールバック文に切り替え

def _ai_raw(system: str, user: str) -> str:
    """JSON取得用（失敗時はNone）"""
    model = _get_gemini()
    if not model:
        return None
    try:
        response = model.generate_content(f'system: {system}\nuser: {user}')
        return response.text.strip()
    except Exception:
        return None

# ---------------------------------------------------------------------------
# アバターHTML（プレビューはキャラ別プレースホルダー）
# ---------------------------------------------------------------------------
AVATAR_ICONS = {'rei': '👓', 'mirai': '🌸', 'ritu': '🎲'}

def _avatar_html(name: str, size: str = '72px') -> str:
    profile = ANALYST_PROFILES[name]
    icon = AVATAR_ICONS.get(name, '👤')
    return (
        f'<div class="character-avatar placeholder-{name}" style="width:{size};height:{size};">'
        f'<span class="avatar-icon">{icon}</span>'
        f'<span class="avatar-name">{profile["name_short"]}</span>'
        f'</div>'
    )

def get_expression(rate: float) -> str:
    if rate >= 5:  return 'victory'
    if rate >= 0:  return 'happy'
    if rate >= -5: return 'worried'
    return 'defeated'

# ---------------------------------------------------------------------------
# ナレーション生成（夜記事用）
# ---------------------------------------------------------------------------
def generate_lead() -> str:
    summary = ', '.join(
        f'{ANALYST_PROFILES[d["analyst_name"]]["name_short"]}が'
        f'{"+" if d["total_profit_loss"]>=0 else ""}{d["total_profit_loss"]:,}円'
        for d in SAMPLE_DAILY
    )
    return _ai(
        system=PromptLoader.base_system('投資シミュレーションブログの編集者'),
        user=(f'今日の仮想投資バトルの結果は以下でした：{summary}。\n'
              f'読者が「今日もドラマあったな」と感じるような、1〜2文のリード文を書いてください。'
              f'キャラクターの名前を入れてください。'),
        fallback=summary,
    )

def generate_hero_intro(hero: dict) -> str:
    name = hero['analyst_name']
    profile = ANALYST_PROFILES[name]
    profit = hero['total_profit_loss']
    sign = '+' if profit >= 0 else ''
    win, lose = hero['win_count'], hero['lose_count']
    return _ai(
        system=PromptLoader.character_system(name, profile['name_jp']),
        user=(f'今日の成績は{sign}{profit:,}円（{win}勝{lose}敗）でした。'
              f'今日の主役として紹介される1文のコメントを返してください。'),
        fallback=f'今日は{sign}{profit:,}円。{win}勝{lose}敗でした。',
    )

def generate_girls_talk() -> list:
    fallback = [
        {'name': 'rei',   'line': '今日も流れをうまく拾えたと思います。'},
        {'name': 'mirai', 'line': 'えー、私だけ負けてるんだけど〜！明日は絶対巻き返す！'},
        {'name': 'ritu',  'line': 'きたきたきた〜！今日の律、最強だったんだけど！？'},
    ]
    summary = '\n'.join(
        f'{ANALYST_PROFILES[d["analyst_name"]]["name_jp"]}: '
        f'{"+" if d["total_profit_loss"]>=0 else ""}{d["total_profit_loss"]:,}円'
        f'（{d["win_count"]}勝{d["lose_count"]}敗）'
        for d in SAMPLE_DAILY
    )
    ranking_txt = ', '.join(
        f'{i+1}位: {ANALYST_PROFILES[r["analyst_name"]]["name_short"]}'
        for i, r in enumerate(SAMPLE_RANKING)
    )
    raw = _ai_raw(
        system=PromptLoader.base_system() + f'\n\n## 会話生成ガイドライン\n\n{PromptLoader.talk()}',
        user=(f'今日の仮想投資結果：\n{summary}\n順位：{ranking_txt}\n\n'
              f'3人が今日の結果について1行ずつ会話する「反省会」シーンを書いてください。'
              f'各キャラが自分の成績だけでなく、他2人の成績と比較しながら話すようにしてください。\n'
              f'（例：勝ったキャラは負けたキャラをいじる、負けたキャラは勝ったキャラに悔しがる）\n'
              f'以下のJSON配列形式で返してください（他の文字は不要）：\n'
              f'[{{"name":"rei","line":"..."}},{{"name":"mirai","line":"..."}},{{"name":"ritu","line":"..."}}]'),
    )
    if raw:
        try:
            m = re.search(r'\[.*?\]', raw, re.DOTALL)
            if m:
                parsed = json.loads(m.group())
                if isinstance(parsed, list) and len(parsed) == 3:
                    return parsed
        except Exception:
            pass
    return fallback

def generate_next_hook(narrator: str = 'rei') -> str:
    """「次回へのひとこと」をAIで生成。曜日担当ナレーターの口調で地の文として書く。"""
    fallback_by_narrator = {
        'rei': '明日も3人の勝負を、静かに見守ってください。',
        'mirai': '明日もみんなの勝負、一緒に応援しましょう！',
        'ritu': '明日もなんか面白いことありそうじゃん？また見てね！',
    }
    fallback = fallback_by_narrator.get(narrator, fallback_by_narrator['rei'])
    ranking_txt = ', '.join(
        ANALYST_PROFILES[r['analyst_name']]['name_short'] for r in SAMPLE_RANKING
    )
    tone = _narrator_tone_hint(narrator)
    return _ai(
        system=PromptLoader.base_system() + f'\n\n## キャラクタープロファイル\n\n{PromptLoader.character_profile()}',
        user=(f'現在の順位: {ranking_txt}の順。\n'
              f'【口調・語り手の指定】{tone}\n'
              f'読者が明日も見に来たくなるような、1〜2文の締めの地の文を書いてください。'
              f'キャラ名を入れて、連載感を出してください。'
              f'地の文のみ（「玲：」などのセリフ形式は禁止）。'),
        fallback=fallback,
    )

# ---------------------------------------------------------------------------
# ナレーション生成（朝記事用）
# ---------------------------------------------------------------------------
def generate_morning_opening() -> dict:
    """朝記事用 subtitle/lead/talk_lines を生成する"""
    fallback = {
        'subtitle': '今日の3人のエントリー',
        'lead': '今日も3人の勝負が始まります。',
        'talk_lines': [
            {'name': 'rei',   'line': 'テクニカルで流れを拾っていきます。'},
            {'name': 'mirai', 'line': '今日もいい銘柄見つけたよ！'},
            {'name': 'ritu',  'line': 'きたきたきた！今日もノリで行くよ！'},
        ],
    }
    entries_summary = '\n'.join(
        f'{ANALYST_PROFILES[e["analyst_name"]]["name_jp"]}: {e["stock_name"]}（{e["stock_code"]}）{e["prediction_reason"]}'
        for e in SAMPLE_TODAY_ENTRIES
    )
    ranking_txt = ', '.join(
        f'{i+1}位: {ANALYST_PROFILES[r["analyst_name"]]["name_short"]}（{r["current_balance"]:,}円）'
        for i, r in enumerate(SAMPLE_RANKING)
    )
    raw = _ai_raw(
        system=PromptLoader.base_system()
            + f'\n\n## 記事ガイドライン\n\n{PromptLoader.prediction_article()}'
            + f'\n\n## 会話生成ガイドライン\n\n{PromptLoader.talk()}',
        user=(f'今日のエントリー：\n{entries_summary}\n'
              f'現在の順位：{ranking_txt}\n\n'
              f'朝の作戦会議記事用のオープニングコンテンツを作ってください。\n'
              f'以下のJSON形式で返してください（他の文字は不要）：\n'
              f'{{"subtitle":"玲は堅実、律は今日もノリ勝負（例）","lead":"リード文1〜2文",'
              f'"talk_lines":[{{"name":"rei","line":"..."}},{{"name":"mirai","line":"..."}},{{"name":"ritu","line":"..."}}]}}'),
    )
    if raw:
        try:
            m = re.search(r'\{.*\}', raw, re.DOTALL)
            if m:
                parsed = json.loads(m.group())
                if isinstance(parsed, dict) and 'subtitle' in parsed:
                    return parsed
        except Exception:
            pass
    return fallback

def generate_morning_three() -> list:
    fallback = [
        {'name': 'rei',   'line': 'テクニカルで流れを拾っていきます。'},
        {'name': 'mirai', 'line': '今日もいい銘柄見つけたよ！'},
        {'name': 'ritu',  'line': 'きたきたきた！今日もノリで行くよ！'},
    ]
    entries_summary = '\n'.join(
        f'{ANALYST_PROFILES[e["analyst_name"]]["name_jp"]}: {e["stock_name"]}（{e["stock_code"]}）'
        for e in SAMPLE_TODAY_ENTRIES
    )
    ranking_txt = ', '.join(
        f'{i+1}位: {ANALYST_PROFILES[r["analyst_name"]]["name_short"]}（{r["current_balance"]:,}円）'
        for i, r in enumerate(SAMPLE_RANKING)
    )
    raw = _ai_raw(
        system=PromptLoader.base_system() + f'\n\n## 会話生成ガイドライン\n\n{PromptLoader.talk()}',
        user=(f'今日のエントリー：\n{entries_summary}\n'
              f'現在の順位：{ranking_txt}\n\n'
              f'「今朝の3人」コーナー用のセリフを生成してください。'
              f'各キャラが現在の順位・自分の選択・他2人の選択への反応を踏まえて一言ずつ話します。\n'
              f'以下のJSON配列形式で返してください（他の文字は不要）：\n'
              f'[{{"name":"rei","line":"..."}},{{"name":"mirai","line":"..."}},{{"name":"ritu","line":"..."}}]'),
    )
    if raw:
        try:
            m = re.search(r'\[.*?\]', raw, re.DOTALL)
            if m:
                parsed = json.loads(m.group())
                if isinstance(parsed, list) and len(parsed) == 3:
                    return parsed
        except Exception:
            pass
    return fallback

def generate_push_points() -> list:
    # フォールバックは SAMPLE_DAILY の勝敗に合わせた情景描写にしておく
    # （rei: 2勝1敗 / mirai: 1勝2敗 / ritu: 3勝0敗）
    fallback = [
        {'name': 'rei',   'point': 'メガネを直しながら、静かに今日のプラスを分析ノートへ書き留める。'},
        {'name': 'mirai', 'point': '悔しそうに唇をとがらせながら、明日の銘柄をスマホで検索している。'},
        {'name': 'ritu',  'point': '机に身を乗り出して、今日の3勝を全力で喜んでいる。'},
    ]
    summary = '\n'.join(
        f'{ANALYST_PROFILES[d["analyst_name"]]["name_jp"]}: '
        f'{"+" if d["total_profit_loss"]>=0 else ""}{d["total_profit_loss"]:,}円'
        f'（{d["win_count"]}勝{d["lose_count"]}敗）'
        for d in SAMPLE_DAILY
    )
    raw = _ai_raw(
        system=PromptLoader.base_system() + f'\n\n## ハイライト生成ガイドライン\n\n{PromptLoader.talk()}',
        user=(f'今日の仮想投資結果：\n{summary}\n\n'
              f'今日のキャラクターそれぞれの「ハイライト」を1文ずつ書いてください。'
              f'その日の名場面・情景を自然な一文で切り取ってください（推し説明ではなくシーン描写）。\n'
              f'以下のJSON配列形式で返してください（他の文字は不要）：\n'
              f'[{{"name":"rei","point":"..."}},{{"name":"mirai","point":"..."}},{{"name":"ritu","point":"..."}}]'),
    )
    if raw:
        try:
            m = re.search(r'\[.*?\]', raw, re.DOTALL)
            if m:
                parsed = json.loads(m.group())
                if isinstance(parsed, list) and len(parsed) == 3:
                    return parsed
        except Exception:
            pass
    return fallback

# ---------------------------------------------------------------------------
# セクション生成（共通）
# ---------------------------------------------------------------------------
def section_today_hero(hero: dict, intro: str) -> str:
    name = hero['analyst_name']
    profile = ANALYST_PROFILES[name]
    hero_img = _scene_image_html(SCENE_IMAGES.get(name, ''), f'{profile["name_short"]}', 'scene-image hero-image', 'hero_scene')
    return (
        f'<section class="today-hero character-{name}">\n'
        f'  <p class="section-label">今日の主役</p>\n'
        f'  <h2>{profile["name_short"]}が今日の主役！</h2>\n'
        f'{hero_img}'
        f'  <p>{intro}</p>\n'
        f'</section>\n'
    )

def section_result() -> str:
    first_balance = SAMPLE_RANKING[0]['current_balance']
    ranking_map = {r['analyst_name']: i + 1 for i, r in enumerate(SAMPLE_RANKING)}
    total = len(SAMPLE_RANKING)

    html = f'<h2>🏁 今日の勝負結果 <span style="font-size:.8em;font-weight:normal;">{SAMPLE_DATE}</span></h2>\n'
    for d in SAMPLE_DAILY:
        name = d['analyst_name']
        profile = ANALYST_PROFILES[name]
        profit = d['total_profit_loss']
        balance = d['current_balance']
        win, lose = d['win_count'], d['lose_count']
        sign = '+' if profit >= 0 else ''
        score_class = 'plus' if profit >= 0 else 'minus'

        pl_rates = [e['profit_loss_rate'] for e in SAMPLE_PREV_ENTRIES if e['analyst_name'] == name]
        avg_rate = sum(pl_rates) / len(pl_rates) if pl_rates else 0
        expression = get_expression(avg_rate)

        rank = ranking_map.get(name, total)
        gap = first_balance - balance
        rank_ctx = '現在1位です。' if rank == 1 else f'現在{rank}位（1位との差：{gap:,}円）です。'

        comment = _ai(
            system=PromptLoader.character_system(name, profile['name_jp']),
            user=(f'今日の結果は{sign}{profit:,}円（{win}勝{lose}敗）でした。{rank_ctx}'
                  f'キャラクターらしい短いコメントを1〜2文で。順位にも触れてください。'),
            fallback=f'今日は{sign}{profit:,}円でした。',
        )
        html += (
            f'<div class="character-card character-{name}">\n'
            f'  <div class="character-header">\n'
            f'    {_avatar_html(name)}\n'
            f'    <div>\n'
            f'      <h3 style="margin:0 0 2px;">{profile["name_jp"]}</h3>\n'
            f'      <p class="character-role">{profile["role"]}</p>\n'
            f'    </div>\n'
            f'  </div>\n'
            f'  <div class="result-score {score_class}">{sign}{profit:,}円</div>\n'
            f'  <p class="result-meta">{win}勝{lose}敗 / 現在の資産 {balance:,}円</p>\n'
            f'  <div class="character-balloon">{comment}</div>\n'
            f'</div>\n'
        )
    return html

def generate_ranking_narrative() -> list:
    """各キャラのランキングコメントをAIで生成する（順位＋今日の結果感情を含む）。"""
    daily_map = {d['analyst_name']: d for d in SAMPLE_DAILY}
    ranking_summary = '\n'.join(
        f'{i+1}位: {ANALYST_PROFILES.get(r["analyst_name"],{}).get("name_short","")}（'
        f'今日{"+" if daily_map.get(r["analyst_name"],{}).get("total_profit_loss",0)>=0 else ""}'
        f'{daily_map.get(r["analyst_name"],{}).get("total_profit_loss",0):,}円）'
        for i, r in enumerate(SAMPLE_RANKING)
    )
    raw = _ai_raw(
        system=PromptLoader.base_system() + f'\n\n## キャラクタープロファイル\n\n{PromptLoader.character_profile()}',
        user=(
            f'今日のランキングと結果：\n{ranking_summary}\n\n'
            f'各キャラクターのランキングコメントを生成してください。\n'
            f'・順位だけで終わらせず、今日の結果に合わせたキャラの感情を1文で入れてください\n'
            f'・長くしすぎない（1文以内）\n'
            f'・キャラの口調に合わせてください\n'
            f'・コメント本文の先頭にキャラ名（「律：」「玲：」など）を入れないでください（HTML側で表示します）\n'
            f'・投資助言・断言表現は禁止です\n'
            f'以下のJSON配列形式で返してください（他の文字は不要）：\n'
            f'[{{"name":"rei","comment":"..."}},{{"name":"mirai","comment":"..."}},{{"name":"ritu","comment":"..."}}]'
        ),
    )
    if raw:
        try:
            m = re.search(r'\[.*?\]', raw, re.DOTALL)
            if m:
                parsed = json.loads(m.group())
                if isinstance(parsed, list) and len(parsed) > 0:
                    return parsed
        except Exception:
            pass
    # フォールバック: 順位＋今日の感情を含む簡易コメント
    fallback = []
    for i, r in enumerate(SAMPLE_RANKING):
        name = r['analyst_name']
        profile = ANALYST_PROFILES.get(name, {})
        short = profile.get('name_short', name)
        d = daily_map.get(name, {})
        profit = d.get('total_profit_loss', 0)
        rank = i + 1
        if rank == 1:
            mood = 'ご機嫌' if profit >= 0 else '首位キープも複雑な表情'
        elif rank == 2:
            mood = '静かに追走中' if profit >= 0 else '差を意識しながらも落ち着いている'
        else:
            mood = '悔しいが明日に気持ちを向けている'
        fallback.append({'name': name, 'comment': f'{mood}。'})
    return fallback


def section_ranking() -> str:
    html = '<h2>🏆 今月のランキング</h2>\n'
    total = len(SAMPLE_RANKING)
    first_balance = SAMPLE_RANKING[0]['current_balance']

    for i, r in enumerate(SAMPLE_RANKING):
        name = r['analyst_name']
        profile = ANALYST_PROFILES[name]
        diff = r['current_balance'] - r['initial_balance']
        sign = '+' if diff >= 0 else ''
        rank = i + 1
        badge_class = RANK_BADGE_CLASS.get(rank, 'rank-badge-n')
        medal = RANK_MEDAL.get(rank, str(rank))
        html += (
            f'<div class="ranking-card">\n'
            f'  <span class="rank-badge {badge_class}">{medal}</span>\n'
            f'  {_avatar_html(name, "48px")}\n'
            f'  <div>\n'
            f'    <strong>{profile["name_jp"]}</strong><br>\n'
            f'    <span style="font-size:1.05em;font-weight:700;">{r["current_balance"]:,}円</span>'
            f'    <span style="font-size:.88em;color:#888;"> ({sign}{diff:,}円)</span>\n'
            f'  </div>\n'
            f'</div>\n'
        )

    narrative = generate_ranking_narrative()
    narrative_map = {item['name']: item.get('comment', '') for item in narrative}
    for i, r in enumerate(SAMPLE_RANKING):
        name = r['analyst_name']
        profile = ANALYST_PROFILES[name]
        gap = first_balance - r['current_balance']
        rank = i + 1
        comment = narrative_map.get(name, '')
        if not comment:
            rank_ctx = f'{total}人中1位です。' if rank == 1 else f'{total}人中{rank}位（差：{gap:,}円）です。'
            comment = _ai(
                system=PromptLoader.character_system(name, profile['name_jp']),
                user=(f'{rank_ctx}順位についてキャラクターらしい一言を1文で。'),
                fallback=f'{rank}位です。',
            )
        html += (
            f'<div class="ranking-inline">\n'
            f'  {_avatar_html(name, "56px")}\n'
            f'  <div class="character-balloon" style="flex:1;">'
            f'<strong>{profile["name_jp"]}</strong>：{comment}</div>\n'
            f'</div>\n'
        )
    return html

def section_today_entry() -> str:
    html = f'<h2>📒 今日の作戦ノート <span style="font-size:.8em;font-weight:normal;">{SAMPLE_TRADE_DATE}</span></h2>\n'
    for analyst_name, profile in ANALYST_PROFILES.items():
        ae = [e for e in SAMPLE_TODAY_ENTRIES if e['analyst_name'] == analyst_name]
        if not ae:
            continue
        icon = AVATAR_ICONS.get(analyst_name, '👤')
        short = profile['name_short']
        name_jp = profile['name_jp']
        role = profile['role']
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
        reasons = []
        total = 0
        for e in ae:
            approx_man = round(e['buy_amount'] / 10000)
            total += e['buy_amount']
            html += (
                f'    <div class="entry-chip">'
                f'<span class="stock-code">{e["stock_code"]}</span>'
                f'<strong>{e["stock_name"]}</strong>'
                f'<span class="amount">約{approx_man}万円</span>'
                f'</div>\n'
            )
            reasons.append(e.get('prediction_reason', ''))
        html += '  </div>\n'
        total_man = round(total / 10000)
        html += f'  <div class="strategy-total">今日の作戦予算：<strong>合計 約{total_man}万円</strong></div>\n'
        reason_text = '／'.join(r for r in reasons if r)
        if reason_text:
            html += f'  <div class="strategy-reason">{reason_text}</div>\n'

        stocks = [e['stock_name'] for e in ae]
        comment = _ai(
            system=PromptLoader.character_system(analyst_name, profile['name_jp']),
            user=(f'今日のエントリー銘柄は{"、".join(stocks)}です。'
                  f'選んだ理由や意気込みをキャラクターらしく1〜2文で。'),
            fallback=f'今日は{"、".join(stocks)}に注目しています。',
        )
        html += (
            f'  <div class="character-balloon">{comment}</div>\n'
            f'</section>\n'
        )
    return html

def section_strategy_talk(talk_lines: list) -> str:
    html = '<section class="strategy-talk">\n<h2>☀️ 今日の作戦会議</h2>\n'
    html += _scene_image_html(SCENE_IMAGES['morning_scene'], '朝の作戦会議をする3人', 'scene-image scene-image-main', 'morning_scene')
    for line in talk_lines:
        name = line.get('name', '')
        text = line.get('line', '')
        short = ANALYST_PROFILES.get(name, {}).get('name_short', name)
        html += f'<div class="talk-line {name}">{short}「{text}」</div>\n'
    html += '</section>\n'
    return html

def section_morning_three(talk_lines: list) -> str:
    html = '<section class="strategy-talk morning-three">\n<h2>💬 今朝の3人</h2>\n'
    html += _scene_image_html('', '今朝の3人', 'scene-image scene-image-sub', 'morning_sub_scene')
    for line in talk_lines:
        name = line.get('name', '')
        text = line.get('line', '')
        short = ANALYST_PROFILES.get(name, {}).get('name_short', name)
        html += f'<div class="talk-line {name}">{short}「{text}」</div>\n'
    html += '</section>\n'
    return html

def generate_result_teaser(narrator: str = 'rei') -> str:
    """朝記事末尾の結果予告をAIで生成。曜日担当ナレーターの口調で地の文として書く。"""
    fallback_by_narrator = {
        'rei': '今日の勝負の結果は、今夜22時ごろに発表予定です。お楽しみに。',
        'mirai': '今夜の結果、一緒に待ちましょう！22時ごろに発表します！',
        'ritu': '今夜の結果は22時ごろ発表するよ〜！どうなるか楽しみじゃん？',
    }
    fallback = fallback_by_narrator.get(narrator, fallback_by_narrator['rei'])
    stocks = [e['stock_name'] for e in SAMPLE_TODAY_ENTRIES]
    ranking_txt = ', '.join(
        ANALYST_PROFILES[r['analyst_name']]['name_short'] for r in SAMPLE_RANKING
    )
    tone = _narrator_tone_hint(narrator)
    return _ai(
        PromptLoader.base_system() + f'\n\n## キャラクタープロファイル\n\n{PromptLoader.character_profile()}',
        (
            f'今日のエントリー銘柄：{", ".join(stocks)}\n'
            f'現在の順位：{ranking_txt}\n\n'
            f'朝記事の末尾に置く「今夜の結果予告」の一言を1〜2文で書いてください。\n'
            f'【口調・語り手の指定】{tone}\n'
            f'・今夜22時ごろ結果発表予定であることを自然に伝えてください\n'
            f'・読者が夜も見に来たくなるような軽いひと押しにしてください\n'
            f'・地の文として書いてください（「玲：」などのセリフ形式は禁止）\n'
            f'・投資助言や断言表現は禁止です'
        ),
        fallback,
    )


def section_result_teaser(text: str, narrator: str = 'rei') -> str:
    avatar = _narrator_avatar_html(narrator)
    return f'<div class="result-teaser">{avatar}{text}</div>\n'

def section_morning_link(url: str = None) -> str:
    if not url:
        return ''
    return f'<div class="morning-link">📋 <a href="{url}">朝の作戦会議はこちら</a></div>\n'

def section_girls_talk(talk_lines: list) -> str:
    html = '<section class="girls-talk">\n<h2>🌙 今日の反省会</h2>\n'
    html += _scene_image_html(SCENE_IMAGES['evening_scene'], '夜の反省会をする3人', 'scene-image scene-image-main', 'night_reflection_scene')
    for line in talk_lines:
        name = line.get('name', '')
        text = line.get('line', '')
        short = ANALYST_PROFILES.get(name, {}).get('name_short', name)
        html += f'<div class="talk-line {name}">{short}「{text}」</div>\n'
    html += '</section>\n'
    return html

def section_push_points(push_points: list) -> str:
    html = '<section class="push-points">\n<h2>✨ 今日の名場面</h2>\n'
    html += _scene_image_html('', '今日の名場面', 'scene-image scene-image-sub', 'highlight_scene')
    for item in push_points:
        name = item.get('name', '')
        point = item.get('point', '')
        short = ANALYST_PROFILES.get(name, {}).get('name_short', name)
        html += f'<div class="push-item {name}">{short}：{point}</div>\n'
    html += '</section>\n'
    return html

def section_cumulative() -> str:
    html = '<h2>🏅 MVP記録</h2>\n'
    for i, r in enumerate(SAMPLE_CUMULATIVE_MVP):
        name_jp = ANALYST_PROFILES[r['analyst_name']]['name_jp']
        medal = RANK_MEDAL.get(i + 1, '🏅')
        html += (
            f'<div class="cumulative-card">\n'
            f'  <span style="font-size:1.4rem;">{medal}</span>\n'
            f'  <div>\n'
            f'    <strong>{name_jp}</strong><br>\n'
            f'    <span class="mvp-count">MVP {r["mvp_count"]}回 / '
            f'月間優勝 {r["win_count"]}回 / '
            f'累計損益 {r["cumulative_profit_loss"]:+,}円</span>\n'
            f'  </div>\n'
            f'</div>\n'
        )
    return html

def generate_morning_beginning(narrator: str = 'rei') -> str:
    """「☕ 今朝のはじまり」の本文をAIで生成。曜日担当ナレーターの口調で地の文として書く。"""
    fallback_by_narrator = {
        'rei': (
            '昨日は律さんが大きく前に出て、私は落ち着いて積み上げる展開でした。'
            'みらいは少し悔しい朝かもしれませんが、今朝も3人それぞれの作戦が始まります。'
        ),
        'mirai': (
            '昨日は律が大暴れでしたね！悔しいけど、今日はここから巻き返します。'
            'それぞれの作戦、一緒に見ていきましょう！'
        ),
        'ritu': (
            '昨日の結果はさておき、今日も勝負の朝です。週末前ラスト、なんか面白いことありそうじゃん？'
            '3人の作戦を見ていきます！'
        ),
    }
    fallback = fallback_by_narrator.get(narrator, fallback_by_narrator['rei'])
    prev_summary = '前営業日の結果：' + '、'.join(
        f'{ANALYST_PROFILES[d["analyst_name"]]["name_short"]}が'
        f'{"+" if d["total_profit_loss"] >= 0 else ""}{d["total_profit_loss"]:,}円'
        f'（{d["win_count"]}勝{d["lose_count"]}敗）'
        for d in SAMPLE_DAILY
    )
    ranking_txt = '現在の月間順位：' + '、'.join(
        f'{i+1}位: {ANALYST_PROFILES[r["analyst_name"]]["name_short"]}'
        for i, r in enumerate(SAMPLE_RANKING)
    )
    tone = _narrator_tone_hint(narrator)
    return _ai(
        PromptLoader.base_system() + f'\n\n## キャラクタープロファイル\n\n{PromptLoader.character_profile()}',
        (
            f'{prev_summary}\n{ranking_txt}\n\n'
            f'朝記事「☕ 今朝のはじまり」の本文を2〜4文で書いてください。\n'
            f'【口調・語り手の指定】{tone}\n'
            f'前日の流れと今の順位をふまえた3人の今朝の空気を描写し、文末は今日の作戦会議へつなげてください。\n'
            f'地の文のみ（「玲：」などのセリフ形式は禁止）。'
        ),
        fallback,
    )


def generate_night_beginning(narrator: str = 'rei') -> str:
    """「🌙 夜のはじまり」の本文をAIで生成。曜日担当ナレーターの口調で地の文として書く。"""
    fallback_by_narrator = {
        'rei': (
            '今日の勝負が終わって、3人はそれぞれの結果を持ち寄りました。'
            '大きく笑う子もいれば、少し悔しそうに手帳を握る子もいます。'
            'まずは、今日いちばん空気を動かした主役から見ていきます。'
        ),
        'mirai': (
            '今日の勝負、結果が出ましたよ！ドキドキしながら数字を確認しました。'
            '笑い声が聞こえた子もいれば、唸り声が聞こえた子もいます。'
            'まずは今日の主役から見ていきましょう！'
        ),
        'ritu': (
            '今日の勝負終わったよ〜！みんなどうだったんだろ？'
            '結果見る前からなんか空気でわかる気がするんだけどね笑。'
            'とりあえず今日いちばん目立ってた子から行くよ！'
        ),
    }
    fallback = fallback_by_narrator.get(narrator, fallback_by_narrator['rei'])
    hero_char = max(SAMPLE_DAILY, key=lambda d: abs(d['total_profit_loss']))
    summary = '\n'.join(
        f'{ANALYST_PROFILES[d["analyst_name"]]["name_short"]}: '
        f'{"+" if d["total_profit_loss"] >= 0 else ""}{d["total_profit_loss"]:,}円 '
        f'（{d["win_count"]}勝{d["lose_count"]}敗）'
        for d in SAMPLE_DAILY
    )
    hero_name = ANALYST_PROFILES[hero_char['analyst_name']]['name_short']
    tone = _narrator_tone_hint(narrator)
    return _ai(
        PromptLoader.base_system() + f'\n\n## キャラクタープロファイル\n\n{PromptLoader.character_profile()}',
        (
            f'今日の仮想投資結果：\n{summary}\n今日の主役候補: {hero_name}\n\n'
            f'夜記事「🌙 夜のはじまり」の本文を2〜4文で書いてください。\n'
            f'【口調・語り手の指定】{tone}\n'
            f'結果の数字はまだ出さず、勝負が終わった直後の3人の空気・表情を描写し、'
            f'文末は「まずは今日の主役から」でつなげてください。\n'
            f'地の文のみ（「玲：」などのセリフ形式は禁止）。'
        ),
        fallback,
    )


def _narrator_avatar_html(narrator: str) -> str:
    profile = ANALYST_PROFILES.get(narrator, {})
    name_jp = profile.get('name_jp', narrator)
    name_short = profile.get('name_short', narrator)
    icons = {'rei': '👓', 'mirai': '🌸', 'ritu': '🎲'}
    icon = icons.get(narrator, '👤')
    return (
        f'<div class="narrator-header">'
        f'<div class="character-avatar placeholder-{narrator}">'
        f'<span class="avatar-icon">{icon}</span>'
        f'<span class="avatar-name">{name_short}</span>'
        f'</div>'
        f'<span class="narrator-name">{name_jp}</span>'
        f'</div>\n'
    )


def section_morning_beginning(text: str, narrator: str = 'rei') -> str:
    return (
        '<section class="day-beginning morning-beginning">\n'
        '<h2>☕ 今朝のはじまり</h2>\n'
        f'{_narrator_avatar_html(narrator)}'
        f'<p class="beginning-text">{text}</p>\n'
        '</section>\n'
    )


def section_night_beginning(text: str, narrator: str = 'rei') -> str:
    return (
        '<section class="day-beginning night-beginning">\n'
        '<h2>🌙 夜のはじまり</h2>\n'
        f'{_narrator_avatar_html(narrator)}'
        f'<p class="beginning-text">{text}</p>\n'
        '</section>\n'
    )


# ---------------------------------------------------------------------------
# HTML組み立て — 朝記事
# ---------------------------------------------------------------------------
def build_morning_html() -> str:
    narrator = get_weekday_narrator(SAMPLE_TRADE_DATE, sunday_narrator=SAMPLE_SUNDAY_NARRATOR)
    print(f'  [朝記事] 今朝のはじまり（ナレーター: {narrator}）...')
    morning_beginning = generate_morning_beginning(narrator)

    print('  [朝記事] オープニング生成中...')
    opening = generate_morning_opening()
    subtitle = opening.get('subtitle', '今日の3人のエントリー')
    lead = opening.get('lead', '今日も3人の勝負が始まります。')
    talk_lines = opening.get('talk_lines', [
        {'name': 'rei',   'line': 'テクニカルで流れを拾っていきます。'},
        {'name': 'mirai', 'line': '今日もいい銘柄見つけたよ！'},
        {'name': 'ritu',  'line': 'きたきたきた！今日もノリで行くよ！'},
    ])

    print('  [朝記事] 今朝の3人...')
    morning_three = generate_morning_three()

    print('  [朝記事] エントリー...')
    s_entry = section_today_entry()

    print(f'  [朝記事] 結果予告（ナレーター: {narrator}）...')
    result_teaser_text = generate_result_teaser(narrator)

    title = f'【AI投資バトル】{SAMPLE_TRADE_DATE} 朝の作戦会議｜{subtitle}'
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
    preview_notice = f'<p class="preview-notice">※ サンプルデータによるプレビュー（朝記事 {SAMPLE_TRADE_DATE}生成）</p>'

    return '\n'.join([
        '<div id="morning">',
        preview_notice,
        hero_html,
        notice,
        section_morning_beginning(morning_beginning, narrator),
        section_strategy_talk(talk_lines),
        s_entry,
        section_morning_three(morning_three),
        section_result_teaser(result_teaser_text, narrator),
        DISCLAIMER,
        '</div>',
    ])

# ---------------------------------------------------------------------------
# HTML組み立て — 夜記事
# ---------------------------------------------------------------------------
def build_evening_html() -> str:
    narrator = get_weekday_narrator(SAMPLE_DATE, sunday_narrator=SAMPLE_SUNDAY_NARRATOR)
    print(f'  [夜記事] 夜のはじまり（ナレーター: {narrator}）...')
    night_beginning = generate_night_beginning(narrator)

    print('  [夜記事] リード文...')
    lead = generate_lead()

    hero_char = max(SAMPLE_DAILY, key=lambda d: abs(d['total_profit_loss']))
    print(f'  [夜記事] 今日の主役: {hero_char["analyst_name"]}...')
    hero_intro = generate_hero_intro(hero_char)

    print('  [夜記事] 反省会...')
    talk_lines = generate_girls_talk()

    print(f'  [夜記事] 明日へのひとこと（ナレーター: {narrator}）...')
    next_hook = generate_next_hook(narrator)

    print('  [夜記事] 推しポイント...')
    push_points = generate_push_points()

    print('  [夜記事] 勝負結果...')
    s_result = section_result()
    print('  [夜記事] ランキング...')
    s_rank = section_ranking()
    print('  [夜記事] MVP記録...')
    s_cum = section_cumulative()

    hero_html = (
        f'<div class="battle-hero">'
        f'<p class="battle-label">AI Virtual Investment Battle</p>'
        f'<h1>【AI投資バトル】{SAMPLE_DATE} 結果発表</h1>'
        f'<p class="battle-lead">{lead}</p>'
        f'</div>'
    )
    notice = (
        '<p class="sim-notice">この記事は、AIキャラクターによる投資シミュレーション企画です。'
        '実際の売買を行ったものではありません。</p>'
    )
    preview_notice = f'<p class="preview-notice">※ サンプルデータによるプレビュー（夜記事 {SAMPLE_DATE}生成）</p>'

    return '\n'.join([
        '<div id="evening">',
        preview_notice,
        section_morning_link(SAMPLE_MORNING_POST_URL),
        hero_html,
        notice,
        section_night_beginning(night_beginning, narrator),
        section_today_hero(hero_char, hero_intro),
        s_result,
        section_girls_talk(talk_lines),
        section_push_points(push_points),
        s_rank,
        s_cum,
        f'<div class="next-hook">{_narrator_avatar_html(narrator)}{next_hook}</div>',
        DISCLAIMER,
        '</div>',
    ])

# ---------------------------------------------------------------------------
# 統合HTML出力
# ---------------------------------------------------------------------------
def build_html() -> str:
    print('=== 朝記事生成中 ===')
    morning_body = build_morning_html()
    print('=== 夜記事生成中 ===')
    evening_body = build_evening_html()

    nav = (
        '<div class="preview-nav">'
        '<a href="#morning">☀️ 朝の作戦会議</a>'
        '<a href="#evening">🌙 夜の結果発表</a>'
        '</div>'
    )
    divider = '<hr class="article-divider">'

    body = '\n'.join([
        BATTLE_CSS,
        nav,
        '<section class="battle-article">',
        morning_body,
        '</section>',
        divider,
        '<section class="battle-article">',
        evening_body,
        '</section>',
    ])

    return (
        '<!DOCTYPE html><html lang="ja">'
        '<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>'
        f'<body>{body}</body></html>'
    )

if __name__ == '__main__':
    out_path = os.path.join(os.path.dirname(__file__), 'blog_preview.html')
    html = build_html()
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f'\n生成完了: {out_path}')
