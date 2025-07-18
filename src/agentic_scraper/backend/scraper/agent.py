import logging
import json
from openai import AsyncOpenAI, OpenAIError, RateLimitError, APIError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from agentic_scraper.backend.core.settings import settings
from agentic_scraper.backend.scraper.models import ScrapedItem


logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

logger = logging.getLogger(__name__)
client = AsyncOpenAI(api_key=settings.openai_api_key)

SYSTEM_PROMPT = """
You are a web extraction assistant. Your job is to extract key data from webpage content.
Return only a JSON object with the following fields:
- title (string or null)
- description (string or null)
- price (float or null)
- author (string or null)
- date_published (string or null)

All values must be valid JSON. If a field is not found, return null for it.
"""


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(OpenAIError),
    reraise=True,
)
async def extract_structured_data(text: str, url: str) -> ScrapedItem:
    """
    Use an LLM to extract structured data from raw page text.

    Args:
        text (str): Cleaned text content extracted from the webpage.
        url (str): Source URL of the page (included in returned schema).

    Returns:
        ScrapedItem: Pydantic model with structured data.

    Raises:
        ValueError: If LLM output is not valid JSON or schema is malformed.
    """
    messages: list[dict[str, str]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": text[:4000]},
    ]

    try:
        response = await client.chat.completions.create(
            model=settings.openai_model,
            messages=messages,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
            response_format="json",
        )

        try:
            content = response.choices[0].message.content
        except Exception:
            logger.error("LLM response missing or malformed: %s", response)
            raise ValueError("No valid message content returned from OpenAI.")

        try:
            raw_data = json.loads(content)
        except json.JSONDecodeError as e:
            logger.error("Failed to decode JSON from LLM response: %s", content)
            raise ValueError(f"Failed to parse structured output from LLM: {e}")

        return ScrapedItem(url=url, **raw_data)

    except RateLimitError as e:
        logger.error("OpenAI quota exceeded: %s", e)
        raise ValueError(
            "OpenAI quota exceeded. Please check your usage and billing at https://platform.openai.com/account/usage."
        )
    except APIError as e:
        logger.error("OpenAI API error occurred: %s", e)
        logger.debug("Full exception details:", exc_info=True)
        raise ValueError(f"OpenAI API error occurred: {e}")
    except OpenAIError as e:
        logger.error("Unexpected OpenAI error: %s", e)
        raise ValueError(f"Unexpected OpenAI error: {e}")
