from typing import Dict, List
from src.ai_clients.gemini_client import GeminiClient

class IchinoseRitu:
    def __init__(self):
        self.name = "ritu"
        self.name_jp = "一ノ瀬 律"
        self.title = "まったく株の事はわかりません"
        self.style = "分析なんてしない勘で選ぶ"
        self.description = "敬語は使わず、豪快な性格の女性です。話し方は男らしいですが、女性です。"
        self.focus = "ガチの乱数"
        self.model = "gemini"
        self.client = GeminiClient()

    def stock_run(self, messages: List[Dict[str, str]]) -> None:
        """
        株価予測を実行する

        Args:
            messages (List[Dict[str, str]]): チャットメッセージのリスト
        """
        print(f"\n=== {self.name}の分析 ===")
        print(f"専門: {self.title}")
        print(f"分析スタイル: {self.style}")
        print(f"注目ポイント: {self.focus}")
        print("-" * 50)
        
        result = self.client.execute_chat(messages)
        
        print(f"\n分析結果:\n{result}")
        print("=" * 50) 
        return result 