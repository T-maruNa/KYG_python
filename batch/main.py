from src.core.stock_predictor import StockPredictor
from src.database.t_stock_result_manager import TStockResultManager
from src.database.t_stock_predict_manager import TStockPredictManager
from src.database.t_stock_actual_manager import TStockActualManager
from src.core.stock_yfinance import StockYFinance
from datetime import date, timedelta

int_monday = 0
int_friday = 4

# 現在の日付を取得
today = date.today()
# 1日分の時間差を定義
one_day = timedelta(days=1)

# 前営業日を計算
if today.weekday() == int_monday:
    # 月曜日の場合は金曜日が対象日
    pre_day = today - (one_day * 3)
else:
    # 月曜日以外の場合は昨日が対象日
    pre_day = today - one_day
formatted_pre_day = pre_day.strftime("%Y-%m-%d")

# 次営業日を計算
if today.weekday() == int_friday:
    # 金曜日の場合は月曜日が対象日
    next_day = today + (one_day * 3)
else:
    # 金曜日以外の場合は明日が対象日
    next_day = today + one_day

formatted_next_day = next_day.strftime("%Y-%m-%d")


# 既存の株価データをチェック
actual_manager = TStockActualManager()
if actual_manager.get_stock_actual(date_from=formatted_pre_day):
    print(f"デバッグ: {formatted_pre_day} の株価データは既に存在します")
else:
    # 現在の株価データを取得、設定(yfinance)
    StockYFinance().set_stock_prices(formatted_pre_day)

# 既存の予測データをチェック
predict_manager = TStockPredictManager()
if predict_manager.exists_prediction(formatted_next_day):
    print(f"デバッグ: {formatted_next_day} の予測データは既に存在します")
else:
    # 株価予測を実行(AI予想)
    StockPredictor().predict(formatted_pre_day, formatted_next_day)

# 既存の予測結果をチェック

result_manager = TStockResultManager()
no_resut_date = result_manager.get_no_result_date()
if no_resut_date is None:
    print(f"デバッグ: {today}の予測結果は既に存在します")
else:
    # 予測の結果を保存
    # StockResultAnalyzer().insert_prediction_results()
    # 成績を保存
    print(f"デバッグ: まだなんもない")