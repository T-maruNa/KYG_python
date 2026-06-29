import os
from functools import lru_cache

_PROMPTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    'prompts',
)


@lru_cache(maxsize=None)
def _load(filename: str) -> str:
    path = os.path.join(_PROMPTS_DIR, filename)
    try:
        with open(path, encoding='utf-8') as f:
            return f.read().strip()
    except FileNotFoundError:
        return ''


class PromptLoader:
    """prompts/ ディレクトリのMarkdownファイルを読み込んで返す。

    キャラクター設定や共通ルールを変更する場合は、コードではなく
    prompts/ 以下のファイルを編集してください。
    """

    @staticmethod
    def character_profile() -> str:
        return _load('character_profile.md')

    @staticmethod
    def common_rules() -> str:
        return _load('common_rules.md')

    @staticmethod
    def prediction_article() -> str:
        return _load('prediction_article_prompt.md')

    @staticmethod
    def result_article() -> str:
        return _load('result_article_prompt.md')

    @staticmethod
    def talk() -> str:
        return _load('talk_prompt.md')

    @staticmethod
    def base_system(role: str = '投資シミュレーションブログの脚本家') -> str:
        """共通ルール + キャラクター設定を結合したシステムプロンプトを返す。"""
        return (
            f'あなたは{role}です。\n\n'
            f'## 共通ルール\n\n{PromptLoader.common_rules()}\n\n'
            f'## キャラクター設定\n\n{PromptLoader.character_profile()}'
        )

    @staticmethod
    def character_system(analyst_name: str, name_jp: str) -> str:
        """特定キャラクターとして話すためのシステムプロンプトを返す。"""
        profile_text = PromptLoader.character_profile()
        rules_text = PromptLoader.common_rules()
        return (
            f'あなたは{name_jp}（{analyst_name}）です。\n\n'
            f'## 共通ルール\n\n{rules_text}\n\n'
            f'## キャラクター設定\n\n{profile_text}'
        )
