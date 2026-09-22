"""Application boundaries: resources, transactions, readiness and CLI entry points."""

import io
import runpy
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic_ai.models.test import TestModel
from sqlalchemy.exc import OperationalError

import db.session as sessions
import dependencies.providers as providers
import main
from core.config import get_settings
from errors import register_exception_handlers
from ingest import __main__ as ingest_cli
from ingest.report import IngestReport
from llm import eval as evaluation
from llm.eval_cases import EvalCase
from schemas.search import SearchIntent


@asynccontextmanager
async def session_context(session: AsyncMock) -> AsyncIterator[AsyncMock]:
    yield session


async def test_session_commit_and_rollback(monkeypatch: pytest.MonkeyPatch) -> None:
    session = AsyncMock()
    monkeypatch.setattr(
        sessions, "get_session_factory", lambda: lambda: session_context(session)
    )
    iterator = sessions.get_session()
    assert await anext(iterator) is session
    with pytest.raises(StopAsyncIteration):
        await anext(iterator)
    session.commit.assert_awaited_once()
    iterator = sessions.get_session()
    await anext(iterator)
    with pytest.raises(ValueError, match="failed"):
        await iterator.athrow(ValueError("failed"))
    session.rollback.assert_awaited_once()


async def test_engine_factory_and_cache_lifecycle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sessions.get_engine.cache_clear()
    sessions.get_session_factory.cache_clear()
    try:
        engine = sessions.get_engine()
        assert sessions.get_engine() is engine
        assert sessions.get_session_factory().kw["bind"] is engine
        await engine.dispose()
    finally:
        sessions.get_engine.cache_clear()
        sessions.get_session_factory.cache_clear()
    client = AsyncMock()
    monkeypatch.setattr(providers.Redis, "from_url", Mock(return_value=client))
    providers.get_cache.cache_clear()
    try:
        cache = providers.get_cache()
        assert providers.get_cache() is cache
        await cache.close()
        client.aclose.assert_awaited_once()
    finally:
        providers.get_cache.cache_clear()


@pytest.mark.parametrize("model", [None, TestModel()])
def test_agent_providers(
    monkeypatch: pytest.MonkeyPatch, model: TestModel | None
) -> None:
    monkeypatch.setattr(providers, "build_model", lambda _: model)
    for factory in (providers.get_intent_agent, providers.get_assistant_agent):
        factory.cache_clear()
        try:
            agent = factory()
            assert (agent is None) == (model is None)
            assert factory() is agent
        finally:
            factory.cache_clear()


async def test_startup_bootstraps_and_shutdown_releases_resources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session, service, cache, engine = (AsyncMock() for _ in range(4))
    monkeypatch.setattr(
        main, "get_session_factory", lambda: lambda: session_context(session)
    )
    monkeypatch.setattr(main, "get_auth_service", lambda *_: service)
    monkeypatch.setattr(main, "get_cache", lambda: cache)
    monkeypatch.setattr(main, "get_engine", lambda: engine)
    async with main.lifespan(FastAPI()):
        service.ensure_admin.assert_awaited_once()
        session.commit.assert_awaited_once()
        cache.close.assert_not_awaited()
    cache.close.assert_awaited_once()
    engine.dispose.assert_awaited_once()


async def test_readiness_redis_failure(app: FastAPI, client: AsyncClient) -> None:
    database = AsyncMock()
    cache = AsyncMock()
    cache.ping.return_value = False
    app.dependency_overrides[providers.get_health_repository] = lambda: database
    app.dependency_overrides[providers.get_cache] = lambda: cache
    response = await client.get("/health/ready")
    assert response.status_code == 503
    database.ping.assert_awaited_once()


async def test_database_failure_is_sanitized() -> None:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/broken")
    def broken() -> None:
        raise OperationalError("secret SQL", {}, RuntimeError("secret credentials"))

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/broken")
    assert response.status_code == 503
    assert "secret" not in response.text


def test_offline_migrations_produce_schema() -> None:
    output = io.StringIO()
    config = Config("alembic.ini", output_buffer=output)
    config.attributes["database_url"] = get_settings().test_database_url
    command.upgrade(config, "head", sql=True)
    assert "CREATE TABLE users" in output.getvalue()
    assert "CREATE TABLE chats" in output.getvalue()


async def test_ingest_transaction_and_cleanup(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    session, cache, engine, pipeline = (AsyncMock() for _ in range(4))
    report = IngestReport()
    pipeline.run.return_value = report
    monkeypatch.setattr(
        ingest_cli, "get_session_factory", lambda: lambda: session_context(session)
    )
    monkeypatch.setattr(ingest_cli, "get_cache", lambda: cache)
    monkeypatch.setattr(ingest_cli, "get_engine", lambda: engine)
    monkeypatch.setattr(ingest_cli, "IngestPipeline", lambda *_: pipeline)
    assert await ingest_cli.run_ingest(tmp_path / "cars.csv") is report
    session.commit.assert_awaited_once()
    cache.close.assert_awaited_once()
    engine.dispose.assert_awaited_once()
    pipeline.run.side_effect = ValueError("bad CSV")
    with pytest.raises(ValueError, match="bad CSV"):
        await ingest_cli.run_ingest(tmp_path / "cars.csv")
    assert session.commit.await_count == 1
    assert cache.close.await_count == engine.dispose.await_count == 2


def test_ingest_cli_validation_and_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("sys.argv", ["ingest"])
    with pytest.raises(SystemExit, match="usage:"):
        ingest_cli.main()
    monkeypatch.setattr("sys.argv", ["ingest", str(tmp_path / "missing")])
    with pytest.raises(SystemExit, match="not a file"):
        ingest_cli.main()
    csv = tmp_path / "cars.csv"
    csv.write_text("id\n")
    monkeypatch.setattr("sys.argv", ["ingest", str(csv)])
    monkeypatch.setattr(
        ingest_cli, "run_ingest", AsyncMock(return_value=IngestReport())
    )
    ingest_cli.main()
    assert capsys.readouterr().out


def test_ingest_module_usage(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.argv", ["ingest"])
    with pytest.raises(SystemExit, match="usage:"):
        runpy.run_module("ingest.__main__", run_name="__main__")


async def test_eval_without_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(evaluation, "build_model", lambda _: None)
    with pytest.raises(SystemExit, match="LLM_API_KEY"):
        await evaluation.main()


async def test_eval_reports_accuracy(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    agent = SimpleNamespace(
        run=AsyncMock(return_value=SimpleNamespace(output=SearchIntent()))
    )
    monkeypatch.setattr(evaluation, "build_model", lambda _: TestModel())
    monkeypatch.setattr(evaluation, "build_intent_agent", lambda _: agent)
    monkeypatch.setattr(
        evaluation,
        "EVAL_CASES",
        [
            EvalCase(
                query="test", expected={"only_below_market": False}, vehicle_words=()
            )
        ],
    )
    await evaluation.main()
    assert "1/1 = 100%" in capsys.readouterr().out


def test_eval_module_requires_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("llm.model_factory.build_model", lambda _: None)
    with pytest.raises(SystemExit, match="LLM_API_KEY"):
        runpy.run_module("llm.eval", run_name="__main__")
