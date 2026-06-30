CREATE TABLE IF NOT EXISTS t_candidate_stock_scores (
    id              SERIAL        PRIMARY KEY,
    target_date     DATE          NOT NULL,
    stock_code      VARCHAR(20)   NOT NULL,
    stock_name      VARCHAR(200)  NOT NULL,
    price_range     INT           NOT NULL,
    common_score    FLOAT         NOT NULL DEFAULT 0,
    rei_score       FLOAT         NOT NULL DEFAULT 0,
    mirai_score     FLOAT         NOT NULL DEFAULT 0,
    rank_common     INT,
    rank_rei        INT,
    rank_mirai      INT,
    feature_summary TEXT,
    created_at      TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (target_date, stock_code)
)
