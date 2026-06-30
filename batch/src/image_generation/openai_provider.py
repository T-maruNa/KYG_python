"""OpenAI Images API を使った画像生成 provider"""
import os
from typing import Optional
from .base_provider import BaseImageProvider
from config.config import config


class OpenAIImageProvider(BaseImageProvider):
    def __init__(self):
        # openai パッケージは optional 依存なので遅延インポート
        from openai import OpenAI
        self._client = OpenAI(api_key=config.IMAGE_API_KEY)
        self._model = config.IMAGE_MODEL  # 例: 'gpt-image-1'

    @property
    def provider_name(self) -> str:
        return 'openai'

    @property
    def model_name(self) -> str:
        return self._model

    def generate(self, prompt: str, reference_images: list = None) -> Optional[str]:
        """
        画像を生成してURLを返す。失敗時は None を返す。

        reference_images にキャラの基準画像（base.png）が渡された場合は
        images.edit を使ってキャラの外見を維持しながら生成する。
        ファイルが存在しない場合は通常の images.generate にフォールバックする。
        """
        try:
            if reference_images:
                # 実際にディスク上に存在するファイルだけ使う
                existing = [p for p in reference_images if os.path.exists(p)]
                if existing:
                    # 複数渡されても最初の1枚のみ使用（API制約）
                    with open(existing[0], 'rb') as f:
                        response = self._client.images.edit(
                            model=self._model,
                            image=f,
                            prompt=prompt,
                            n=1,
                            size='1024x1024',
                        )
                    return response.data[0].url

            # 参照画像なし → テキストプロンプトのみで生成
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
