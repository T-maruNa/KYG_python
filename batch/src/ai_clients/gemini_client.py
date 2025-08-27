import google.generativeai as genai
from typing import List, Dict
from config.config import config

class GeminiClient:
    def __init__(self):
        genai.configure(api_key=config.GEMINI_STOCK_API_KEY)
        self.model = "gemini-2.0-flash"
    def execute_chat(self, messages: List[Dict[str, str]]) -> str:
        """
        Geminiのチャット完了APIを実行する

        Args:
            messages (List[Dict[str, str]]): チャットメッセージのリスト

        Returns:
            str: モデルの応答テキスト
        """
        # メッセージをプロンプトに変換
        prompt = "\n".join([f"{msg['role']}: {msg['content']}" for msg in messages])
        
        # モデルの生成
        model = genai.GenerativeModel(self.model)
        response = model.generate_content(prompt)
        
        return response.text 