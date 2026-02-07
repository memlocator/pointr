from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Enrichment service settings"""

    # External APIs
    overpass_api_url: str = "https://overpass-api.de/api/interpreter"

    # Service Configuration
    enrichment_port: int = 50051

    # Rate Limiting
    overpass_rate_limit: int = 120

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False
    }


settings = Settings()
