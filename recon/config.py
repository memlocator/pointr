from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Recon service settings"""

    # Application
    app_name: str = "Pointr"
    app_version: str = "1.0"

    # External APIs
    crt_sh_api_url: str = "https://crt.sh/"
    cymru_asn_domain: str = "origin.asn.cymru.com"
    cymru_asn_details_domain: str = "asn.cymru.com"

    @property
    def user_agent(self) -> str:
        """Dynamically generate user agent from app name and version"""
        return f"{self.app_name}-Recon/{self.app_version}"

    # Service Configuration
    recon_port: int = 50052
    max_workers: int = 5

    # Rate Limiting
    crt_sh_rate_limit: int = 300

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False
    }


settings = Settings()
