from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Claude / Anthropic
    anthropic_api_key: str

    # OpenMetadata
    openmetadata_host: str = "http://localhost:8585"
    openmetadata_jwt_token: str

    # GitHub App (all optional — not required for local dev without webhook)
    github_app_id: str | None = None
    github_app_private_key_path: str | None = None   # path to .pem file on disk
    github_webhook_secret: str | None = None

    # App
    app_version: str = "0.1.0"
    fluxguardian_env: str = "dev"   # "dev" | "prod"


settings = Settings()  # type: ignore[call-arg]
