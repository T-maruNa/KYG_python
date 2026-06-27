CREATE TABLE IF NOT EXISTS t_monthly_result (
    id                SERIAL    NOT NULL PRIMARY KEY,
    year_month        TEXT      NOT NULL,
    analyst_name      TEXT      NOT NULL,
    total_profit_loss INTEGER   NOT NULL DEFAULT 0,
    final_balance     INTEGER   NOT NULL DEFAULT 1000000,
    win_count         INTEGER   NOT NULL DEFAULT 0,
    lose_count        INTEGER   NOT NULL DEFAULT 0,
    rank              INTEGER,
    is_mvp            INTEGER   NOT NULL DEFAULT 0,
    insert_date       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_date       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(year_month, analyst_name)
);
