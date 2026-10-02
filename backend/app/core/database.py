import json
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

settings = get_settings()

def _json_serializer(value) -> str:
    """Used for every JSON column in the app. The stdlib json encoder
    can't serialize a Decimal on its own - default=str stringifies
    anything like that instead of raising, so a Decimal slipping into
    a JSON column fails safely as a readable string rather than
    crashing the request with a 500."""
    return json.dumps(value, default=str)

engine = create_async_engine(settings.database_url, echo=(settings.environment == "development"), json_serializer=_json_serializer)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
