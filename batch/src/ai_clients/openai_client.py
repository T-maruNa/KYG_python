import openai
from openai import OpenAI
from typing import List, Dict
from config.config import config

class OpenAIClient:
    def __init__(self):
        self.client = OpenAI(
            api_key=config.OPENAI_STOCK_API_KEY
        )
        self.model = config.TEXT_MODEL
    def execute_chat(self, messages: List[Dict[str, str]]) -> str:
        """
        OpenAIのチャット完了APIを実行する

        Args:
            messages (List[Dict[str, str]]): チャットメッセージのリスト
            model (str, optional): 使用するモデル名. デフォルトは "gpt-4".

        Returns:
            str: モデルの応答テキスト
        """
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages
        )
        return response.choices[0].message.content 