"""
画像アセットのURL/パス解決。

優先順位:
  1. 個別キャラenv（IMG_REI 等）— 後方互換。blog_generator 側で処理。
  2. ASSET_BASE_URL が設定されている → 本番URL（WordPressメディアライブラリ等）
  3. 未設定 → ローカル assets/ 配下への相対パス（開発・プレビュー用）

画像ディレクトリ構成（プロジェクトルート/assets/）:
  characters/{character_key}/{expression}.png  （base/normal/happy/victory/smug/worried/defeated）
  scenes/{scene_file_name}.png
  site/{site_file_name}.png
"""
import os


def _project_root() -> str:
    # このファイルは batch/src/core/ にある
    # dirname x3 → batch/src → batch → project_root
    return os.path.normpath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..')
    )


class AssetResolver:
    """
    ASSET_BASE_URL が設定されている場合: 本番URLを返す
    未設定の場合: プロジェクトルート assets/ への相対パスを返す
    """

    # フォールバック用シーン画像ファイル名マッピング
    SCENE_FALLBACKS = {
        'morning_scene':          'morning_meeting_default.png',
        'morning_sub_scene':      'morning_sub_default.png',
        'night_reflection_scene': 'night_reflection_default.png',
        'highlight_scene':        'highlight_default.png',
        'monthly_mvp':            'monthly_mvp_default.png',
    }
    HERO_SCENE_FALLBACKS = {
        'rei':   'hero_default_rei.png',
        'mirai': 'hero_default_mirai.png',
        'ritu':  'hero_default_ritu.png',
    }

    def __init__(self):
        self._base_url = os.getenv('ASSET_BASE_URL', '').rstrip('/')
        self._assets_abs = os.path.join(_project_root(), 'assets')

    @property
    def is_remote(self) -> bool:
        """ASSET_BASE_URL が設定されている（本番モード）か"""
        return bool(self._base_url)

    # ------------------------------------------------------------------
    # HTML用 URL / 相対パス（<img src> に使う）
    # ------------------------------------------------------------------

    def character(self, character_key: str, file_name: str) -> str:
        """キャラクター画像のURL/相対パス。例: character('rei', 'normal.png')"""
        if self._base_url:
            return f'{self._base_url}/characters/{character_key}/{file_name}'
        return f'assets/characters/{character_key}/{file_name}'

    def scene(self, file_name: str) -> str:
        """シーン画像のURL/相対パス。例: scene('morning_meeting_default.png')"""
        if self._base_url:
            return f'{self._base_url}/scenes/{file_name}'
        return f'assets/scenes/{file_name}'

    def site(self, file_name: str) -> str:
        """サイト画像のURL/相対パス。例: site('logo.png')"""
        if self._base_url:
            return f'{self._base_url}/site/{file_name}'
        return f'assets/site/{file_name}'

    # ------------------------------------------------------------------
    # ファイル存在確認・APIアップロード用の絶対パス
    # ------------------------------------------------------------------

    def character_abs(self, character_key: str, file_name: str) -> str:
        """絶対パス。os.path.exists() や画像APIアップロードに使う。"""
        return os.path.join(self._assets_abs, 'characters', character_key, file_name)

    def scene_abs(self, file_name: str) -> str:
        return os.path.join(self._assets_abs, 'scenes', file_name)

    def site_abs(self, file_name: str) -> str:
        return os.path.join(self._assets_abs, 'site', file_name)

    def exists_abs(self, abs_path: str) -> bool:
        """
        本番URLモード: 常にTrue（ローカル存在確認スキップ）。
        ローカルモード: ファイルが実際に存在するか確認する。
        """
        if self._base_url:
            return True
        return os.path.exists(abs_path)

    # ------------------------------------------------------------------
    # 表情差分画像の解決
    # ------------------------------------------------------------------

    def character_expression(self, character_key: str, expression: str,
                             individual_url: str = '') -> str:
        """
        表情差分画像を解決して <img src> 用のURL/パスを返す。

        優先順位:
          1. individual_url（IMG_REI 等の個別env）が設定されていればそれを返す
          2. {expression}.png が存在する（ローカル or 本番URLモード）なら expression 画像
          3. base.png にフォールバック
          4. 空文字 → blog_generator 側でプレースホルダーに変換
        """
        if individual_url:
            return individual_url
        abs_expr = self.character_abs(character_key, f'{expression}.png')
        if self.exists_abs(abs_expr):
            return self.character(character_key, f'{expression}.png')
        abs_base = self.character_abs(character_key, 'base.png')
        if self.exists_abs(abs_base):
            return self.character(character_key, 'base.png')
        return ''

    # ------------------------------------------------------------------
    # シーンフォールバック画像の解決
    # ------------------------------------------------------------------

    def scene_fallback(self, image_type: str, character_key: str = '') -> str:
        """
        API生成失敗時のシーン固定画像を返す。
        存在しない（ローカルモードでファイルなし）場合は空文字を返す。
        """
        if image_type == 'hero_scene' and character_key:
            fname = self.HERO_SCENE_FALLBACKS.get(character_key, 'hero_default_rei.png')
        else:
            fname = self.SCENE_FALLBACKS.get(image_type, '')
        if not fname:
            return ''
        abs_path = self.scene_abs(fname)
        if not self.exists_abs(abs_path):
            return ''
        return self.scene(fname)
