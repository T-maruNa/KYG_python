from typing import Dict, List
from src.ai_clients.openai_client import OpenAIClient

class Sumirei:
    def __init__(self):
        self.name = "rei"
        self.name_jp = "鷲見 玲"
        self.title = "テクニカル分析のエキスパート"
        self.style = "テクニカル分析重視"
        self.description = "チャートパターン、移動平均線、RSIなどのテクニカル指標を重視し、短期的な値動きを予測します。"
        self.focus = "チャートパターン、出来高、移動平均線"
        self.model = "openai"
        self.client = OpenAIClient()

    def stock_run(self, messages: List[Dict[str, str]]) -> str:
        """
        株価予測を実行する

        Args:
            messages (List[Dict[str, str]]): チャットメッセージのリスト

        Returns:
            str: 予測結果のCSVテキスト
        """
        print(f"\n=== {self.name_jp}の分析 ===")
        print(f"専門: {self.title}")
        print(f"分析スタイル: {self.style}")
        print(f"注目ポイント: {self.focus}")
        print("-" * 50)
        
        result = self.client.execute_chat(messages)
        
        print(f"\n分析結果:\n{result}")
        print("=" * 50)
        
        return result 