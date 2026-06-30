"""OpenAI Images API を使った画像生成 provider"""
import os
from typing import Optional
from .base_provider import BaseImageProvider
from config.config import config


class OpenAIImageProvider(BaseImageProvider):
    def __init__(self):
        from openai import OpenAI
        self._client = OpenAI(api_key=config.IMAGE_API_KEY)
        self._model = config.IMAGE_MODEL

    @property
    def provider_name(self) -> str:
        return 'openai'

    @property
    def model_name(self) -> str:
        return self._model

    def generate(self, prompt: str, reference_images: list = None) -> Optional[str]:
        """
        画像を生成してURLを返す。
        reference_images が指定された場合、最初のファイルを使って images.edit を呼ぶ。
        失敗時は None を返す。
        """
        try:
            if reference_images:
                existing = [p for p in reference_images if os.path.exists(p)]
                if existing:
                    with open(existing[0], 'rb') as f:
                        response = self._client.images.edit(
                            model=self._model,
                            image=f,
                            prompt=prompt,
                            n=1,
                            size='1024x1024',
                        )
                    return response.data[0].url

            response = self._client.images.generate(
                model=self._model,
                prompt=prompt,
                n=1,
                size='1024x1024',
            )
            return response.data[0].url
        except Exception as e:
            print(f'[OpenAIImageProvider] 生成失敗: {e}')
            return None
