from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "农民工工资专户管理服务"
    API_V1_PREFIX: str = "/api/v1"
    DATABASE_URL: str = "sqlite:///./salary_account.db"
    DEBUG: bool = True

    class Config:
        env_file = ".env"


settings = Settings()
