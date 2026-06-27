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
from src.core.ai_budget_guard import AIBudgetGuard

# ------------------------------------------------------------------
# 引数パース
# ------------------------------------------------------------------
DRY_RUN = '--dry-run' in sys.argv
BACKFILL = '--backfill' in sys.argv


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
    if not DRY_RUN:
        print(f'AI予測実行: {formatted_prev_day} → {formatted_trade_date}')
        predictor = StockPredictor()
        predictor.predict(
            yesterday_date=formatted_prev_day,
            tomorrow_date=formatted_trade_date,
            active_ranges_by_analyst=active_ranges_by_analyst,
        )
    else:
        print(f'[DRY-RUN] AI予測スキップ: {formatted_trade_date}')

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

# 月末なら月次成績を確定
if is_last_business_day:
    print(f'\n月次成績確定: {year_month}')
    aggregator.finalize_month(year_month)

# ------------------------------------------------------------------
# 8. ブログ本文生成
# ------------------------------------------------------------------
blog_gen = BlogGenerator()
blog_history = TBlogPostHistoryManager()

if not blog_history.exists(formatted_today, 'daily'):
    print('\nブログ本文生成中...')
    content = blog_gen.generate_daily(
        result_date=formatted_prev_day,
        trade_date=formatted_trade_date,
        year_month=year_month,
    )
    title = f'【AI投資バトル】{formatted_today} 結果発表'

    errors = blog_gen.check(content, actual_manager.get_stock_actual(
        date_from=formatted_next_day, date_to=formatted_next_day
    ))
    if errors:
        print(f'ブログチェックNG: {errors}')
    else:
        # ------------------------------------------------------------------
        # 9. WordPress投稿
        # ------------------------------------------------------------------
        wp = WordPressClient()
        if not DRY_RUN and wp.exists_post(formatted_today):
            print(f'WordPress投稿スキップ: {formatted_today} は投稿済み')
            blog_history.insert(formatted_today, 'daily', title=title,
                                content=content, status='skipped')
        elif DRY_RUN:
            wp_id = wp.post(title, content, formatted_today, dry_run=True)
            print(f'[DRY-RUN] WordPress投稿シミュレート完了: post_id={wp_id}')
            # DRY_RUN 時は履歴に書かない（本番実行を妨げないため）
        else:
            wp_id = wp.post(title, content, formatted_today, dry_run=False)
            if wp_id is not None:
                blog_history.insert(formatted_today, 'daily', title=title,
                                    content=content, wp_post_id=wp_id,
                                    status='scheduled')
                print(f'WordPress投稿完了: post_id={wp_id}')
            else:
                blog_history.insert(formatted_today, 'daily', title=title,
                                    content=content, status='failed')
                print('WordPress投稿失敗')
else:
    print(f'ブログ投稿スキップ: {formatted_today} は投稿済み')

# 月末なら月次まとめ記事も投稿
if is_last_business_day and not blog_history.exists(formatted_today, 'monthly'):
    monthly_content = blog_gen.generate_monthly(year_month)
    if monthly_content:
        monthly_title = f'【AI投資バトル】{year_month} 月間まとめ'
        errors = blog_gen.check(monthly_content, [])
        if not errors:
            wp = WordPressClient()
            if not DRY_RUN:
                wp_id = wp.post(monthly_title, monthly_content, formatted_today,
                                dry_run=False)
                blog_history.insert(formatted_today, 'monthly',
                                    title=monthly_title, content=monthly_content,
                                    wp_post_id=wp_id,
                                    status='scheduled')
            else:
                wp.post(monthly_title, monthly_content, formatted_today,
                        scheduled_hour=9, dry_run=True)
                print('[DRY-RUN] 月次記事投稿シミュレート完了')

# ------------------------------------------------------------------
# 10. AI予算使用状況を表示
# ------------------------------------------------------------------
guard = AIBudgetGuard()
print(f'\n=== AI予算状況 ===')
print(f'  本日残り呼び出し回数: {guard.remaining_calls_today()} 回')
print(f'  今月残り予算: {guard.remaining_budget_this_month():.0f} 円')

print(f'\n=== バッチ完了 {formatted_today} ===')
