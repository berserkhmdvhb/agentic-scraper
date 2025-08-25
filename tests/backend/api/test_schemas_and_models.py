from __future__ import annotations

import uuid
from typing import Any

import pytest
from pydantic import HttpUrl, ValidationError

from agentic_scraper.backend.api.models import OwnerSub, RequiredScopes
from agentic_scraper.backend.api.schemas.items import (
    ScrapedItemDynamicDTO,
    ScrapedItemFixedDTO,
)
from agentic_scraper.backend.api.schemas.scrape import (
    ScrapeCreate,
    ScrapeJob,
    ScrapeResultDynamic,
    ScrapeResultFixed,
)
from agentic_scraper.backend.api.schemas.user import (
    UserCredentialsIn,
    UserCredentialsOut,
    UserCredentialsStatus,
    UserProfile,
)
from agentic_scraper.backend.config.constants import (
    DEFAULT_AGENT_MODE,
    MAX_URLS_PER_REQUEST,
)
from agentic_scraper.backend.config.types import AgentMode, JobStatus, OpenAIModel
from agentic_scraper.backend.scraper.schemas import ScrapedItem


# -----------------------------
# ScrapeCreate (boundary input)
# -----------------------------

def test_scrape_create_urls_normalize_and_dedupe() -> None:
    data: dict[str, Any] = {
        "urls": [" https://example.com/a ", "https://example.com/a", "https://example.com/b"],
        "agent_mode": DEFAULT_AGENT_MODE,
        "openai_model": OpenAIModel.GPT_3_5,
        "llm_concurrency": 2,
        "llm_schema_retries": 1,
        "fetch_concurrency": 3,
        "screenshot_enabled": False,
        "verbose": False,
        "retry_attempts": 0,
    }
    sc = ScrapeCreate.model_validate(data)
    # HttpUrl coerces to str on model_dump, order preserved after dedupe
    assert [str(u) for u in sc.urls] == ["https://example.com/a", "https://example.com/b"]

def test_scrape_create_urls_must_be_list_type_error() -> None:
    with pytest.raises((TypeError, ValidationError)):
        # @field_validator("urls", mode="before") raises TypeError for non-list
        ScrapeCreate.model_validate({"urls": "https://example.com", "agent_mode": DEFAULT_AGENT_MODE})

def test_scrape_create_urls_max_len_enforced() -> None:
    urls = [f"https://example.com/{i}" for i in range(MAX_URLS_PER_REQUEST + 1)]
    with pytest.raises(ValidationError):
        ScrapeCreate.model_validate(
            {"urls": urls, "agent_mode": DEFAULT_AGENT_MODE, "openai_model": OpenAIModel.GPT_3_5}
        )

@pytest.mark.parametrize(
    "mode,requires_model",
    [
        (AgentMode.RULE_BASED, False),
        (AgentMode.LLM_FIXED, True),
        (AgentMode.LLM_DYNAMIC, True),
    ],
)
def test_scrape_create_openai_model_requirement(mode: AgentMode, requires_model: bool) -> None:
    payload = {
        "urls": ["https://example.com/x"],
        "agent_mode": mode,
        # openai_model omitted intentionally sometimes
    }
    if requires_model:
        with pytest.raises(ValidationError):
            ScrapeCreate.model_validate(payload)
    else:
        sc = ScrapeCreate.model_validate(payload)
        assert sc.agent_mode == AgentMode.RULE_BASED


# -----------------------------
# ScrapeJob (boundary output)
# -----------------------------

def test_scrape_job_parses_uuid4_and_progress_bounds() -> None:
    job_id = str(uuid.uuid4())
    job = ScrapeJob.model_validate(
        {
            "id": job_id,
            "status": JobStatus.QUEUED,
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
            "progress": 0.5,
            "error": None,
            "result": None,
        }
    )
    # id parsed to UUID object by the schema
    assert str(job.id) == job_id
    assert job.progress == 0.5

@pytest.mark.parametrize("bad_progress", [-0.01, 1.01])
def test_scrape_job_rejects_invalid_progress(bad_progress: float) -> None:
    with pytest.raises(ValidationError):
        ScrapeJob.model_validate(
            {
                "id": str(uuid.uuid4()),
                "status": JobStatus.QUEUED,
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
                "progress": bad_progress,
            }
        )

def test_scrape_job_error_empty_string_rejected() -> None:
    with pytest.raises(ValidationError):
        ScrapeJob.model_validate(
            {
                "id": str(uuid.uuid4()),
                "status": JobStatus.FAILED,
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
                "error": "  ",
            }
        )


# -------------------------------------
# Scrape results (from_internal helpers)
# -------------------------------------

def test_scrape_result_fixed_and_dynamic_from_internal() -> None:
    # Build internal ScrapedItem (allows extra fields)
    item = ScrapedItem.model_validate(
        {
            "url": "https://example.com/alpha",
            "title": "Hello",
            "description": None,
            "price": 12.34,
            "author": None,
            "date_published": None,
            "screenshot_path": None,
            "rating": 5,  # extra
        }
    )
    stats = {"total_urls": 1, "succeeded": 1, "failed": 0, "duration_sec": 0.01}

    fixed = ScrapeResultFixed.from_internal([item], stats)
    dynamic = ScrapeResultDynamic.from_internal([item], stats)

    assert isinstance(fixed, ScrapeResultFixed)
    assert isinstance(dynamic, ScrapeResultDynamic)

    # Fixed DTO should drop extras; Dynamic DTO should keep extras
    fixed_item = fixed.items[0].model_dump()
    dynamic_item = dynamic.items[0].model_dump()

    assert "rating" not in fixed_item
    assert dynamic_item.get("rating") == 5


# -----------------------------
# Item DTOs (boundary objects)
# -----------------------------

def test_item_dto_requires_http_url_and_cleans_optionals() -> None:
    # Valid URL (HttpUrl is validated by the model from a plain string)
    ok = ScrapedItemFixedDTO(url="https://example.com")
    # Pydantic normalizes bare origins to include a trailing slash
    assert str(ok.url) == "https://example.com/"
    # Empty optionals rejected (validators convert empty -> error)
    with pytest.raises(ValidationError):
        ScrapedItemFixedDTO(url="https://example.com", title="  ")

def test_item_dynamic_allows_extra_fields() -> None:
    dto = ScrapedItemDynamicDTO(url="https://example.com", foo="bar")
    assert dto.model_extra and dto.model_extra.get("foo") == "bar"


# -----------------------------
# User schemas
# -----------------------------

def test_user_credentials_in_project_id_trim_and_non_empty() -> None:
    creds = UserCredentialsIn(api_key="sk-abc", project_id="  proj_123  ")
    assert creds.project_id == "proj_123"

    with pytest.raises(ValidationError):
        UserCredentialsIn(api_key="sk-abc", project_id="   ")

def test_user_credentials_out_shape() -> None:
    out = UserCredentialsOut(api_key="sk-********************************cdef", project_id="proj_123")
    assert out.api_key.endswith("cdef")
    assert out.project_id == "proj_123"

def test_user_credentials_status_simple() -> None:
    status = UserCredentialsStatus(has_credentials=True)
    assert status.has_credentials is True

def test_user_profile_validations() -> None:
    profile = UserProfile(sub="  auth0|abc123  ", email="u@example.com", name="Alice ")
    assert profile.sub == "auth0|abc123"
    assert profile.email == "u@example.com"
    assert profile.name == "Alice"

    with pytest.raises(ValidationError):
        UserProfile(sub="  ", email=None, name=None)

    with pytest.raises(ValidationError):
        UserProfile(sub="auth0|abc", email="not-an-email", name=None)

    with pytest.raises(ValidationError):
        UserProfile(sub="auth0|abc", email=None, name="  ")


# -----------------------------
# Auth models (OwnerSub, scopes)
# -----------------------------

def test_owner_sub_from_value() -> None:
    good = OwnerSub.from_value("auth0|abc123")
    assert isinstance(good, OwnerSub)
    assert str(good) == "auth0|abc123"

    with pytest.raises(ValueError):
        _ = OwnerSub.from_value("no-pipe-here")

def test_required_scopes_values() -> None:
    values = {s.value for s in RequiredScopes}
    assert "create:scrapes" in values
    assert "read:scrapes" in values
    assert "cancel:scrapes" in values
    assert "read:user_profile" in values
    assert "create:openai_credentials" in values
