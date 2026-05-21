from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+asyncpg://patentis:patentis@localhost:5433/patentis"
    redis_url: str = "redis://localhost:6379/0"

    platform_jwt_secret: str = "change-me-in-production-use-long-random"
    platform_api_keys: str = ""  # comma-separated

    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_chat_model: str = "gpt-4o-mini"
    openai_vision_model: str = "gpt-4o"

    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_deployment_chat: str = ""

    patentsview_api_key: str = ""
    medtech_cpc_prefixes: str = "A61B,A61F,A61N"

    epo_client_id: str = ""
    epo_client_secret: str = ""

    lens_api_token: str = ""
    semantic_scholar_api_key: str = ""

    azure_ml_subscription_id: str = ""
    model_registry_active_sft: str = ""  # path or deployment id when promoted

    org_adapters_blob_prefix: str = "org-adapters"
    org_adapters_local_root: str = "data"
    azure_org_adapters_container: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
