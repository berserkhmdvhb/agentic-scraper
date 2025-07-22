# test_settings_validators.py

import os
from pprint import pprint
from agentic_scraper.backend.core.settings import Settings

# Simulate .env or environment vars (overrides .env file)
os.environ["OPENAI_API_KEY"] = "sk-test1234567890abcdef"
os.environ["OPENAI_PROJECT_ID"] = "test-project"
os.environ["LLM_MAX_TOKENS"] = "300"
os.environ["LLM_TEMPERATURE"] = "0.7"
os.environ["MAX_CONCURRENT_REQUESTS"] = "5"
os.environ["ENV"] = "prod"
os.environ["DEBUG"] = "True"
os.environ["LOG_LEVEL"] = "debug"
os.environ["LOG_MAX_BYTES"] = "500000"
os.environ["LOG_BACKUP_COUNT"] = "3"
os.environ["LOG_FORMAT"] = "json"

try:
    settings = Settings()
    print("✅ Settings loaded and validated successfully!\n")
    pprint(settings.model_dump())
except Exception as e:
    print("❌ Validation failed: ", e)
