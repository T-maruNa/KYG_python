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
    ENABLE_MONTHLY_MVP_IMAGE = os.getenv('ENABLE_MONTHLY_MVP_IMAGE', 'true').lower() == 'true'
    MAX_CANDIDATES_PER_RANGE = int(os.getenv('MAX_CANDIDATES_PER_RANGE', '30'))

    # AI呼び出し1回あたりの推定コスト（円）— 超えたら月次予算チェックに使う
    ESTIMATED_COST_PER_CALL_JPY = float(os.getenv('ESTIMATED_COST_PER_CALL_JPY', '30'))

    # キャラクター固定画像URL（未設定の場合はプレースホルダー）
    IMG_MORNING_SCENE = os.getenv('IMG_MORNING_SCENE', '')  # 朝の作戦会議 固定フォールバック画像
    IMG_EVENING_SCENE = os.getenv('IMG_EVENING_SCENE', '')  # 夜の反省会 固定フォールバック画像
    IMG_REI   = os.getenv('IMG_REI', '')                    # 玲の固定フォールバック画像
    IMG_MIRAI = os.getenv('IMG_MIRAI', '')                  # みらいの固定フォールバック画像
    IMG_RITU  = os.getenv('IMG_RITU', '')                   # 律の固定フォールバック画像

    # 画像生成プロバイダー設定
    IMAGE_PROVIDER = os.getenv('IMAGE_PROVIDER', 'openai')
    IMAGE_MODEL    = os.getenv('IMAGE_MODEL', 'gpt-image-1')
    IMAGE_API_KEY  = os.getenv('IMAGE_API_KEY') or os.getenv('OPENAI_STOCK_API_KEY')

    # 画像自動生成設定
    ENABLE_DAILY_IMAGE_GENERATION   = os.getenv('ENABLE_DAILY_IMAGE_GENERATION', 'false').lower() == 'true'
    DAILY_IMAGE_GENERATION_LIMIT    = int(os.getenv('DAILY_IMAGE_GENERATION_LIMIT', '5'))
    IMAGE_RETRY_LIMIT               = int(os.getenv('IMAGE_RETRY_LIMIT', '1'))
    ENABLE_MORNING_SCENE_IMAGE      = os.getenv('ENABLE_MORNING_SCENE_IMAGE', 'true').lower() == 'true'
    ENABLE_MORNING_SUB_SCENE_IMAGE  = os.getenv('ENABLE_MORNING_SUB_SCENE_IMAGE', 'true').lower() == 'true'
    ENABLE_HERO_SCENE_IMAGE         = os.getenv('ENABLE_HERO_SCENE_IMAGE', 'true').lower() == 'true'
    ENABLE_NIGHT_REFLECTION_SCENE   = os.getenv('ENABLE_NIGHT_REFLECTION_SCENE', 'true').lower() == 'true'
    ENABLE_HIGHLIGHT_SCENE_IMAGE    = os.getenv('ENABLE_HIGHLIGHT_SCENE_IMAGE', 'true').lower() == 'true'


config = Config()
