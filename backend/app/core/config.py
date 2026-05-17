from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = ""
    jwt_secret: str = ""
    app_salt: str = ""
    backend_private_key: str = ""
    sepolia_rpc_url: str = ""
    contract_address: str = ""

    model_config = {"env_file": ".env"}


settings = Settings()
