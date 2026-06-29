CREATE TABLE IF NOT EXISTS t_stock_result (
    id              SERIAL      NOT NULL PRIMARY KEY,
    date            TEXT        NOT NULL,
    period          TEXT        NOT NULL,
    analyst_name    TEXT        NOT NULL,
    range           INTEGER     NOT NULL,
    stock_code      TEXT        NOT NULL,
    stock_name      TEXT        NOT NULL,
    predicted_price INTEGER     NOT NULL,
    actual_price    INTEGER     NOT NULL,
    is_up           BOOLEAN     NOT NULL,
    insert_date     TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    insert_user     VARCHAR(20) NOT NULL,
    update_date     TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_user     VARCHAR(20) NOT NULL,
    delete_flag     INTEGER     NOT NULL DEFAULT 0,
    delete_date     TIMESTAMP   NULL
);
