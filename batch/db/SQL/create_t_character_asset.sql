CREATE TABLE IF NOT EXISTS t_character_asset (
    id              SERIAL      NOT NULL PRIMARY KEY,
    year_month      TEXT        NOT NULL,
    analyst_name    TEXT        NOT NULL,
    initial_balance INTEGER     NOT NULL DEFAULT 1000000,
    current_balance INTEGER     NOT NULL DEFAULT 1000000,
    insert_date     TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_date     TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_user     VARCHAR(20) NOT NULL DEFAULT 'SYSTEM',
    UNIQUE(year_month, analyst_name)
);
