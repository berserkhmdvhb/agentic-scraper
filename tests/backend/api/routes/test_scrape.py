from __future__ import annotations

from collections.abc import Callable
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

import httpx
import pytest
from fastapi import status

from agentic_scraper import __api_version__ as api_version
from agentic_scraper.backend.api.schemas.scrape import ScrapeJob, ScrapeList
from agentic_scraper.backend.api.stores import job_store as js
from agentic_scraper.backend.config.types import JobStatus


def _unique_sub(tag: str) -> str:
    """Stable-but-unique Auth0 sub per test to isolate listing by owner."""
    return f"auth0|{uuid5(NAMESPACE_URL, tag)}"


@pytest.mark.asyncio
async def test_create_scrape_job_accepted_sets_location_and_body(
    monkeypatch: pytest.MonkeyPatch,
    test_client: httpx.AsyncClient,
    make_jwt: Callable[..., str],
    jwks_mock: None,
    api_base: str,
) -> None:
    # Stub the background task to a no-op so the pipeline doesn't run.
    async def _noop(*_args: Any, **_kwargs: Any) -> None:
        return None

    import agentic_scraper.backend.api.routes.scrape as scrape_routes
    monkeypatch.setattr(scrape_routes, "_run_scrape_job", _noop, raising=True)

    sub = _unique_sub("create-ok")
    test_client.headers.update({
        "Authorization": f"Bearer {make_jwt(sub=sub, scope=['create:scrapes','read:scrapes'])}"
    })

    payload = {
        "urls": [
            "https://example.com/a",
            "https://example.com/b",
            "https://example.com/c",
        ],
    }
    res = await test_client.post(f"{api_base}/scrapes/", json=payload)
    assert res.status_code == status.HTTP_202_ACCEPTED, f"422 detail: {res.text}"

    job = ScrapeJob.model_validate(res.json())
    assert isinstance(job.id, UUID)
    assert str(job.status).lower() == "queued"

    loc = res.headers.get("Location")
    assert isinstance(loc, str)
    assert loc.endswith(f"/api/{api_version}/scrapes/{job.id!s}")


@pytest.mark.asyncio
async def test_create_scrape_job_invalid_urls_returns_422(
    monkeypatch: pytest.MonkeyPatch,
    test_client: httpx.AsyncClient,
    make_jwt: Callable[..., str],
    jwks_mock: None,
    api_base: str,
) -> None:
    async def _noop(*_args: Any, **_kwargs: Any) -> None:
        return None

    import agentic_scraper.backend.api.routes.scrape as scrape_routes
    monkeypatch.setattr(scrape_routes, "_run_scrape_job", _noop, raising=True)

    sub = _unique_sub("create-bad-url")
    test_client.headers.update({"Authorization": f"Bearer {make_jwt(sub=sub, scope='create:scrapes')}"})

    res = await test_client.post(
        f"{api_base}/scrapes/",
        json={"urls": ["not-a-url"]},
    )
    assert res.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


@pytest.mark.asyncio
async def test_list_scrape_jobs_default_and_pagination(
    monkeypatch: pytest.MonkeyPatch,
    test_client: httpx.AsyncClient,
    make_jwt: Callable[..., str],
    jwks_mock: None,
    api_base: str,
) -> None:
    async def _noop(*_args: Any, **_kwargs: Any) -> None:
        return None

    import agentic_scraper.backend.api.routes.scrape as scrape_routes
    monkeypatch.setattr(scrape_routes, "_run_scrape_job", _noop, raising=True)

    sub = _unique_sub("list-default")
    test_client.headers.update({
        "Authorization": f"Bearer {make_jwt(sub=sub, scope=['create:scrapes','read:scrapes'])}"
    })

    ids: list[str] = []
    for suffix in ("/a", "/b", "/c"):
        r = await test_client.post(
            f"{api_base}/scrapes/",
            json={"urls": [f"https://example.com{suffix}"]},
        )
        assert r.status_code == status.HTTP_202_ACCEPTED
        ids.append(str(ScrapeJob.model_validate(r.json()).id))

    res1 = await test_client.get(f"{api_base}/scrapes/")
    assert res1.status_code == status.HTTP_200_OK
    body1 = ScrapeList.model_validate(res1.json())
    assert [str(it.id) for it in body1.items] == ids
    assert body1.next_cursor is None

    res2 = await test_client.get(f"{api_base}/scrapes/?limit=2")
    assert res2.status_code == status.HTTP_200_OK
    body2 = ScrapeList.model_validate(res2.json())
    assert len(body2.items) == 2
    cur = body2.next_cursor
    assert isinstance(cur, str)

    res3 = await test_client.get(f"{api_base}/scrapes/?cursor={cur}")
    assert res3.status_code == status.HTTP_200_OK
    body3 = ScrapeList.model_validate(res3.json())
    assert [str(it.id) for it in body3.items] == [ids[2]]
    assert body3.next_cursor is None


@pytest.mark.asyncio
async def test_list_scrape_jobs_status_filter_and_limit_zero(
    monkeypatch: pytest.MonkeyPatch,
    test_client: httpx.AsyncClient,
    make_jwt: Callable[..., str],
    jwks_mock: None,
    api_base: str,
) -> None:
    async def _noop(*_args: Any, **_kwargs: Any) -> None:
        return None

    import agentic_scraper.backend.api.routes.scrape as scrape_routes
    monkeypatch.setattr(scrape_routes, "_run_scrape_job", _noop, raising=True)

    sub = _unique_sub("list-status")
    test_client.headers.update({
        "Authorization": f"Bearer {make_jwt(sub=sub, scope=['create:scrapes','read:scrapes'])}"
    })

    r1 = await test_client.post(
        f"{api_base}/scrapes/",
        json={"urls": ["https://example.com/one"]},
    )
    r2 = await test_client.post(
        f"{api_base}/scrapes/",
        json={"urls": ["https://example.com/two"]},
    )
    assert r1.status_code == r2.status_code == status.HTTP_202_ACCEPTED

    j2 = ScrapeJob.model_validate(r2.json())
    _ = js.update_job(str(j2.id), status=JobStatus.RUNNING)

    res = await test_client.get(f"{api_base}/scrapes/?status_=running")
    assert res.status_code == status.HTTP_200_OK
    body = ScrapeList.model_validate(res.json())
    assert [it.id for it in body.items] == [j2.id]

    res0 = await test_client.get(f"{api_base}/scrapes/?limit=0")
    assert res0.status_code == status.HTTP_200_OK
    body0 = ScrapeList.model_validate(res0.json())
    assert body0.items == []
    assert body0.next_cursor is None


@pytest.mark.asyncio
async def test_list_scrape_jobs_invalid_limit_cursor_and_status(
    test_client: httpx.AsyncClient,
    make_jwt: Callable[..., str],
    jwks_mock: None,
    api_base: str,
) -> None:
    sub = _unique_sub("list-invalids")
    test_client.headers.update({"Authorization": f"Bearer {make_jwt(sub=sub, scope='read:scrapes')}"})

    res_limit = await test_client.get(f"{api_base}/scrapes/?limit=-1")
    assert res_limit.status_code == status.HTTP_400_BAD_REQUEST

    res_cursor = await test_client.get(f"{api_base}/scrapes/?cursor=not-a-uuid")
    assert res_cursor.status_code == status.HTTP_400_BAD_REQUEST

    res_status = await test_client.get(f"{api_base}/scrapes/?status_=bogus")
    assert res_status.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.asyncio
async def test_get_scrape_job_404_and_forbidden_on_owner_mismatch(
    monkeypatch: pytest.MonkeyPatch,
    test_client: httpx.AsyncClient,
    make_jwt: Callable[..., str],
    jwks_mock: None,
    api_base: str,
) -> None:
    # Stub background runner
    async def _noop(*_args: Any, **_kwargs: Any) -> None:
        return None

    import agentic_scraper.backend.api.routes.scrape as scrape_routes
    monkeypatch.setattr(scrape_routes, "_run_scrape_job", _noop, raising=True)

    # Reader token (will try to GET)
    reader_sub = _unique_sub("get-forbidden-reader")
    test_client.headers.update({"Authorization": f"Bearer {make_jwt(sub=reader_sub, scope='read:scrapes')}"})

    # Swap to creator token to create a job owned by someone else
    owner_sub = _unique_sub("get-forbidden-owner")
    test_client.headers.update({"Authorization": f"Bearer {make_jwt(sub=owner_sub, scope='create:scrapes')}"})
    create_res = await test_client.post(
        f"{api_base}/scrapes/",
        json={"urls": ["https://example.com/owned-by-else"]},
    )
    assert create_res.status_code == status.HTTP_202_ACCEPTED
    job_id = create_res.json()["id"]

    # Restore reader token
    test_client.headers.update({"Authorization": f"Bearer {make_jwt(sub=reader_sub, scope='read:scrapes')}"})

    # 404 for missing job
    res_missing = await test_client.get(f"{api_base}/scrapes/{uuid4()}")
    assert res_missing.status_code == status.HTTP_404_NOT_FOUND

    # 403 for owner mismatch
    res_forbid = await test_client.get(f"{api_base}/scrapes/{job_id}")
    assert res_forbid.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_cancel_scrape_job_happy_and_idempotent(
    monkeypatch: pytest.MonkeyPatch,
    test_client: httpx.AsyncClient,
    make_jwt: Callable[..., str],
    jwks_mock: None,
    api_base: str,
) -> None:
    async def _noop(*_args: Any, **_kwargs: Any) -> None:
        return None

    import agentic_scraper.backend.api.routes.scrape as scrape_routes
    monkeypatch.setattr(scrape_routes, "_run_scrape_job", _noop, raising=True)

    sub = _unique_sub("cancel-ok")
    test_client.headers.update({
        "Authorization": f"Bearer {make_jwt(sub=sub, scope=['cancel:scrapes','read:scrapes','create:scrapes'])}"
    })

    r = await test_client.post(
        f"{api_base}/scrapes/",
        json={"urls": ["https://example.com/cancel-me"]},
    )

    assert r.status_code == status.HTTP_202_ACCEPTED
    jid = ScrapeJob.model_validate(r.json()).id

    res1 = await test_client.delete(f"{api_base}/scrapes/{jid}")
    assert res1.status_code == status.HTTP_204_NO_CONTENT

    res2 = await test_client.delete(f"{api_base}/scrapes/{jid}")
    assert res2.status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.asyncio
async def test_cancel_scrape_job_not_found_and_not_cancelable(
    monkeypatch: pytest.MonkeyPatch,
    test_client: httpx.AsyncClient,
    make_jwt: Callable[..., str],
    jwks_mock: None,
    api_base: str,
) -> None:
    async def _noop(*_args: Any, **_kwargs: Any) -> None:
        return None

    import agentic_scraper.backend.api.routes.scrape as scrape_routes
    monkeypatch.setattr(scrape_routes, "_run_scrape_job", _noop, raising=True)

    sub = _unique_sub("cancel-misc")
    test_client.headers.update({
        "Authorization": f"Bearer {make_jwt(sub=sub, scope=['cancel:scrapes','read:scrapes','create:scrapes'])}"
    })

    res_missing = await test_client.delete(f"{api_base}/scrapes/{uuid4()}")
    assert res_missing.status_code == status.HTTP_404_NOT_FOUND

    r = await test_client.post(
        f"{api_base}/scrapes/",
        json={"urls": ["https://example.com/done"]},
    )
    assert r.status_code == status.HTTP_202_ACCEPTED
    jid = ScrapeJob.model_validate(r.json()).id
    _ = js.update_job(str(jid), status=JobStatus.SUCCEEDED)

    res_conflict = await test_client.delete(f"{api_base}/scrapes/{jid}")
    assert res_conflict.status_code == status.HTTP_409_CONFLICT


@pytest.mark.asyncio
async def test_scope_enforcement(
    monkeypatch: pytest.MonkeyPatch,
    test_client: httpx.AsyncClient,
    make_jwt: Callable[..., str],
    jwks_mock: None,
    api_base: str,
) -> None:
    # Stub background runner (we create jobs below)
    async def _noop(*_args: Any, **_kwargs: Any) -> None:
        return None

    import agentic_scraper.backend.api.routes.scrape as scrape_routes
    monkeypatch.setattr(scrape_routes, "_run_scrape_job", _noop, raising=True)

    # Missing create scope -> 401/403
    sub_ro = _unique_sub("scopes-read-only")
    test_client.headers.update({
        "Authorization": f"Bearer {make_jwt(sub=sub_ro, scope='read:scrapes')}"
    })
    res_create = await test_client.post(
        f"{api_base}/scrapes/",
        json={"urls": ["https://example.com"]},
    )
    assert res_create.status_code in {status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN}

    # Missing cancel scope -> 401/403
    sub_nc = _unique_sub("scopes-no-cancel")
    test_client.headers.update({
        "Authorization": f"Bearer {make_jwt(sub=sub_nc, scope=['read:scrapes','create:scrapes'])}"
    })
    r = await test_client.post(
        f"{api_base}/scrapes/",
        json={"urls": ["https://example.com/need-cancel"]},
    )
    assert r.status_code == status.HTTP_202_ACCEPTED
    jid = ScrapeJob.model_validate(r.json()).id

    res_cancel = await test_client.delete(f"{api_base}/scrapes/{jid}")
    assert res_cancel.status_code in {status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN}
