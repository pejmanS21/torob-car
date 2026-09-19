import time
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from db.ids import new_uuid8
from models.city import City

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent


def test_new_uuid8_is_version_8_and_time_ordered() -> None:
    first = new_uuid8()
    time.sleep(0.002)
    second = new_uuid8()
    assert first.version == second.version == 8
    assert first < second


@pytest.mark.db
async def test_migration_installs_pg_trgm_and_the_trigram_indexes(
    session: AsyncSession,
) -> None:
    extensions = await session.scalars(text("SELECT extname FROM pg_extension"))
    assert "pg_trgm" in set(extensions)
    indexes = await session.scalars(
        text("SELECT indexname FROM pg_indexes WHERE schemaname = 'public'")
    )
    assert {"ix_listings_title_trgm", "ix_vehicle_catalog_trim_trgm"} <= set(indexes)


@pytest.mark.db
def test_models_and_migrations_do_not_drift(migrated_database_url: str) -> None:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "db" / "migrations"))
    config.attributes["database_url"] = migrated_database_url
    command.check(config)  # raises if autogenerate would produce a new migration


@pytest.mark.db
async def test_primary_keys_are_generated_app_side(session: AsyncSession) -> None:
    city = City(name="شهر آزمایشی", name_normalized="شهر آزمایشی")
    session.add(city)
    await session.flush()
    assert city.id.version == 8
