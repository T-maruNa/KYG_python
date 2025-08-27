import os
from dotenv import load_dotenv

# .envファイルを読み込む
load_dotenv()

class Config:
    OPENAI_STOCK_API_KEY = os.getenv("OPENAI_STOCK_API_KEY")
    OPENAI_BLOG_API_KEY = os.getenv("OPENAI_BLOG_API_KEY")
    GEMINI_STOCK_API_KEY = os.getenv("GEMINI_STOCK_API_KEY")
    GEMINI_BLOG_API_KEY = os.getenv("GEMINI_BLOG_API_KEY")
    DB = 'KYG.db'
config = Config() 