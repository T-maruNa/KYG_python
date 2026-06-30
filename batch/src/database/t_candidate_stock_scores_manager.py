from typing import List, Dict
from .db_manager import DBManager


class TCandidateStockScoresManager(DBManager):
    """候補銘柄スコアリング結果の保存・取得。"""

    def __init__(self):
        super().__init__()

    def upsert_scores(self, target_date: str, candidates: List[Dict]) -> None:
        """
        スコアリング済み候補をまとめて保存（同一日付・銘柄は上書き）。
        candidates は CandidateScorer.score_and_rank() が返したリスト。
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            for c in candidates:
                cursor.execute('''
                    INSERT INTO t_candidate_stock_scores
                        (target_date, stock_code, stock_name, price_range,
                         common_score, rei_score, mirai_score,
                         rank_common, rank_rei, rank_mirai,
                         feature_summary)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (target_date, stock_code) DO UPDATE SET
                        common_score    = EXCLUDED.common_score,
                        rei_score       = EXCLUDED.rei_score,
                        mirai_score     = EXCLUDED.mirai_score,
                        rank_common     = EXCLUDED.rank_common,
                        rank_rei        = EXCLUDED.rank_rei,
                        rank_mirai      = EXCLUDED.rank_mirai,
                        feature_summary = EXCLUDED.feature_summary
                ''', (
                    target_date,
                    c.get('stock_code'),
                    c.get('stock_name'),
                    c.get('price_range'),
                    c.get('common_score', 0),
                    c.get('rei_score', 0),
                    c.get('mirai_score', 0),
                    c.get('rank_common'),
                    c.get('rank_rei'),
                    c.get('rank_mirai'),
                    c.get('feature_label', ''),
                ))

    def get_top_by_date(self, target_date: str,
                        score_col: str = 'common_score',
                        limit: int = 30) -> List[Dict]:
        """指定日付のスコア上位銘柄を返す。"""
        allowed = {'common_score', 'rei_score', 'mirai_score'}
        if score_col not in allowed:
            score_col = 'common_score'
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f'''
                SELECT stock_code, stock_name, price_range,
                       common_score, rei_score, mirai_score,
                       rank_common, rank_rei, rank_mirai,
                       feature_summary
                FROM t_candidate_stock_scores
                WHERE target_date = %s
                ORDER BY {score_col} DESC
                LIMIT %s
            ''', (target_date, limit))
            return [dict(r) for r in cursor.fetchall()]

    def exists(self, target_date: str) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT COUNT(*) FROM t_candidate_stock_scores WHERE target_date = %s',
                (target_date,)
            )
            return cursor.fetchone()['count'] > 0
