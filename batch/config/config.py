import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # AI API
    OPENAI_STOCK_API_KEY = os.getenv('OPENAI_STOCK_API_KEY')
    OPENAI_BLOG_API_KEY = os.getenv('OPENAI_BLOG_API_KEY')
    GEMINI_STOCK_API_KEY = os.getenv('GEMINI_STOCK_API_KEY')
    GEMINI_BLOG_API_KEY = os.getenv('GEMINI_BLOG_API_KEY')

    # DB (PostgreSQL)
    DATABASE_URL = os.getenv('DATABASE_URL', '')

    # WordPress
    WORDPRESS_BASE_URL = os.getenv('WORDPRESS_BASE_URL', '')
    WORDPRESS_USERNAME = os.getenv('WORDPRESS_USERNAME', '')
    WORDPRESS_APP_PASSWORD = os.getenv('WORDPRESS_APP_PASSWORD', '')

    # AI API 予算ガード
    MONTHLY_AI_BUDGET_JPY = int(os.getenv('MONTHLY_AI_BUDGET_JPY', '3000'))
    DAILY_AI_CALL_LIMIT = int(os.getenv('DAILY_AI_CALL_LIMIT', '5'))
    AI_RETRY_LIMIT = int(os.getenv('AI_RETRY_LIMIT', '2'))
    ENABLE_DAILY_IMAGE_GENERATION = os.getenv('ENABLE_DAILY_IMAGE_GENERATION', 'false').lower() == 'true'
    ENABLE_MONTHLY_MVP_IMAGE = os.getenv('ENABLE_MONTHLY_MVP_IMAGE', 'true').lower() == 'true'
    MAX_CANDIDATES_PER_RANGE = int(os.getenv('MAX_CANDIDATES_PER_RANGE', '30'))

    # AI呼び出し1回あたりの推定コスト（円）— 超えたら月次予算チェックに使う
    ESTIMATED_COST_PER_CALL_JPY = float(os.getenv('ESTIMATED_COST_PER_CALL_JPY', '30'))

    # キャラクター画像URL（未設定の場合は画像なし）
    IMG_MORNING_SCENE = os.getenv('IMG_MORNING_SCENE', '')  # 朝の作戦会議 3人集合画像
    IMG_EVENING_SCENE = os.getenv('IMG_EVENING_SCENE', '')  # 夜の反省会 3人集合画像
    IMG_REI   = os.getenv('IMG_REI', '')                    # 玲のキャラ画像
    IMG_MIRAI = os.getenv('IMG_MIRAI', '')                  # みらいのキャラ画像
    IMG_RITU  = os.getenv('IMG_RITU', '')                   # 律のキャラ画像


config = Config()
