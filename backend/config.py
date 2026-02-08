from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Application
    app_name: str = "Pointr"
    app_version: str = "1.0"

    # External APIs
    nominatim_api_url: str = "https://nominatim.openstreetmap.org"
    osrm_api_url: str = "http://router.project-osrm.org"

    @property
    def user_agent(self) -> str:
        """Dynamically generate user agent from app name and version"""
        return f"{self.app_name}/{self.app_version}"

    # Service Configuration
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    geo_host: str = "geo"
    geo_port: int = 50051
    recon_host: str = "recon"
    recon_port: int = 50052

    # CORS
    cors_origins: list[str] = ["http://localhost:5173"]

    # Additional PostGIS sources (same JSON as GEO_ADDITIONAL_DBS)
    geo_additional_dbs: str = "[]"

    # Rate Limiting
    nominatim_rate_limit: int = 60

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False
    }


settings = Settings()
