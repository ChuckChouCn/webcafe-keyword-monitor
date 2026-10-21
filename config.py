import os
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
REPORTS_DIR = DATA_DIR / "reports"

DATA_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "keywords.db"

# ----------------------------------------------------------------------
# Environment Variables (.env) Loader
# ----------------------------------------------------------------------
def _load_env_file(env_path: Path):
    if not env_path.exists():
        return
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip("'\"")
                if k and k not in os.environ:
                    os.environ[k] = v
    except Exception as e:
        print(f"[!] 加载 .env 异常: {e}")

_load_env_file(BASE_DIR / ".env")

# ----------------------------------------------------------------------
# WebCafe API Configuration
# ----------------------------------------------------------------------
WEBCAFE_API_BASE = os.getenv("WEBCAFE_API_BASE", "https://seo.web.cafe/api/v1")
WEBCAFE_TOKEN = os.getenv("WEBCAFE_TOKEN", "")

# ----------------------------------------------------------------------
# AI Gatekeeper Configuration (DeepSeek / Compatible API)
# ----------------------------------------------------------------------
DEEPSEEK_API_URL = os.getenv("DEEPSEEK_API_URL", "https://api.deepseek.com/chat/completions")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")

# ----------------------------------------------------------------------
# Feishu Official App Configuration
# ----------------------------------------------------------------------
FEISHU_APP_ID = os.getenv("FEISHU_APP_ID", "")
FEISHU_APP_SECRET = os.getenv("FEISHU_APP_SECRET", "")
FEISHU_BITABLE_APP_TOKEN = os.getenv("FEISHU_BITABLE_APP_TOKEN", "")
FEISHU_BITABLE_TABLE_ID = os.getenv("FEISHU_BITABLE_TABLE_ID", "")
FEISHU_CHAT_ID = os.getenv("FEISHU_CHAT_ID", "")

# ----------------------------------------------------------------------
# cc-connect Session Configuration
# ----------------------------------------------------------------------
CC_CONNECT_SESSION_KEY = os.getenv("CC_CONNECT_SESSION_KEY", "")

DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) WebCafeMonitor/1.0"
