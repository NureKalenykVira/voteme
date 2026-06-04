from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = ""
    jwt_secret: str = ""
    app_salt: str = ""
    backend_private_key: str = ""
    sepolia_rpc_url: str = ""
    contract_address: str = ""
    access_token_expire_minutes: int = 30
    cors_origins: list[str] = [
        "http://localhost:4200",
        "http://127.0.0.1:4200",
    ]
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_start_tls: bool = False
    smtp_use_tls: bool = False
    frontend_url: str = "http://localhost:4200"
    app_timezone: str = "Europe/Kyiv"
    gmail_client_id: str = ""
    gmail_client_secret: str = ""
    gmail_refresh_token: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
