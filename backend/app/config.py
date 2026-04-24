from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Claude / Anthropic
    anthropic_api_key: str

    # OpenMetadata — use 127.0.0.1 explicitly; Python 3.13 resolves "localhost"
    # to ::1 (IPv6) first which fails when OM only listens on 0.0.0.0 (IPv4).
    openmetadata_host: str = "http://127.0.0.1:8585"
    openmetadata_jwt_token: str

    # GitHub App (all optional — not required for local dev without webhook)
    github_app_id: str | None = None
    github_app_private_key_path: str | None = None
    github_webhook_secret: str | None = None

    # Extra CORS origins (comma-separated, e.g. "https://my-app.vercel.app")
    cors_allowed_origins: str = ""

    # App
    app_version: str = "1.0.0"
    log_level: str = "INFO"
    fluxguardian_env: str = "dev"   # "dev" | "prod"


settings = Settings()  # type: ignore[call-arg]
