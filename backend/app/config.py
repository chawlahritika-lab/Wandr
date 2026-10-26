from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Wandr API"
    debug: bool = False
    api_prefix: str = "/api"
    database_url: str = "sqlite:///./wandr.db"
    openai_api_key: str | None = None
    azure_openai_endpoint: str | None = None
    azure_openai_api_key: str | None = None
    azure_openai_deployment: str | None = None
    azure_openai_api_version: str = "2024-10-21"
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-3-5-sonnet-latest"
    anthropic_api_version: str = "2023-06-01"
    groq_api_key: str | None = None
    groq_model: str = "openai/gpt-oss-20b"
    agent_timeout_seconds: float = 45.0
    agent_min_confidence: float = 0.65
    google_maps_api_key: str | None = None
    google_places_base_url: str = "https://maps.googleapis.com/maps/api/place"
    research_timeout_seconds: float = 20.0
    research_max_results: int = 4
    research_cache_ttl_seconds: int = 3600

    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")


settings = Settings()
