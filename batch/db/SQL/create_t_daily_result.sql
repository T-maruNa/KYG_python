CREATE TABLE IF NOT EXISTS t_daily_result (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    result_date TEXT NOT NULL,
    analyst_name TEXT NOT NULL,
    total_profit_loss INTEGER NOT NULL DEFAULT 0,
    current_balance INTEGER NOT NULL,
    win_count INTEGER NOT NULL DEFAULT 0,
    lose_count INTEGER NOT NULL DEFAULT 0,
    insert_date DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(result_date, analyst_name)
)
