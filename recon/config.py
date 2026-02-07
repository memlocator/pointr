from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Recon service settings"""

    # External APIs
    crt_sh_api_url: str = "https://crt.sh/"
    cymru_asn_domain: str = "origin.asn.cymru.com"
    cymru_asn_details_domain: str = "asn.cymru.com"

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
