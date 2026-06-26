"""
DBテーブルを初期化するユーティリティ。
main.py 起動時に呼ぶことで全テーブルが存在することを保証する。
"""
import os
import sqlite3
from config.config import config


def initialize_db() -> None:
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    db_path = os.path.join(project_root, 'db', config.DB)
    sql_dir = os.path.join(project_root, 'db', 'SQL')

    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    sql_files = sorted(f for f in os.listdir(sql_dir) if f.endswith('.sql'))
    with sqlite3.connect(db_path) as conn:
        for filename in sql_files:
            filepath = os.path.join(sql_dir, filename)
            with open(filepath, encoding='utf-8') as f:
                sql = f.read()
            try:
                conn.executescript(sql)
            except Exception as e:
                print(f'SQL実行エラー ({filename}): {e}')
        conn.commit()
    print(f'DB初期化完了: {db_path}')
