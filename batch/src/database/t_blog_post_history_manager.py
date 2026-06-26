from typing import Optional
from .db_manager import DBManager


class TBlogPostHistoryManager(DBManager):
    def __init__(self):
        super().__init__()

    def exists(self, post_date: str, post_type: str = 'daily') -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT COUNT(*) FROM t_blog_post_history
                WHERE post_date = ? AND post_type = ?
            ''', (post_date, post_type))
            return cursor.fetchone()[0] > 0

    def insert(self, post_date: str, post_type: str = 'daily',
               wp_post_id: Optional[int] = None, status: str = 'pending') -> bool:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR IGNORE INTO t_blog_post_history
                        (post_date, post_type, wp_post_id, status)
                    VALUES (?, ?, ?, ?)
                ''', (post_date, post_type, wp_post_id, status))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            print(f"ブログ投稿履歴登録エラー: {e}")
            return False

    def update_status(self, post_date: str, post_type: str,
                      status: str, wp_post_id: Optional[int] = None) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE t_blog_post_history
                SET status = ?, wp_post_id = ?, update_date = CURRENT_TIMESTAMP
                WHERE post_date = ? AND post_type = ?
            ''', (status, wp_post_id, post_date, post_type))
            conn.commit()
