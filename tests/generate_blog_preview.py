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
import json

# batch/ をパスに追加
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
    {'analyst_name': 'rei',   'stock_code': '7203', 'stock_name': 'トヨタ自動車', 'profit_loss_rate': 1.2, 'buy_amount': 298000},
    {'analyst_name': 'rei',   'stock_code': '6758', 'stock_name': 'ソニーグループ', 'profit_loss_rate': 2.8, 'buy_amount': 312000},
    {'analyst_name': 'mirai', 'stock_code': '9984', 'stock_name': 'ソフトバンクG', 'profit_loss_rate': -1.5, 'buy_amount': 285000},
    {'analyst_name': 'ritu',  'stock_code': '2914', 'stock_name': '日本たばこ産業', 'profit_loss_rate': 3.1, 'buy_amount': 276000},
]

SAMPLE_TODAY_ENTRIES = [
    {'analyst_name': 'rei',   'stock_code': '6501', 'stock_name': '日立製作所',   'buy_amount': 290000, 'prediction_reason': 'MACDゴールデンクロス確認。上昇トレンド継続中。'},
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
# キャラクター定義（blog_generator.py と同じ）
# ---------------------------------------------------------------------------
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

DISCLAIMER = (
    '<p style="font-size:0.85em;color:#888;border-top:1px solid #ddd;'
    'padding-top:1em;margin-top:2em;">'
    'この記事はAIキャラクターによる仮想投資シミュレーションです。<br>'
    '実際の売買を推奨するものではありません。<br>'
    '投資判断はご自身の責任で行ってください。'
    '</p>'
)

# ---------------------------------------------------------------------------
# Gemini呼び出し（APIキーなければフォールバック）
# ---------------------------------------------------------------------------
def _gemini_comment(system: str, user: str, fallback: str) -> str:
    api_key = os.getenv('GEMINI_STOCK_API_KEY') or os.getenv('GEMINI_API_KEY')
    if not api_key:
        return f'<em>[AIコメント: APIキー未設定のためプレースホルダー]</em> {fallback}'
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.0-flash')
        prompt = f'system: {system}\nuser: {user}'
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return f'<em>[AIエラー: {e}]</em> {fallback}'


# ---------------------------------------------------------------------------
# セクション生成
# ---------------------------------------------------------------------------
def get_expression(rate: float) -> str:
    if rate >= 5:  return 'victory'
    if rate >= 0:  return 'happy'
    if rate >= -5: return 'worried'
    return 'defeated'


def section_result() -> str:
    html = f'<h2>{SAMPLE_DATE} の結果発表</h2>\n'
    total = len(SAMPLE_RANKING)
    first_balance = SAMPLE_RANKING[0]['current_balance']

    ranking_map = {
        r['analyst_name']: i + 1 for i, r in enumerate(SAMPLE_RANKING)
    }

    for d in SAMPLE_DAILY:
        name = d['analyst_name']
        profile = ANALYST_PROFILES[name]
        profit = d['total_profit_loss']
        balance = d['current_balance']
        win, lose = d['win_count'], d['lose_count']
        sign = '+' if profit >= 0 else ''

        pl_rates = [e['profit_loss_rate'] for e in SAMPLE_PREV_ENTRIES if e['analyst_name'] == name]
        avg_rate = sum(pl_rates) / len(pl_rates) if pl_rates else 0

        rank = ranking_map.get(name, total)
        gap = first_balance - balance
        if rank == 1:
            rank_ctx = '現在ランキング1位です。'
        else:
            rank_ctx = f'現在ランキング{rank}位（1位との差：{gap:,}円）です。'

        comment = _gemini_comment(
            system=f'あなたは{profile["name_jp"]}です。{profile["personality"]}',
            user=(f'今日の投資結果は{sign}{profit:,}円（{win}勝{lose}敗）でした。'
                  f'{rank_ctx}キャラクターらしい短いコメントを1〜2文で返してください。'
                  f'順位についても触れてください。投資助言・断言表現は避けてください。'),
            fallback=f'今日は{sign}{profit:,}円でした。',
        )

        html += (
            f'<div class="character-result">\n'
            f'  <h3>{profile["name_jp"]}</h3>\n'
            f'  <p>損益: <strong>{sign}{profit:,}円</strong>（{win}勝{lose}敗）'
            f'　残高: {balance:,}円</p>\n'
            f'  <blockquote>{comment}</blockquote>\n'
            f'</div>\n'
        )
    return html


def section_ranking() -> str:
    html = f'<h2>{SAMPLE_YEAR_MONTH} 現在資産ランキング</h2>\n<ol>\n'
    total = len(SAMPLE_RANKING)
    first_balance = SAMPLE_RANKING[0]['current_balance']

    for r in SAMPLE_RANKING:
        diff = r['current_balance'] - r['initial_balance']
        sign = '+' if diff >= 0 else ''
        name_jp = ANALYST_PROFILES[r['analyst_name']]['name_jp']
        html += f'  <li>{name_jp}: {r["current_balance"]:,}円 ({sign}{diff:,}円)</li>\n'
    html += '</ol>\n'

    for i, r in enumerate(SAMPLE_RANKING):
        name = r['analyst_name']
        profile = ANALYST_PROFILES[name]
        gap = first_balance - r['current_balance']
        rank = i + 1
        if rank == 1:
            rank_ctx = f'{total}人中1位です。'
        else:
            rank_ctx = f'{total}人中{rank}位で、1位との差は{gap:,}円です。'

        comment = _gemini_comment(
            system=f'あなたは{profile["name_jp"]}です。{profile["personality"]}',
            user=(f'現在{rank_ctx}現在の順位についてキャラクターらしい一言コメントを1文で返してください。'
                  f'投資助言・断言表現は避けてください。'),
            fallback=f'{rank}位です。',
        )
        html += f'<p><strong>{profile["name_jp"]}</strong>：{comment}</p>\n'

    return html


def section_today_entry() -> str:
    html = f'<h2>{SAMPLE_TRADE_DATE} のエントリー銘柄</h2>\n'
    for analyst_name, profile in ANALYST_PROFILES.items():
        ae = [e for e in SAMPLE_TODAY_ENTRIES if e['analyst_name'] == analyst_name]
        if not ae:
            continue
        html += (
            f'<h3>{profile["name_jp"]}</h3>\n'
            f'<table border="1" cellpadding="6" cellspacing="0">'
            f'<tr><th>銘柄コード</th><th>銘柄名</th><th>購入金額</th><th>予想理由</th></tr>\n'
        )
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
        html += f'</table>\n<p>合計　約{round(total / 10000)}万円</p>\n'

        stocks = [e['stock_name'] for e in ae]
        comment = _gemini_comment(
            system=f'あなたは{profile["name_jp"]}です。{profile["personality"]}',
            user=(f'今日のエントリー銘柄は{"、".join(stocks)}です。'
                  f'選んだ理由や意気込みをキャラクターらしく1〜2文で話してください。'
                  f'投資助言・断言表現は避けてください。'),
            fallback=f'今日は{"、".join(stocks)}に注目しています。',
        )
        html += f'<blockquote>{comment}</blockquote>\n'
    return html


def section_cumulative() -> str:
    html = '<h2>累計MVP記録</h2>\n<ol>\n'
    for r in SAMPLE_CUMULATIVE_MVP:
        name_jp = ANALYST_PROFILES[r['analyst_name']]['name_jp']
        html += (
            f'  <li>{name_jp}: MVP {r["mvp_count"]}回 / '
            f'月間優勝 {r["win_count"]}回 / '
            f'累計損益 {r["cumulative_profit_loss"]:+,}円</li>\n'
        )
    html += '</ol>\n'
    return html


# ---------------------------------------------------------------------------
# HTML組み立て
# ---------------------------------------------------------------------------
CSS = '''
<style>
  body { font-family: sans-serif; max-width: 800px; margin: 2em auto; padding: 0 1em; color: #333; }
  h1 { color: #1a1a2e; }
  h2 { color: #16213e; border-bottom: 2px solid #0f3460; padding-bottom: 4px; margin-top: 2em; }
  h3 { color: #533483; }
  .character-result { background: #f9f9f9; border-radius: 8px; padding: 1em; margin: 1em 0; }
  blockquote { border-left: 4px solid #0f3460; margin: 0.5em 0; padding: 0.5em 1em; background: #eef; }
  table { border-collapse: collapse; width: 100%; margin: 0.5em 0; }
  th { background: #0f3460; color: white; padding: 8px; }
  td { padding: 6px 8px; border: 1px solid #ddd; }
  ol { padding-left: 1.5em; }
</style>
'''

def build_html() -> str:
    print('セクション生成中...')
    print('  結果発表...')
    s_result = section_result()
    print('  ランキング...')
    s_rank = section_ranking()
    print('  エントリー...')
    s_entry = section_today_entry()
    print('  累計MVP...')
    s_cum = section_cumulative()

    body = '\n'.join([
        f'<h1>【AI投資バトル】{SAMPLE_TRADE_DATE} 結果発表</h1>',
        f'<p style="color:#888;font-size:0.9em;">※ これはサンプルデータによるプレビューです（{SAMPLE_TRADE_DATE}生成）</p>',
        s_result,
        s_rank,
        s_entry,
        s_cum,
        DISCLAIMER,
    ])

    return f'<!DOCTYPE html><html lang="ja"><head><meta charset="UTF-8">{CSS}</head><body>{body}</body></html>'


if __name__ == '__main__':
    out_path = os.path.join(os.path.dirname(__file__), 'blog_preview.html')
    html = build_html()
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f'\n✅ 生成完了: {out_path}')
