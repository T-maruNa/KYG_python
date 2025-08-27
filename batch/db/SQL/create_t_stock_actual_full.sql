CREATE TABLE IF NOT EXISTS t_stock_actual_full (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL ,
    stock_code TEXT NOT NULL ,
    stock_name TEXT NOT NULL,
    actual_open_price INTEGER NOT NULL,
    actual_high_price INTEGER NOT NULL,
    actual_low_price INTEGER NOT NULL,
    actual_close_price INTEGER NOT NULL,
    actual_volume INTEGER NOT NULL,
    insert_date DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    insert_user VARCHAR(20) NOT NULL,
    update_date DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_user VARCHAR(20) NOT NULL,
    unique(date, stock_code)
)