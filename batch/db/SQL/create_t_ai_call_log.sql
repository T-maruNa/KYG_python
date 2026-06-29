CREATE TABLE IF NOT EXISTS t_ai_call_log (
    id                  SERIAL    NOT NULL PRIMARY KEY,
    call_date           TEXT      NOT NULL,
    call_type           TEXT      NOT NULL,
    model               TEXT      NOT NULL,
    estimated_cost_jpy  REAL      NOT NULL DEFAULT 0,
    success             INTEGER   NOT NULL DEFAULT 1,
    insert_date         TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
