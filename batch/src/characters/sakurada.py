from typing import Dict, List
from src.ai_clients.gemini_client import GeminiClient

class SakuradaMirai:
    def __init__(self):
        self.name = "mirai"
        self.name_jp = "桜庭 みらい"
        self.title = "前向きの可愛い分析家"
        self.style = "ファンダメンタル分析が多め、色々な方法で分析"
        self.description = "企業、社長、従業員のSNS人気度、従業員の働きやすさ、おしゃれさを重視し、短期的な成長性を予測します。"
        self.focus = "SNS人気度、従業員の働きやすさ、おしゃれさ"
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