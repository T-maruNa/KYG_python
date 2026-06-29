CREATE TABLE IF NOT EXISTS m_stock (
    id                SERIAL       NOT NULL PRIMARY KEY,
    stock_code        VARCHAR(4)   NOT NULL UNIQUE,
    stock_name        VARCHAR      NOT NULL,
    market_type       VARCHAR(10)  NOT NULL,
    industry_code_33  VARCHAR(10)  NULL,
    industry_type_33  VARCHAR      NULL,
    industry_code_17  VARCHAR(10)  NULL,
    industry_type_17  VARCHAR      NULL,
    insert_date       TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    insert_user       VARCHAR(20)  NOT NULL,
    update_date       TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_user       VARCHAR(20)  NOT NULL,
    delete_flag       INTEGER      NOT NULL DEFAULT 0,
    delete_date       TIMESTAMP    NULL
);
