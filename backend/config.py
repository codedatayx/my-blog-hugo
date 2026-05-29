import os

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"
DB_PATH = os.getenv("DB_PATH", "data/memory.db")
SOUL_PATH = os.getenv("SOUL_PATH", "soul.md")

# Memory settings
REDIS_TTL = 7200          # 2 hours
REDIS_MAX_TURNS = 20      # max turns in short-term memory
COMPRESS_THRESHOLD = 10   # compress every N turns
SUMMARY_MAX_TOKENS = 200
CHAT_MAX_TOKENS = 600

# Agent settings
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_REPO = os.getenv("GITHUB_REPO", "codedatayx/my-blog-hugo")
GITHUB_BRANCH = os.getenv("GITHUB_BRANCH", "main")
