import uuid

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from errors import ListingNotFoundError, register_exception_handlers


def _failing_app() -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/missing")
    async def missing() -> None:
        raise ListingNotFoundError(uuid.UUID(int=7))

    @app.get("/boom")
    async def boom() -> None:
        raise RuntimeError("secret detail")

    @app.get("/typed/{number}")
    async def typed(number: int) -> int:
        return number

    return app


async def _get(path: str) -> tuple[int, dict]:
    transport = ASGITransport(app=_failing_app(), raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        response = await http.get(path)
    return response.status_code, response.json()


async def test_app_error_becomes_structured_envelope() -> None:
    status, body = await _get("/missing")
    assert status == 404
    assert body["error"]["code"] == "listing_not_found"
    assert body["error"]["details"] == {"listing_id": str(uuid.UUID(int=7))}


async def test_unhandled_error_is_generic_and_leaks_nothing() -> None:
    status, body = await _get("/boom")
    assert status == 500
    assert body["error"]["code"] == "internal_error"
    assert "secret detail" not in str(body)


async def test_validation_error_uses_the_same_envelope() -> None:
    status, body = await _get("/typed/not-a-number")
    assert status == 422
    assert body["error"]["code"] == "validation_error"
    assert isinstance(body["error"]["details"], list)


async def test_unknown_route_uses_the_same_envelope() -> None:
    status, body = await _get("/nope")
    assert status == 404
    assert body["error"]["code"] == "http_error"
