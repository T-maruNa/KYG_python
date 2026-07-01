from typing import Dict, List
from src.ai_clients.openai_client import OpenAIClient


class IchinoseRitu:
    def __init__(self):
        self.name = "ritu"
        self.name_jp = "一ノ瀬 律"
        self.model = "openai"
        self.client = OpenAIClient()

    def stock_run(self, messages: List[Dict[str, str]]) -> str:
        print(f"\n=== {self.name_jp}の分析 ===")
        result = self.client.execute_chat(messages)
        print(f"\n分析結果:\n{result}")
        return result
