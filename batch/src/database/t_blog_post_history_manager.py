from typing import Optional, List, Dict
from .db_manager import DBManager


class TBlogPostHistoryManager(DBManager):
    def __init__(self):
        super().__init__()

    def exists(self, post_date: str, post_type: str = 'daily') -> bool:
        """scheduled/skipped のみ投稿済みとみなす。failed/dry_run は再実行可能。"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT COUNT(*) FROM t_blog_post_history
                WHERE post_date = %s AND post_type = %s
                  AND status IN ('scheduled', 'skipped')
            ''', (post_date, post_type))
            return cursor.fetchone()['count'] > 0

    def insert(self, post_date: str, post_type: str = 'daily',
               title: str = None, content: str = None,
               wp_post_id: Optional[int] = None, status: str = 'pending') -> bool:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO t_blog_post_history
                        (post_date, post_type, title, content, wp_post_id, status)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (post_date, post_type) DO UPDATE SET
                        title       = EXCLUDED.title,
                        content     = EXCLUDED.content,
                        wp_post_id  = EXCLUDED.wp_post_id,
                        status      = EXCLUDED.status,
                        update_date = CURRENT_TIMESTAMP
                ''', (post_date, post_type, title, content, wp_post_id, status))
                return True
        except Exception as e:
            print(f'ブログ投稿履歴登録エラー: {e}')
            return False

    def update_status(self, post_date: str, post_type: str,
                      status: str, wp_post_id: Optional[int] = None) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE t_blog_post_history
                SET status = %s, wp_post_id = %s, update_date = CURRENT_TIMESTAMP
                WHERE post_date = %s AND post_type = %s
            ''', (status, wp_post_id, post_date, post_type))

    def get_by_date(self, post_date: str) -> List[Dict]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT post_date, post_type, title, content, wp_post_id, status
                FROM t_blog_post_history
                WHERE post_date = %s
                ORDER BY post_type
            ''', (post_date,))
            return [dict(r) for r in cursor.fetchall()]

    def get_recent(self, limit: int = 30) -> List[Dict]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT post_date, post_type, title, wp_post_id, status
                FROM t_blog_post_history
                ORDER BY post_date DESC, post_type
                LIMIT %s
            ''', (limit,))
            return [dict(r) for r in cursor.fetchall()]
