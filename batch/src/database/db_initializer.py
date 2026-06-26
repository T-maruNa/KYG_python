"""
DBテーブルを初期化するユーティリティ。
main.py 起動時に呼ぶことで全テーブルが存在することを保証する。

マイグレーション戦略:
  - db/SQL/   : CREATE TABLE IF NOT EXISTS（新規 DB 作成用）
  - db/migrations/ : ALTER TABLE 系の差分 SQL（既存 DB の列追加など）
  - t_db_migration テーブルで適用済みバージョンを管理し、冪等に実行する
"""
import os
import sqlite3
from config.config import config

_CREATE_MIGRATION_TABLE = '''
CREATE TABLE IF NOT EXISTS t_db_migration (
    version TEXT PRIMARY KEY,
    applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
)
'''


def _get_columns(conn: sqlite3.Connection, table: str) -> set:
    cursor = conn.execute(f'PRAGMA table_info({table})')
    return {row[1] for row in cursor.fetchall()}


def _apply_migration(conn: sqlite3.Connection, version: str, sql_path: str) -> None:
    """1 つのマイグレーションファイルを適用して t_db_migration に記録する。"""
    with open(sql_path, encoding='utf-8') as f:
        statements = [s.strip() for s in f.read().split(';') if s.strip()]

    for stmt in statements:
        if not stmt or stmt.startswith('--'):
            continue
        # ALTER TABLE ADD COLUMN は列が既に存在するとエラーになるため事前チェック
        if 'ADD COLUMN' in stmt.upper():
            import re
            m = re.search(r'ALTER\s+TABLE\s+(\w+)\s+ADD\s+COLUMN\s+(\w+)', stmt, re.IGNORECASE)
            if m:
                table, col = m.group(1), m.group(2)
                if col in _get_columns(conn, table):
                    continue  # 既に存在するのでスキップ
        try:
            conn.execute(stmt)
        except sqlite3.OperationalError as e:
            print(f'  マイグレーション警告 ({version}): {e}')

    conn.execute(
        'INSERT OR IGNORE INTO t_db_migration (version) VALUES (?)', (version,)
    )
    conn.commit()
    print(f'  マイグレーション適用: {version}')


def initialize_db() -> None:
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    db_path = os.path.join(project_root, 'db', config.DB)
    sql_dir = os.path.join(project_root, 'db', 'SQL')
    migration_dir = os.path.join(project_root, 'db', 'migrations')

    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    with sqlite3.connect(db_path) as conn:
        # 1. テーブル作成（CREATE TABLE IF NOT EXISTS）
        sql_files = sorted(f for f in os.listdir(sql_dir) if f.endswith('.sql'))
        for filename in sql_files:
            filepath = os.path.join(sql_dir, filename)
            with open(filepath, encoding='utf-8') as f:
                sql = f.read()
            try:
                conn.executescript(sql)
            except Exception as e:
                print(f'SQL実行エラー ({filename}): {e}')
        conn.commit()

        # 2. マイグレーション管理テーブルを確保
        conn.execute(_CREATE_MIGRATION_TABLE)
        conn.commit()

        # 3. 未適用のマイグレーションを順に適用
        if os.path.isdir(migration_dir):
            applied = {
                row[0] for row in conn.execute('SELECT version FROM t_db_migration')
            }
            pending = sorted(
                f for f in os.listdir(migration_dir)
                if f.endswith('.sql') and f not in applied
            )
            for filename in pending:
                _apply_migration(conn, filename, os.path.join(migration_dir, filename))

    print(f'DB初期化完了: {db_path}')
