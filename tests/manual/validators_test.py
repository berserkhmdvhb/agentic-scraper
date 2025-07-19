from agentic_scraper.backend.core.settings import Settings

# ✅ Example: valid config
try:
    settings = Settings(
        openai_api_key="sk-valid-key",
        openai_model="gpt-3.5-turbo",
        env="DEV",
        llm_temperature=0.7,
        max_concurrent_requests=10,
        request_timeout=5,
        llm_max_tokens=1000,
        log_level="debug",
        log_dir="logs",
        screenshot_dir="screenshots",
        log_max_bytes=1_000_000,
        log_backup_count=3,
    )
    print("✅ Settings loaded successfully:")
    print(settings.model_dump())
except Exception as e:
    print("❌ Validation error:")
    print(e)
