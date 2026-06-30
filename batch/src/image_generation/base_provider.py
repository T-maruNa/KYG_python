from abc import ABC, abstractmethod
from typing import Optional


# 将来 Stability AI や SD WebUI など別プロバイダーを追加するときは
# このクラスを継承して generate() を実装するだけでよい
class BaseImageProvider(ABC):
    @abstractmethod
    def generate(self, prompt: str, reference_images: list = None) -> Optional[str]:
        """
        画像を生成してURLを返す。失敗時はNoneを返す。
        reference_images: ローカルファイルパスのリスト（キャラの基準画像など）
        """
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str: ...  # DB記録用 ('openai' など)

    @property
    @abstractmethod
    def model_name(self) -> str: ...     # DB記録用 ('gpt-image-1' など)
