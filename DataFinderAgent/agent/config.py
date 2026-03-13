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
    claude_model: str = "claude-sonnet-4-6"

    # Search provider
    search_api_key: str = ""
    search_provider: str = "brave"  # brave | serpapi | tavily

    # Loop limits
    max_loops: int = 10
    checkpoint_loop: int = 5
    hard_stop_loop: int = 15

    # Request behavior
    request_delay_min: float = 2.0
    request_delay_max: float = 5.0
    request_timeout: float = 30.0
    max_retries: int = 3
    max_attempts_per_domain: int = 3

    # Scrape settings
    playwright_timeout: int = 30_000  # ms
    max_content_tokens: int = 2000    # truncate scrape results before feeding to LLM

    # Logging
    log_level: str = "INFO"

    # User-agent pool selection
    user_agent_pool: str = "default"


settings = Settings()
