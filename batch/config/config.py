import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # AI API
    OPENAI_STOCK_API_KEY = os.getenv('OPENAI_STOCK_API_KEY')
    OPENAI_BLOG_API_KEY = os.getenv('OPENAI_BLOG_API_KEY')
    GEMINI_STOCK_API_KEY = os.getenv('GEMINI_STOCK_API_KEY')
    GEMINI_BLOG_API_KEY = os.getenv('GEMINI_BLOG_API_KEY')

    # DB
    DB = 'KYG.db'

    # WordPress
    WORDPRESS_BASE_URL = os.getenv('WORDPRESS_BASE_URL', '')
    WORDPRESS_USERNAME = os.getenv('WORDPRESS_USERNAME', '')
    WORDPRESS_APP_PASSWORD = os.getenv('WORDPRESS_APP_PASSWORD', '')


config = Config()
