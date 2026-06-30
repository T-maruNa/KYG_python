"""t_generated_images テーブルのCRUD管理"""
from typing import Optional, Dict, List
from .db_manager import DBManager


class TGeneratedImagesManager(DBManager):

    def upsert(self, target_date: str, post_type: str, image_type: str,
               character_key: Optional[str], provider: str, model: str,
               prompt: str, image_url: Optional[str],
               generation_status: str, error_message: Optional[str] = None) -> None:
        """
        INSERT or UPDATE。UNIQUE 制約は (target_date, post_type, image_type, character_key)。
        同日に再実行されたときは最新の結果で上書きされる。
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO t_generated_images
                    (target_date, post_type, image_type, character_key,
                     provider, model, prompt, image_url, generation_status, error_message)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (target_date, post_type, image_type, character_key) DO UPDATE SET
                    provider          = EXCLUDED.provider,
                    model             = EXCLUDED.model,
                    prompt            = EXCLUDED.prompt,
                    image_url         = EXCLUDED.image_url,
                    generation_status = EXCLUDED.generation_status,
                    error_message     = EXCLUDED.error_message
            ''', (target_date, post_type, image_type, character_key,
                  provider, model, prompt, image_url, generation_status, error_message))

    def get(self, target_date: str, post_type: str, image_type: str,
            character_key: Optional[str] = None) -> Optional[Dict]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, target_date, post_type, image_type, character_key,
                       provider, model, image_url, prompt, generation_status, error_message, created_at
                FROM t_generated_images
                WHERE target_date = %s AND post_type = %s AND image_type = %s
                  AND character_key IS NOT DISTINCT FROM %s
            ''', (target_date, post_type, image_type, character_key))
            # IS NOT DISTINCT FROM は NULL = NULL を TRUE にするための PostgreSQL 構文
            # 集合シーン（character_key=NULL）も正しく一致検索できる
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_successful_url(self, target_date: str, post_type: str,
                           image_type: str, character_key: Optional[str] = None) -> Optional[str]:
        """生成済み成功 URL だけを取得する。記事生成時に再利用する用途向け。"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT image_url FROM t_generated_images
                WHERE target_date = %s AND post_type = %s AND image_type = %s
                  AND character_key IS NOT DISTINCT FROM %s
                  AND generation_status = 'success'
            ''', (target_date, post_type, image_type, character_key))
            row = cursor.fetchone()
            return row['image_url'] if row else None

    def count_today_generated(self, target_date: str) -> int:
        """その日の成功生成枚数を返す。1日あたり上限チェックに使う。"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT COUNT(*) FROM t_generated_images
                WHERE target_date = %s AND generation_status = 'success'
            ''', (target_date,))
            return cursor.fetchone()['count']
