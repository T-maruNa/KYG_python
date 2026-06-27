"""
DBテーブルを初期化するユーティリティ。
main.py 起動時に呼ぶことで全テーブルが存在することを保証する。

マイグレーション戦略:
  - db/SQL/   : CREATE TABLE IF NOT EXISTS（新規 DB 作成用）
  - db/migrations/ : ALTER TABLE 系の差分 SQL（既存 DB の列追加など）
  - t_db_migration テーブルで適用済みバージョンを管理し、冪等に実行する
"""
import os
import re
import psycopg2
from config.config import config

_CREATE_MIGRATION_TABLE = '''
CREATE TABLE IF NOT EXISTS t_db_migration (
    version    TEXT      PRIMARY KEY,
    applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
)
'''


def _get_columns(cursor, table: str) -> set:
    cursor.execute('''
        SELECT column_name FROM information_schema.columns
        WHERE table_name = %s
    ''', (table,))
    return {row['column_name'] for row in cursor.fetchall()}


def _exec_sql_file(cursor, filepath: str) -> None:
    with open(filepath, encoding='utf-8') as f:
        content = f.read()
    statements = [s.strip() for s in content.split(';') if s.strip() and not s.strip().startswith('--')]
    for stmt in statements:
        cursor.execute(stmt)


def _apply_migration(cursor, version: str, sql_path: str) -> None:
    with open(sql_path, encoding='utf-8') as f:
        content = f.read()
    statements = [s.strip() for s in content.split(';') if s.strip() and not s.strip().startswith('--')]

    for stmt in statements:
        if 'ADD COLUMN' in stmt.upper():
            m = re.search(r'ALTER\s+TABLE\s+(\w+)\s+ADD\s+COLUMN\s+(\w+)', stmt, re.IGNORECASE)
            if m:
                table, col = m.group(1), m.group(2)
                if col in _get_columns(cursor, table):
                    continue
        try:
            cursor.execute(stmt)
        except psycopg2.errors.DuplicateColumn:
            pass
        except Exception as e:
            print(f'  マイグレーション警告 ({version}): {e}')

    cursor.execute(
        'INSERT INTO t_db_migration (version) VALUES (%s) ON CONFLICT DO NOTHING',
        (version,)
    )
    print(f'  マイグレーション適用: {version}')


def initialize_db() -> None:
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sql_dir = os.path.join(project_root, 'db', 'SQL')
    migration_dir = os.path.join(project_root, 'db', 'migrations')

    conn = psycopg2.connect(
        config.DATABASE_URL,
        cursor_factory=__import__('psycopg2.extras', fromlist=['RealDictCursor']).RealDictCursor,
    )
    try:
        with conn.cursor() as cur:
            # 1. テーブル作成（CREATE TABLE IF NOT EXISTS）
            sql_files = sorted(f for f in os.listdir(sql_dir) if f.endswith('.sql'))
            for filename in sql_files:
                try:
                    _exec_sql_file(cur, os.path.join(sql_dir, filename))
                except Exception as e:
                    print(f'SQL実行エラー ({filename}): {e}')
                    conn.rollback()

            # 2. マイグレーション管理テーブルを確保
            cur.execute(_CREATE_MIGRATION_TABLE)
            conn.commit()

            # 3. 未適用のマイグレーションを順に適用
            if os.path.isdir(migration_dir):
                cur.execute('SELECT version FROM t_db_migration')
                applied = {row['version'] for row in cur.fetchall()}
                pending = sorted(
                    f for f in os.listdir(migration_dir)
                    if f.endswith('.sql') and f not in applied
                )
                for filename in pending:
                    _apply_migration(cur, filename, os.path.join(migration_dir, filename))

            conn.commit()
    finally:
        conn.close()

    print(f'DB初期化完了: {config.DATABASE_URL.split("@")[-1] if "@" in config.DATABASE_URL else "PostgreSQL"}')
