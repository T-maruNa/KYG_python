from abc import ABC, abstractmethod
from typing import Optional


class BaseImageProvider(ABC):
    @abstractmethod
    def generate(self, prompt: str, reference_images: list = None) -> Optional[str]:
        """
        画像を生成してURLを返す。失敗時はNoneを返す。
        reference_images: ローカルファイルパスのリスト（参照画像）
        """
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str: ...

    @property
    @abstractmethod
    def model_name(self) -> str: ...
