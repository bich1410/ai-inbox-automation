from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    llm_provider: str = "gemini"
    llm_api_key: str
    llm_model: str
    llm_fallback_model: str | None = None
    agent_model: str | None = None  # để trống thì agent dùng llm_model
    embedding_model: str = "gemini-embedding-001"
    database_url: str


settings = Settings()