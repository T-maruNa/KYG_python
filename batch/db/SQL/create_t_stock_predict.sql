CREATE TABLE IF NOT EXISTS t_stock_predict (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    predicted_date TEXT NOT NULL,
    analyst_name TEXT NOT NULL,
    range INTEGER NOT NULL,
    stock_code TEXT NOT NULL,
    stock_name TEXT NOT NULL,
    predicted_open_price INTEGER NOT NULL,
    predicted_high_price INTEGER NOT NULL,
    predicted_low_price INTEGER NOT NULL,
    predicted_close_price INTEGER NOT NULL,
    predicted_volume INTEGER NOT NULL,
    prediction_reason TEXT NOT NULL,
    insert_date DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    insert_user VARCHAR(20) NOT NULL
)