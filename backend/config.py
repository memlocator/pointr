from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # External APIs
    nominatim_api_url: str = "https://nominatim.openstreetmap.org"
    user_agent: str = "Pointr/1.0"

    # Service Configuration
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    enrichment_host: str = "enrichment"
    enrichment_port: int = 50051
    recon_host: str = "recon"
    recon_port: int = 50052

    # CORS
    cors_origins: list[str] = ["http://localhost:5173"]

    # Rate Limiting
    nominatim_rate_limit: int = 60

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False
    }


settings = Settings()
