"""Runtime configuration loaded from environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Agent runtime configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Claude API
    anthropic_api_key: str = ""
    claude_model: str = "claude-haiku-4-5-20251001"

    # Search provider
    search_api_key: str = ""
    search_provider: str = "brave"  # brave | serpapi | tavily

    # Fan-out settings
    max_sources: int = 4             # max parallel sub-agents
    max_content_chars: int = 6000    # scrape content truncation before extraction call

    # Request behavior
    request_timeout: float = 30.0
    max_retries: int = 3

    # Scrape settings
    playwright_timeout: int = 30_000  # ms

    # Logging
    log_level: str = "INFO"

    # User-agent pool selection
    user_agent_pool: str = "default"


settings = Settings()
