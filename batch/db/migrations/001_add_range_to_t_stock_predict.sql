-- t_stock_predict に range カラムを追加する
-- SQLite は IF NOT EXISTS の ADD COLUMN をサポートしないため
-- db_initializer が列存在チェックをしてから実行する
ALTER TABLE t_stock_predict ADD COLUMN range INTEGER NOT NULL DEFAULT 0;
