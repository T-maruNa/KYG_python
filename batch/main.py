"""
AI Virtual Investment Battle — メインバッチ

Usage:
    python main.py            # 通常実行
    python main.py --dry-run  # ネットワーク呼び出し・WordPress投稿をスキップ
    python main.py --backfill # 過去30日分の株価データを取得して終了
"""
import sys
import os
from datetime import date, timedelta

try:
    import jpholiday
    _HAS_JPHOLIDAY = True
except ImportError:
    _HAS_JPHOLIDAY = False
    print('警告: jpholiday が未インストールのため祝日チェックをスキップします。'
          '  pip install jpholiday でインストールしてください。')

# batch/ を sys.path に追加（コマンドライン実行時用）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.database.db_initializer import initialize_db
from src.core.stock_yfinance import StockYFinance
from src.core.stock_yfinance_full import StockYFinanceFull
from src.core.feature_calculator import FeatureCalculator
from src.core.stock_predictor import StockPredictor
from src.core.virtual_trader import VirtualTrader
from src.core.result_verifier import ResultVerifier
from src.core.stats_aggregator import StatsAggregator
from src.core.blog_generator import BlogGenerator
from src.api.wordpress_client import WordPressClient
from src.database.t_stock_actual_manager import TStockActualManager
from src.database.t_stock_predict_manager import TStockPredictManager
from src.database.t_blog_post_history_manager import TBlogPostHistoryManager
from src.database.t_investment_history_manager import TInvestmentHistoryManager
from src.core.ai_budget_guard import AIBudgetGuard

# ------------------------------------------------------------------
# 引数パース
# ------------------------------------------------------------------
DRY_RUN = '--dry-run' in sys.argv
BACKFILL = '--backfill' in sys.argv
EVENING_RUN = '--evening' in sys.argv


def _is_business_day(d: date) -> bool:
    """土日・祝日でなければ True"""
    if d.weekday() >= 5:
        return False
    if _HAS_JPHOLIDAY and jpholiday.is_holiday(d):
        return False
    return True


def _prev_business_day(d: date) -> date:
    """d の直前の営業日を返す"""
    target = d - timedelta(days=1)
    while not _is_business_day(target):
        target -= timedelta(days=1)
    return target


def _next_business_day(d: date) -> date:
    """d の直後の営業日を返す"""
    target = d + timedelta(days=1)
    while not _is_business_day(target):
        target += timedelta(days=1)
    return target


# ------------------------------------------------------------------
# 日付計算
# ------------------------------------------------------------------
today = date.today()

prev_day = _prev_business_day(today)
next_day = _next_business_day(today)

formatted_today = today.strftime('%Y-%m-%d')
formatted_prev_day = prev_day.strftime('%Y-%m-%d')
formatted_next_day = next_day.strftime('%Y-%m-%d')
year_month = today.strftime('%Y-%m')
prev_year_month = prev_day.strftime('%Y-%m')

is_first_business_day = (prev_day.month != today.month)
is_last_business_day = (next_day.month != today.month)

# 記事・エントリーの対象日 = 今日（今日の取引を今日の朝に発表する）
# 買値 = prev_day の終値、売値 = today の終値（明朝の検証で確定）
formatted_trade_date = formatted_today

print(f'=== バッチ開始 {formatted_today} ===')
print(f'  前営業日 (買値基準/検証対象): {formatted_prev_day}')
print(f'  取引日  (今日のエントリー): {formatted_trade_date}')
print(f'  次営業日: {formatted_next_day}')
print(f'  月初判定: {is_first_business_day}  月末判定: {is_last_business_day}')
print(f'  DRY_RUN: {DRY_RUN}')

# ------------------------------------------------------------------
# 土日・祝日チェック（休場日はスキップ）
# ------------------------------------------------------------------
if not BACKFILL:
    if not _is_business_day(today):
        holiday_name = (jpholiday.is_holiday_name(today) if _HAS_JPHOLIDAY else '')
        reason = f'祝日: {holiday_name}' if holiday_name else '土日'
        print(f'=== 休場日スキップ ({reason}): {formatted_today} ===')
        sys.exit(0)

# ------------------------------------------------------------------
# DB初期化
# ------------------------------------------------------------------
initialize_db()

# ------------------------------------------------------------------
# 夜バッチモード（--evening）
# ------------------------------------------------------------------
if EVENING_RUN:
    actual_manager = TStockActualManager()
    history_manager = TInvestmentHistoryManager()
    if not DRY_RUN and not actual_manager.get_stock_actual(date_from=formatted_today, date_to=formatted_today):
        StockYFinance().set_stock_prices(formatted_today)
        StockYFinanceFull().set_stock_prices(formatted_today)

    verifier = ResultVerifier()
    verifier.verify(formatted_today, year_month)

    aggregator = StatsAggregator()
    daily_summary = aggregator.get_daily_summary(formatted_today)
    ranking = aggregator.get_ranking(year_month)

    blog_gen = BlogGenerator()
    blog_history = TBlogPostHistoryManager()

    if not blog_history.exists(formatted_today, 'result_daily'):
        morning_url = blog_history.get_post_url(formatted_today, 'prediction_daily')
        result_title, result_content = blog_gen.generate_result(
            result_date=formatted_today,
            trade_date=formatted_today,
            year_month=year_month,
            ranking=ranking,
            morning_post_url=morning_url,
        )
        errors = blog_gen.check(result_content, [])
        if errors:
            print(f'夜記事チェックNG: {errors}')
        elif DRY_RUN:
            print(f'\n[DRY-RUN] 夜記事プレビュー: {result_title}')
            print(result_content)
        else:
            wp = WordPressClient()
            result = wp.post(result_title, result_content, formatted_today,
                             scheduled_hour=22,
                             tags=['鷲見玲', '桜庭みらい', '一ノ瀬律', 'AI投資バトル', '結果発表'])
            if result:
                blog_history.insert(formatted_today, 'result_daily',
                                    title=result_title, content=result_content,
                                    wp_post_id=result['id'], wp_post_url=result.get('url'),
                                    status='scheduled')
            else:
                blog_history.insert(formatted_today, 'result_daily',
                                    title=result_title, content=result_content, status='failed')
    else:
        print(f'夜記事スキップ: {formatted_today} は投稿済み')

    print(f'=== 夜バッチ完了 {formatted_today} ===')
    sys.exit(0)

# ------------------------------------------------------------------
# バックフィルモード
# ------------------------------------------------------------------
if BACKFILL:
    print('=== バックフィル実行（過去30日） ===')
    if not DRY_RUN:
        StockYFinanceFull().backfill(days=30)
    else:
        print('[DRY-RUN] バックフィルスキップ')
    sys.exit(0)

# ------------------------------------------------------------------
# 1. 株価データ取得
# ------------------------------------------------------------------
actual_manager = TStockActualManager()

if actual_manager.get_stock_actual(date_from=formatted_prev_day, date_to=formatted_prev_day):
    print(f'株価取得スキップ: {formatted_prev_day} は取得済み')
else:
    if not DRY_RUN:
        print(f'株価取得: {formatted_prev_day}')
        StockYFinance().set_stock_prices(formatted_prev_day)
        StockYFinanceFull().set_stock_prices(formatted_prev_day)
    else:
        print(f'[DRY-RUN] 株価取得スキップ: {formatted_prev_day}')

# ------------------------------------------------------------------
# 2. 前回エントリーの結果検証
# ------------------------------------------------------------------
verifier = ResultVerifier()
print(f'結果検証: {formatted_prev_day}')
verifier.verify(formatted_prev_day, prev_year_month)

# ------------------------------------------------------------------
# 3. 月初リセット
# ------------------------------------------------------------------
trader = VirtualTrader()
trader.initialize_month(year_month)

# ------------------------------------------------------------------
# 4. 資金残高に応じた投資可能価格帯を取得
# ------------------------------------------------------------------
active_ranges_by_analyst = trader.get_active_ranges_all(year_month)
print('投資可能価格帯:')
for name, ranges in active_ranges_by_analyst.items():
    print(f'  {name}: {ranges}')

# ------------------------------------------------------------------
# 5. AI予測
# ------------------------------------------------------------------
predict_manager = TStockPredictManager()
if predict_manager.exists_prediction(formatted_trade_date):
    print(f'予測スキップ: {formatted_trade_date} は生成済み')
else:
    print(f'AI予測実行: {formatted_prev_day} → {formatted_trade_date}')
    predictor = StockPredictor()
    predictor.predict(
        yesterday_date=formatted_prev_day,
        tomorrow_date=formatted_trade_date,
        active_ranges_by_analyst=active_ranges_by_analyst,
        ranking_by_analyst=ranking_by_analyst,
    )

# ------------------------------------------------------------------
# 6. 仮想エントリー登録
# ------------------------------------------------------------------
print(f'エントリー登録: {formatted_trade_date}')
# buy_date = prev_day（前営業日終値で買ったことにする）
trader.execute_entries(formatted_trade_date, formatted_prev_day, year_month)

# ------------------------------------------------------------------
# 7. 成績集計
# ------------------------------------------------------------------
aggregator = StatsAggregator()
daily_summary = aggregator.get_daily_summary(formatted_prev_day)
ranking = aggregator.get_ranking(year_month)

print(f'\n=== {formatted_prev_day} 日次結果 ===')
for d in daily_summary:
    sign = '+' if d['total_profit_loss'] >= 0 else ''
    print(f'  {d["analyst_name"]}: {sign}{d["total_profit_loss"]:,}円  残高 {d["current_balance"]:,}円')

print(f'\n=== {year_month} 資産ランキング ===')
for i, r in enumerate(ranking, 1):
    diff = r['current_balance'] - r['initial_balance']
    print(f'  {i}位 {r["analyst_name"]}: {r["current_balance"]:,}円 ({diff:+,}円)')

# ランキング情報をアナリスト別に整理（予測・コメントで使用）
_first_balance = ranking[0]['current_balance'] if ranking else 0
ranking_by_analyst = {
    r['analyst_name']: {
        'rank': i + 1,
        'total': len(ranking),
        'gap_from_first': _first_balance - r['current_balance'],
    }
    for i, r in enumerate(ranking)
}

# 月末なら月次成績を確定
if is_last_business_day:
    print(f'\n月次成績確定: {year_month}')
    aggregator.finalize_month(year_month)

# ------------------------------------------------------------------
# 8. 朝記事生成（朝の作戦会議）
# ------------------------------------------------------------------
blog_gen = BlogGenerator()
blog_history = TBlogPostHistoryManager()

if not blog_history.exists(formatted_today, 'prediction_daily'):
    print('\n朝記事生成中...')
    _entry_history_manager = TInvestmentHistoryManager()
    today_entries = _entry_history_manager.get_by_date(formatted_trade_date)
    pred_title, pred_content = blog_gen.generate_prediction(
        trade_date=formatted_trade_date,
        today_entries=today_entries,
        ranking=ranking,
    )
    errors = blog_gen.check(pred_content, [])
    if errors:
        print(f'朝記事チェックNG: {errors}')
    elif DRY_RUN:
        print(f'\n[DRY-RUN] 朝記事プレビュー: {pred_title}')
        print(pred_content)
    else:
        # ------------------------------------------------------------------
        # 9. WordPress投稿（朝記事）
        # ------------------------------------------------------------------
        wp = WordPressClient()
        result = wp.post(pred_title, pred_content, formatted_today,
                         scheduled_hour=8,
                         tags=['鷲見玲', '桜庭みらい', '一ノ瀬律', 'AI投資バトル', '作戦会議'])
        if result:
            blog_history.insert(formatted_today, 'prediction_daily',
                                title=pred_title, content=pred_content,
                                wp_post_id=result['id'], wp_post_url=result.get('url'),
                                status='scheduled')
            print(f'朝記事WordPress投稿完了: post_id={result["id"]}')
        else:
            blog_history.insert(formatted_today, 'prediction_daily',
                                title=pred_title, content=pred_content, status='failed')
            print('朝記事WordPress投稿失敗')
else:
    print(f'朝記事スキップ: {formatted_today} は投稿済み')

# 月末なら月次まとめ記事も投稿
if is_last_business_day and not blog_history.exists(formatted_today, 'monthly'):
    monthly_content = blog_gen.generate_monthly(year_month)
    if monthly_content:
        monthly_title = f'【AI投資バトル】{year_month} 月間まとめ'
        errors = blog_gen.check(monthly_content, [])
        if not errors:
            if DRY_RUN:
                print('\n' + '=' * 60)
                print(f'[DRY-RUN] 月次記事プレビュー: {monthly_title}')
                print('=' * 60)
                print(monthly_content)
                print('=' * 60)
            else:
                wp = WordPressClient()
                monthly_result = wp.post(monthly_title, monthly_content, formatted_today)
                blog_history.insert(formatted_today, 'monthly',
                                    title=monthly_title, content=monthly_content,
                                    wp_post_id=monthly_result['id'] if monthly_result else None,
                                    wp_post_url=monthly_result.get('url') if monthly_result else None,
                                    status='scheduled' if monthly_result else 'failed')

# ------------------------------------------------------------------
# 10. AI予算使用状況を表示
# ------------------------------------------------------------------
guard = AIBudgetGuard()
print(f'\n=== AI予算状況 ===')
print(f'  本日残り呼び出し回数: {guard.remaining_calls_today()} 回')
print(f'  今月残り予算: {guard.remaining_budget_this_month():.0f} 円')

print(f'\n=== バッチ完了 {formatted_today} ===')
