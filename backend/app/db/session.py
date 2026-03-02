from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.core.config import settings

# Use NullPool when connecting through Supabase's pgbouncer pooler (port 6543)
# to avoid double-pooling; use standard pool for local postgres
_use_null_pool = "pooler.supabase.com" in settings.DATABASE_URL or ":6543/" in settings.DATABASE_URL
_pool_kwargs = {"poolclass": NullPool} if _use_null_pool else {
    "pool_size": 10, "max_overflow": 20, "pool_timeout": 30, "pool_pre_ping": True,
}
_connect_args = {"prepare_threshold": None} if _use_null_pool else {}
engine = create_async_engine(settings.DATABASE_URL, echo=False, future=True, connect_args=_connect_args, **_pool_kwargs)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
