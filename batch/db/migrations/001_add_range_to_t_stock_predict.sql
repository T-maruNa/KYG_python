-- t_stock_predict に range カラムを追加する（既存DBへの差分適用）
ALTER TABLE t_stock_predict ADD COLUMN range INTEGER NOT NULL DEFAULT 0;
