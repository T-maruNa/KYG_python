from typing import Optional, List, Dict
from .db_manager import DBManager


class TBlogPostHistoryManager(DBManager):
    def __init__(self):
        super().__init__()

    def exists(self, post_date: str, post_type: str = 'daily') -> bool:
        """scheduled/skipped のみ投稿済みとみなす。failed/dry_run は再実行可能。"""
        with self._get_connection() as conn:
            cursor = conn.execute('''
                SELECT COUNT(*) FROM t_blog_post_history
                WHERE post_date = ? AND post_type = ?
                  AND status IN ('scheduled', 'skipped')
            ''', (post_date, post_type))
            return cursor.fetchone()[0] > 0

    def insert(self, post_date: str, post_type: str = 'daily',
               title: str = None, content: str = None,
               wp_post_id: Optional[int] = None, status: str = 'pending') -> bool:
        try:
            with self._get_connection() as conn:
                conn.execute('''
                    INSERT INTO t_blog_post_history
                        (post_date, post_type, title, content, wp_post_id, status)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(post_date, post_type) DO UPDATE SET
                        title = excluded.title,
                        content = excluded.content,
                        wp_post_id = excluded.wp_post_id,
                        status = excluded.status,
                        update_date = CURRENT_TIMESTAMP
                ''', (post_date, post_type, title, content, wp_post_id, status))
                conn.commit()
                return True
        except Exception as e:
            print(f'ブログ投稿履歴登録エラー: {e}')
            return False

    def update_status(self, post_date: str, post_type: str,
                      status: str, wp_post_id: Optional[int] = None) -> None:
        with self._get_connection() as conn:
            conn.execute('''
                UPDATE t_blog_post_history
                SET status = ?, wp_post_id = ?, update_date = CURRENT_TIMESTAMP
                WHERE post_date = ? AND post_type = ?
            ''', (status, wp_post_id, post_date, post_type))
            conn.commit()

    def get_by_date(self, post_date: str) -> List[Dict]:
        with self._get_connection() as conn:
            cursor = conn.execute('''
                SELECT post_date, post_type, title, content, wp_post_id, status
                FROM t_blog_post_history
                WHERE post_date = ?
                ORDER BY post_type
            ''', (post_date,))
            cols = [d[0] for d in cursor.description]
            return [dict(zip(cols, row)) for row in cursor.fetchall()]

    def get_recent(self, limit: int = 30) -> List[Dict]:
        with self._get_connection() as conn:
            cursor = conn.execute('''
                SELECT post_date, post_type, title, wp_post_id, status
                FROM t_blog_post_history
                ORDER BY post_date DESC, post_type
                LIMIT ?
            ''', (limit,))
            cols = [d[0] for d in cursor.description]
            return [dict(zip(cols, row)) for row in cursor.fetchall()]
