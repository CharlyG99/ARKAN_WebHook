from pydantic_settings import BaseSettings
import os
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    mongo_uri: str = os.getenv("MONGO_URI")
    mongo_db_name: str = os.getenv("MONGO_DB_NAME")
    encryption_key: str = os.getenv("ENCRYPTION_KEY")
    secret: str = os.getenv("SECRET")
    host_url: str = os.getenv("HOST_URL")
    api_port: int = int(os.getenv("API_PORT", "8000"))
    debug: bool = os.getenv("DEBUG", "False").lower() == "true"
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    tg_token: str = os.getenv("TG_TOKEN")
    chan_id: str = os.getenv("CHAN_ID")
    rate_limit: str = os.getenv("RATE_LIMIT")
    api_key: str = os.getenv("API_KEY")
    admin_api_key: str = os.getenv("ADMIN_API_KEY")    
    class Config:
        env_file = ".env"


settings = Settings()
