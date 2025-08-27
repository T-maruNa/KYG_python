import sqlite3
import os
from config.config import config

class DBManager:
    def __init__(self):
        # プロジェクトのルートディレクトリを取得
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        # データベースファイルのパスを設定
        self.db_path = os.path.join(project_root, 'db', config.DB)

    def _get_connection(self):
        """データベース接続を取得する"""
        return sqlite3.connect(self.db_path) 