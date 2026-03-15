from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    asos_api_key: str
    kakao_api_key: Optional[str] = None
    debug: bool = False

    class Config:
        env_file = ".env"


settings = Settings()