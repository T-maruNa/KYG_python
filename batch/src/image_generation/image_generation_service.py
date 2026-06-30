"""
日替わり画像生成サービス。

使い方:
    service = ImageGenerationService()
    url = service.generate_morning_scene(target_date, context)
"""
import os
from typing import Optional, Dict
from config.config import config
from .base_provider import BaseImageProvider
from src.database.t_generated_images_manager import TGeneratedImagesManager

ASSETS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
    'assets',
)


def _char_asset(character: str, variant: str) -> str:
    return os.path.join(ASSETS_DIR, 'characters', character, f'{variant}.png')


def _scene_fallback(image_type: str, character_key: Optional[str] = None) -> Optional[str]:
    fallbacks = {
        'morning_scene':          os.path.join(ASSETS_DIR, 'scenes', 'morning_meeting_default.png'),
        'morning_sub_scene':      os.path.join(ASSETS_DIR, 'scenes', 'morning_sub_default.png'),
        'night_reflection_scene': os.path.join(ASSETS_DIR, 'scenes', 'night_reflection_default.png'),
        'highlight_scene':        os.path.join(ASSETS_DIR, 'scenes', 'highlight_default.png'),
    }
    if image_type == 'hero_scene' and character_key:
        path = _char_asset(character_key, 'normal')
        return path if os.path.exists(path) else None

    path = fallbacks.get(image_type)
    return path if path and os.path.exists(path) else None


class ImageGenerationService:
    def __init__(self, provider: Optional[BaseImageProvider] = None):
        if provider is None:
            provider = self._build_provider()
        self._provider = provider
        self._db = TGeneratedImagesManager()

    @staticmethod
    def _build_provider() -> BaseImageProvider:
        name = config.IMAGE_PROVIDER.lower()
        if name == 'openai':
            from .openai_provider import OpenAIImageProvider
            return OpenAIImageProvider()
        raise ValueError(f'未対応のIMAGE_PROVIDER: {name}')

    def _reference_images(self, characters: list) -> list:
        refs = []
        for char in characters:
            base = _char_asset(char, 'base')
            if os.path.exists(base):
                refs.append(base)
            ref_sheet = _char_asset(char, 'reference_sheet')
            if os.path.exists(ref_sheet):
                refs.append(ref_sheet)
        return refs

    def _generate(self, target_date: str, post_type: str, image_type: str,
                  character_key: Optional[str], prompt: str,
                  reference_characters: list) -> Optional[str]:
        if not config.ENABLE_DAILY_IMAGE_GENERATION:
            return None

        if self._db.count_today_generated(target_date) >= config.DAILY_IMAGE_GENERATION_LIMIT:
            print(f'[ImageGenerationService] 本日の生成上限到達 ({config.DAILY_IMAGE_GENERATION_LIMIT}枚)')
            return None

        ref_images = self._reference_images(reference_characters)
        url = None
        error_msg = None

        for attempt in range(1, config.IMAGE_RETRY_LIMIT + 2):
            try:
                url = self._provider.generate(prompt, ref_images)
                if url:
                    break
            except Exception as e:
                error_msg = str(e)
                print(f'[ImageGenerationService] {image_type} 生成失敗 ({attempt}回目): {e}')

        status = 'success' if url else 'failed'
        try:
            self._db.upsert(
                target_date=target_date,
                post_type=post_type,
                image_type=image_type,
                character_key=character_key,
                provider=self._provider.provider_name,
                model=self._provider.model_name,
                prompt=prompt,
                image_url=url,
                generation_status=status,
                error_message=error_msg,
            )
        except Exception as e:
            print(f'[ImageGenerationService] DB保存失敗: {e}')

        return url

    def _with_fallback(self, url: Optional[str], image_type: str,
                       character_key: Optional[str] = None) -> Optional[str]:
        if url:
            return url
        return _scene_fallback(image_type, character_key)

    # ------------------------------------------------------------------
    # 朝記事用
    # ------------------------------------------------------------------

    def generate_morning_scene(self, target_date: str, context: Dict) -> Optional[str]:
        if not config.ENABLE_MORNING_SCENE_IMAGE:
            return self._with_fallback(None, 'morning_scene')
        prompt = (
            'Anime illustration. Three young women at a morning strategy meeting in a cozy cafe. '
            'Left: adult woman with glasses, intelligent and calm (Rei). '
            'Center: short, energetic woman in a neat office suit (Mirai). '
            'Right: blonde gyaru woman, lively and cheerful (Ritu). '
            'Morning soft light, notebooks, smartphones, coffee cups on the table. '
            f'Atmosphere: {context.get("atmosphere", "bright and energetic")}. '
            'Pastel color palette, cute blog illustration style.'
        )
        url = self._generate(target_date, 'prediction_daily', 'morning_scene', None, prompt, ['rei', 'mirai', 'ritu'])
        return self._with_fallback(url, 'morning_scene')

    def generate_morning_sub_scene(self, target_date: str, context: Dict) -> Optional[str]:
        if not config.ENABLE_MORNING_SUB_SCENE_IMAGE:
            return self._with_fallback(None, 'morning_sub_scene')
        prompt = (
            'Compact anime illustration. Three young women glancing at each other with morning energy. '
            'Rei (glasses, calm adult), Mirai (short, office suit), Ritu (blonde gyaru). '
            f'Mood: {context.get("mood", "competitive yet friendly")}. '
            'Soft pastel, cute blog style, light background.'
        )
        url = self._generate(target_date, 'prediction_daily', 'morning_sub_scene', None, prompt, ['rei', 'mirai', 'ritu'])
        return self._with_fallback(url, 'morning_sub_scene')

    # ------------------------------------------------------------------
    # 夜記事用
    # ------------------------------------------------------------------

    def generate_hero_scene(self, target_date: str, hero_name: str,
                            expression: str, context: Dict) -> Optional[str]:
        if not config.ENABLE_HERO_SCENE_IMAGE:
            return self._with_fallback(None, 'hero_scene', hero_name)

        char_desc = {
            'rei':   'adult woman with glasses, calm and intelligent',
            'mirai': 'short young woman in office recruit suit, energetic',
            'ritu':  'blonde gyaru woman, lively',
        }.get(hero_name, 'young woman')

        prompt = (
            f'Anime illustration. Portrait of a {char_desc}. '
            f'Expression: {expression}. '
            f'Context: {context.get("scene_desc", "today stock battle result")}. '
            'Pastel color palette, cute blog illustration style, light background.'
        )
        url = self._generate(target_date, 'result_daily', 'hero_scene', hero_name, prompt, [hero_name])
        return self._with_fallback(url, 'hero_scene', hero_name)

    def generate_night_reflection_scene(self, target_date: str, context: Dict) -> Optional[str]:
        if not config.ENABLE_NIGHT_REFLECTION_SCENE:
            return self._with_fallback(None, 'night_reflection_scene')
        prompt = (
            'Anime illustration. Three young women at a cozy evening reflection meeting. '
            'Rei (glasses, calm), Mirai (short, office suit), Ritu (blonde gyaru). '
            'Night atmosphere, warm indoor lighting, notebooks or phones on table. '
            f'Mood: {context.get("mood", "reflective but friendly")}. '
            'Pastel color palette, cute blog illustration style.'
        )
        url = self._generate(target_date, 'result_daily', 'night_reflection_scene', None, prompt, ['rei', 'mirai', 'ritu'])
        return self._with_fallback(url, 'night_reflection_scene')

    def generate_highlight_scene(self, target_date: str, highlight_desc: str) -> Optional[str]:
        if not config.ENABLE_HIGHLIGHT_SCENE_IMAGE:
            return self._with_fallback(None, 'highlight_scene')
        prompt = (
            f'Anime illustration. Scene: {highlight_desc} '
            'Characters: Rei (glasses, adult woman), Mirai (short, office suit), Ritu (blonde gyaru). '
            'Pastel color palette, cute blog illustration style, expressive emotions.'
        )
        url = self._generate(target_date, 'result_daily', 'highlight_scene', None, prompt, ['rei', 'mirai', 'ritu'])
        return self._with_fallback(url, 'highlight_scene')
