from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all ORM models."""


class TenantScopedBase(Base):
    """Base class for tenant-scoped tables.

    CONVENTIONS.md rule #3: no database query without tenant scoping.
    Every table holding tenant data must extend this base, and every
    query against it must filter on tenant_id — see db/session.py.
    """

    __abstract__ = True

    tenant_id: Mapped[str] = mapped_column(index=True, nullable=False)
