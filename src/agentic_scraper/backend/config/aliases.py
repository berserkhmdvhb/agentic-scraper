from typing import Literal

# ---------------------------------------------------------------------
# core/
# ---------------------------------------------------------------------

# settings.py
Environment = Literal["DEV", "UAT", "PROD"]
LogFormat = Literal["plain", "json"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
OpenAIModel = Literal["gpt-3.5-turbo", "gpt-4", "gpt-4o"]
