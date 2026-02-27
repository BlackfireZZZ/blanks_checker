from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    APP_NAME: str = "Blanks Checker"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    API_PORT: int = 80

    DB_HOST: str = "db"
    DB_PORT: int = 5432
    DB_NAME: str = "blanks"
    DB_USER: str = "postgres"
    DB_PASSWORD: str = "postgres"

    S3_ENDPOINT_URL: str = "http://minio:9000"
    S3_PUBLIC_URL: str = "http://localhost:9000"
    S3_ACCESS_KEY_ID: str = "minioadmin"
    S3_SECRET_ACCESS_KEY: str = "minioadmin"
    S3_REGION: str = "us-east-1"
    S3_BUCKET_NAME: str = "blanks-artifacts"
    S3_USE_SSL: bool = False

    ADMIN_LOGIN: str = ""
    ADMIN_PASSWORD: str = ""
    JWT_SECRET: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24 * 7  # 1 week

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    @property
    def DATABASE_URL_SYNC(self) -> str:
        return (
            f"postgresql+psycopg2://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )


settings = Settings()
