import json
from pydantic import BaseModel
from pydantic_settings import BaseSettings


class AdditionalDB(BaseModel):
    """Configuration for an additional PostGIS data source."""
    name: str
    url: str
    table: str
    geom_col: str
    name_col: str
    category_col: str = ""
    description_col: str = ""


class Settings(BaseSettings):
    """Geo data service settings"""

    # External APIs
    overpass_api_url: str = "https://overpass-api.de/api/interpreter"

    # Service Configuration
    geo_port: int = 50051

    # Rate Limiting
    overpass_rate_limit: int = 120

    # Database
    geo_db_url: str = ""

    # Additional PostGIS sources (JSON array of AdditionalDB configs)
    geo_additional_dbs: str = "[]"

    @property
    def additional_dbs(self) -> list[AdditionalDB]:
        try:
            return [AdditionalDB(**item) for item in json.loads(self.geo_additional_dbs)]
        except Exception:
            return []

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False
    }


settings = Settings()
