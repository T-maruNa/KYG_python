import json
import requests
from datetime import datetime, timezone
from typing import Optional
from config.config import config

FORBIDDEN_PHRASES = [
    '絶対', '確実', '必ず上がる', '買うべき', '儲かる', '保証', '推奨銘柄',
]


class WordPressClient:
    def __init__(self):
        self.base_url = config.WORDPRESS_BASE_URL
        self.username = config.WORDPRESS_USERNAME
        self.app_password = config.WORDPRESS_APP_PASSWORD
        self._endpoint = f'{self.base_url.rstrip("/")}/wp-json/wp/v2/posts'

    # ------------------------------------------------------------------
    # 公開 API
    # ------------------------------------------------------------------

    def post(self, title: str, content: str, post_date: str,
             scheduled_hour: int = None, dry_run: bool = False) -> Optional[int]:
        """
        記事を即公開で投稿する。dry_run=True の場合はAPIを呼ばずにチェックだけ行う。
        scheduled_hour を指定した場合は予約投稿（後方互換のため残している）。

        Returns:
            WordPress post ID（dry_run時は0）、失敗時は None
        """
        errors = self._pre_check(title, content)
        if errors:
            print(f'投稿前チェックNG: {errors}')
            return None

        if scheduled_hour is not None:
            status = 'future'
            date_param = f'{post_date}T{scheduled_hour:02d}:00:00+09:00'
        else:
            status = 'publish'
            date_param = None

        payload = {'title': title, 'content': content, 'status': status}
        if date_param:
            payload['date'] = date_param

        if dry_run:
            print('[DRY-RUN] 投稿内容:')
            print(f'  タイトル : {title}')
            print(f'  ステータス: {status}' + (f'  予約={date_param}' if date_param else '  即公開'))
            print(f'  本文文字数: {len(content)}')
            return 0

        try:
            resp = requests.post(
                self._endpoint,
                auth=(self.username, self.app_password),
                json=payload,
                timeout=30,
            )
            resp.raise_for_status()
            wp_id = resp.json().get('id')
            label = f'予約={date_param}' if date_param else '即公開'
            print(f'WordPress投稿成功: ID={wp_id}  {label}')
            return wp_id
        except requests.RequestException as e:
            print(f'WordPress投稿エラー: {e}')
            return None

    def exists_post(self, post_date: str) -> bool:
        """同一日付の記事が既に存在するか確認する"""
        if not self.base_url:
            return False
        try:
            resp = requests.get(
                self._endpoint,
                params={'search': post_date, 'per_page': 5},
                auth=(self.username, self.app_password),
                timeout=10,
            )
            resp.raise_for_status()
            return any(post_date in p.get('date', '') for p in resp.json())
        except Exception:
            return False

    # ------------------------------------------------------------------
    # 内部チェック
    # ------------------------------------------------------------------

    def _pre_check(self, title: str, content: str) -> list:
        errors = []
        if not title.strip():
            errors.append('タイトルが空')
        if not content.strip():
            errors.append('本文が空')
        if '仮想投資シミュレーション' not in content:
            errors.append('免責文なし')
        for phrase in FORBIDDEN_PHRASES:
            if phrase in content or phrase in title:
                errors.append(f'禁止表現: {phrase}')
        return errors
