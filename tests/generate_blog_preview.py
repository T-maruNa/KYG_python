"""
ブログプレビュー生成スクリプト

DBや予算ガードを使わず、サンプルデータ＋Gemini APIで
実際のブログHTMLを生成して blog_preview.html に出力する。

GEMINI_STOCK_API_KEY が未設定の場合はAIコメントをプレースホルダーで代替。

Usage:
    cd tests
    python generate_blog_preview.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'batch'))

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
    {'analyst_name': 'mirai', 'stock_code': '9984', 'stock_name': 'ソフトバンクG', 'profit_loss_rate': -1.5, 'buy_amount': 285000},
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

# ---------------------------------------------------------------------------
# キャラクター定義
# ---------------------------------------------------------------------------
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
.battle-article{max-width:860px;margin:0 auto;color:#3f3446;line-height:1.8;font-family:sans-serif;}
.battle-hero{background:linear-gradient(135deg,#fff7fb,#f3f8ff);border:1px solid #f0ddea;border-radius:28px;padding:28px 24px;margin-bottom:28px;box-shadow:0 10px 30px rgba(120,80,120,.08);}
.battle-label{display:inline-block;font-size:.82rem;letter-spacing:.08em;color:#9b6b88;background:rgba(255,255,255,.8);border-radius:999px;padding:4px 12px;margin-bottom:8px;}
.battle-lead{margin:.4em 0 0;color:#7a6b80;font-size:.95rem;}
.battle-article h1{color:#4b3b57;margin:.2em 0;}
.battle-article h2{color:#4b3b57;border-bottom:none;margin-top:2.2em;padding-left:.2em;}
.battle-article h2::before{content:"✦ ";color:#e6a6c8;}
.battle-article h3{color:#4b3b57;margin:.6em 0 .3em;}
.sim-notice{font-size:.9em;color:#666;background:#f9f9f9;border-left:4px solid #e6a6c8;padding:.6em 1em;border-radius:0 8px 8px 0;margin-bottom:1.5em;}
.preview-notice{font-size:.85em;color:#999;background:#fafafa;border:1px dashed #ddd;border-radius:8px;padding:.5em 1em;margin-bottom:1em;text-align:center;}
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

# ---------------------------------------------------------------------------
# Gemini呼び出し（APIキーなければフォールバック）
# ---------------------------------------------------------------------------
def _gemini_comment(system: str, user: str, fallback: str) -> str:
    api_key = os.getenv('GEMINI_STOCK_API_KEY') or os.getenv('GEMINI_API_KEY')
    if not api_key:
        return f'<em style="color:#aaa;">[AIコメント: APIキー未設定]</em> {fallback}'
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.0-flash')
        prompt = f'system: {system}\nuser: {user}'
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return f'<em style="color:#aaa;">[AIエラー: {e}]</em> {fallback}'


# ---------------------------------------------------------------------------
# アバターHTML（プレビュー用は常にプレースホルダー）
# ---------------------------------------------------------------------------
def _avatar_html(name: str, expression: str, size: str = '92px') -> str:
    profile = ANALYST_PROFILES[name]
    return (
        f'<div class="character-avatar" style="width:{size};height:{size};">'
        f'<div class="character-avatar-placeholder">🖼️<br>{profile["name_jp"]}<br>'
        f'<span style="font-size:.55rem;">※結果により変動</span></div>'
        f'</div>'
    )


def get_expression(rate: float) -> str:
    if rate >= 5:  return 'victory'
    if rate >= 0:  return 'happy'
    if rate >= -5: return 'worried'
    return 'defeated'


# ---------------------------------------------------------------------------
# セクション生成
# ---------------------------------------------------------------------------
def section_result() -> str:
    first_balance = SAMPLE_RANKING[0]['current_balance']
    ranking_map = {r['analyst_name']: i + 1 for i, r in enumerate(SAMPLE_RANKING)}
    total = len(SAMPLE_RANKING)

    html = f'<h2>今日の成績 <span style="font-size:.8em;font-weight:normal;">{SAMPLE_DATE}</span></h2>\n'
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
        rank_ctx = '現在ランキング1位です。' if rank == 1 else f'現在ランキング{rank}位（1位との差：{gap:,}円）です。'

        comment = _gemini_comment(
            system=f'あなたは{profile["name_jp"]}です。{profile["personality"]}',
            user=(f'今日の投資結果は{sign}{profit:,}円（{win}勝{lose}敗）でした。'
                  f'{rank_ctx}キャラクターらしい短いコメントを1〜2文で返してください。'
                  f'順位についても触れてください。投資助言・断言表現は避けてください。'),
            fallback=f'今日は{sign}{profit:,}円でした。',
        )

        html += (
            f'<div class="character-card character-{name}">\n'
            f'  <div class="character-header">\n'
            f'    {_avatar_html(name, expression)}\n'
            f'    <div>\n'
            f'      <h3 style="margin:0 0 2px;">{profile["name_jp"]}</h3>\n'
            f'      <p class="character-role">{profile["role"]}</p>\n'
            f'    </div>\n'
            f'  </div>\n'
            f'  <div class="result-score {score_class}">{sign}{profit:,}円</div>\n'
            f'  <p class="result-meta">{win}勝{lose}敗 / 現在資産 {balance:,}円</p>\n'
            f'  <div class="character-balloon">{comment}</div>\n'
            f'</div>\n'
        )
    return html


def section_ranking() -> str:
    html = '<h2>今月の資産ランキング</h2>\n'
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
            f'  {_avatar_html(name, "happy", "48px")}\n'
            f'  <div>\n'
            f'    <strong>{profile["name_jp"]}</strong><br>\n'
            f'    <span style="font-size:1.05em;font-weight:700;">{r["current_balance"]:,}円</span>'
            f'    <span style="font-size:.88em;color:#888;"> ({sign}{diff:,}円)</span>\n'
            f'  </div>\n'
            f'</div>\n'
        )

    for i, r in enumerate(SAMPLE_RANKING):
        name = r['analyst_name']
        profile = ANALYST_PROFILES[name]
        gap = first_balance - r['current_balance']
        rank = i + 1
        rank_ctx = f'{total}人中1位です。' if rank == 1 else f'{total}人中{rank}位で、1位との差は{gap:,}円です。'
        comment = _gemini_comment(
            system=f'あなたは{profile["name_jp"]}です。{profile["personality"]}',
            user=(f'現在{rank_ctx}現在の順位についてキャラクターらしい一言コメントを1文で返してください。'
                  f'投資助言・断言表現は避けてください。'),
            fallback=f'{rank}位です。',
        )
        html += (
            f'<div class="ranking-inline">\n'
            f'  {_avatar_html(name, "happy", "56px")}\n'
            f'  <div class="character-balloon" style="flex:1;">'
            f'<strong>{profile["name_jp"]}</strong>：{comment}</div>\n'
            f'</div>\n'
        )
    return html


def section_today_entry() -> str:
    html = f'<h2>今日のエントリー <span style="font-size:.8em;font-weight:normal;">{SAMPLE_TRADE_DATE}</span></h2>\n'
    for analyst_name, profile in ANALYST_PROFILES.items():
        ae = [e for e in SAMPLE_TODAY_ENTRIES if e['analyst_name'] == analyst_name]
        if not ae:
            continue
        html += f'<h3>{profile["name_jp"]}</h3>\n'
        html += '<table class="battle-table"><tr><th>銘柄コード</th><th>銘柄名</th><th>投資額</th><th>選定理由</th></tr>\n'
        total = 0
        for e in ae:
            approx_man = round(e['buy_amount'] / 10000)
            total += e['buy_amount']
            html += (
                f'<tr><td>{e["stock_code"]}</td>'
                f'<td>{e["stock_name"]}</td>'
                f'<td>約{approx_man}万円</td>'
                f'<td>{e["prediction_reason"]}</td></tr>\n'
            )
        html += f'</table>\n<p class="entry-total">合計　約{round(total / 10000)}万円</p>\n'

        stocks = [e['stock_name'] for e in ae]
        comment = _gemini_comment(
            system=f'あなたは{profile["name_jp"]}です。{profile["personality"]}',
            user=(f'今日のエントリー銘柄は{"、".join(stocks)}です。'
                  f'選んだ理由や意気込みをキャラクターらしく1〜2文で話してください。'
                  f'投資助言・断言表現は避けてください。'),
            fallback=f'今日は{"、".join(stocks)}に注目しています。',
        )
        html += (
            f'<div class="character-inline">\n'
            f'  {_avatar_html(analyst_name, "happy", "56px")}\n'
            f'  <div class="character-balloon" style="flex:1;">{comment}</div>\n'
            f'</div>\n'
        )
    return html


def section_cumulative() -> str:
    html = '<h2>累計MVP記録</h2>\n'
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


# ---------------------------------------------------------------------------
# HTML組み立て
# ---------------------------------------------------------------------------
def build_html() -> str:
    print('セクション生成中...')
    print('  今日の成績...')
    s_result = section_result()
    print('  ランキング...')
    s_rank = section_ranking()
    print('  エントリー...')
    s_entry = section_today_entry()
    print('  累計MVP...')
    s_cum = section_cumulative()

    hero = (
        f'<div class="battle-hero">'
        f'<p class="battle-label">AI Virtual Investment Battle</p>'
        f'<h1>【AI投資バトル】{SAMPLE_TRADE_DATE} 今日の結果発表</h1>'
        f'<p class="battle-lead">3人のAIキャラクターが、今日もシミュレーションで投資バトル。</p>'
        f'</div>'
    )
    notice = (
        '<p class="sim-notice">この記事は、AIキャラクターによる投資シミュレーション企画です。'
        '実際の売買を行ったものではありません。</p>'
    )
    preview_notice = (
        f'<p class="preview-notice">※ サンプルデータによるプレビュー（{SAMPLE_TRADE_DATE}生成）</p>'
    )

    body = '\n'.join([
        BATTLE_CSS,
        '<section class="battle-article">',
        preview_notice,
        hero,
        notice,
        s_result,
        s_rank,
        s_entry,
        s_cum,
        DISCLAIMER,
        '</section>',
    ])

    return f'<!DOCTYPE html><html lang="ja"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head><body>{body}</body></html>'


if __name__ == '__main__':
    out_path = os.path.join(os.path.dirname(__file__), 'blog_preview.html')
    html = build_html()
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f'\n✅ 生成完了: {out_path}')
