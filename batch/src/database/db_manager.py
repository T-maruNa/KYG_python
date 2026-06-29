import psycopg2
import psycopg2.extras
from config.config import config


class _ConnectionContext:
    """psycopg2 接続をコンテキストマネージャで包む。
    with self._get_connection() as conn: が sqlite3 と同じ挙動になる。
    成功時に commit、例外時に rollback、どちらの場合も接続を close する。
    conn.cursor() で DictCursor を返すので row[column_name] でアクセスできる。
    """

    def __init__(self, dsn: str):
        self._dsn = dsn
        self._conn = None

    def __enter__(self):
        self._conn = psycopg2.connect(
            self._dsn,
            cursor_factory=psycopg2.extras.RealDictCursor,
        )
        return self._conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._conn:
            if exc_type:
                self._conn.rollback()
            else:
                self._conn.commit()
            self._conn.close()
        return False


class DBManager:
    def _get_connection(self) -> _ConnectionContext:
        return _ConnectionContext(config.DATABASE_URL)
