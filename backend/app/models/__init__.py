"""SQLAlchemy ORM models. See docs/ARCHITECTURE.md for the entity diagram."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(120), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    # Incremented to invalidate every issued session token (password change, sign out everywhere).
    token_version: Mapped[int] = mapped_column(Integer, default=0)


class Property(TimestampMixin, Base):
    __tablename__ = "properties"
    __table_args__ = (Index("ix_properties_owner_created", "owner_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(200))
    address_line: Mapped[str] = mapped_column(String(300), default="")
    town: Mapped[str] = mapped_column(String(120), default="")
    postcode: Mapped[str | None] = mapped_column(String(10), nullable=True, index=True)
    region: Mapped[str] = mapped_column(String(20), default="england")
    property_type: Mapped[str] = mapped_column(String(20), default="flat")
    tenure: Mapped[str] = mapped_column(String(20), default="leasehold")
    bedrooms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bathrooms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    floor_area_sqm: Mapped[float | None] = mapped_column(Float, nullable=True)
    asking_price: Mapped[float] = mapped_column(Float)
    estimated_monthly_rent: Mapped[float] = mapped_column(Float)
    # Where the rent figure came from: user_estimate | agent_quote | current_tenancy | demo
    rent_source: Mapped[str] = mapped_column(String(30), default="user_estimate")
    listing_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    # Provenance of the record itself: manual | csv_import | demo
    data_source: Mapped[str] = mapped_column(String(20), default="manual")
    import_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("data_imports.id", ondelete="SET NULL"), nullable=True
    )
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    # Per-property overrides of the user's assumption profile (subset of DealInputs).
    assumption_overrides: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class AssumptionProfile(TimestampMixin, Base):
    __tablename__ = "assumption_profiles"
    __table_args__ = (UniqueConstraint("owner_id", "name"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    values: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class Analysis(Base):
    __tablename__ = "analyses"
    __table_args__ = (Index("ix_analyses_owner_created", "owner_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    property_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("properties.id", ondelete="CASCADE"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    inputs: Mapped[dict[str, Any]] = mapped_column(JSON)
    results: Mapped[dict[str, Any]] = mapped_column(JSON)
    engine_version: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    explanations: Mapped[list[AIExplanation]] = relationship(
        back_populates="analysis", cascade="all, delete-orphan", passive_deletes=True
    )


class AIExplanation(Base):
    __tablename__ = "ai_explanations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    analysis_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("analyses.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(30))
    model: Mapped[str] = mapped_column(String(100))
    content: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    analysis: Mapped[Analysis] = relationship(back_populates="explanations")


class Comparison(TimestampMixin, Base):
    __tablename__ = "comparisons"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    # Shared assumptions applied identically to every property in the comparison.
    assumptions: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    items: Mapped[list[ComparisonItem]] = relationship(
        back_populates="comparison",
        cascade="all, delete-orphan",
        order_by="ComparisonItem.position",
        passive_deletes=True,
    )


class ComparisonItem(Base):
    __tablename__ = "comparison_items"
    __table_args__ = (UniqueConstraint("comparison_id", "property_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    comparison_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("comparisons.id", ondelete="CASCADE"), index=True)
    property_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("properties.id", ondelete="CASCADE"))
    position: Mapped[int] = mapped_column(Integer, default=0)

    comparison: Mapped[Comparison] = relationship(back_populates="items")
    property: Mapped[Property] = relationship()


class Watchlist(TimestampMixin, Base):
    __tablename__ = "watchlists"
    __table_args__ = (UniqueConstraint("owner_id", "name"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")

    items: Mapped[list[WatchlistItem]] = relationship(
        back_populates="watchlist",
        cascade="all, delete-orphan",
        order_by="WatchlistItem.added_at",
        passive_deletes=True,
    )


class WatchlistItem(Base):
    __tablename__ = "watchlist_items"
    __table_args__ = (UniqueConstraint("watchlist_id", "property_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    watchlist_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("watchlists.id", ondelete="CASCADE"), index=True)
    property_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("properties.id", ondelete="CASCADE"))
    note: Mapped[str] = mapped_column(Text, default="")
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    watchlist: Mapped[Watchlist] = relationship(back_populates="items")
    property: Mapped[Property] = relationship()


class DataImport(Base):
    __tablename__ = "data_imports"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # Null for system imports run from the CLI.
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # properties_csv (private to the owner) | land_registry_ppd (shared market data)
    kind: Mapped[str] = mapped_column(String(30))
    # processing | completed | completed_with_errors | failed
    status: Mapped[str] = mapped_column(String(30), default="processing")
    filename: Mapped[str] = mapped_column(String(255))
    sha256: Mapped[str] = mapped_column(String(64))
    rows_total: Mapped[int] = mapped_column(Integer, default=0)
    rows_imported: Mapped[int] = mapped_column(Integer, default=0)
    rows_rejected: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    source_name: Mapped[str] = mapped_column(String(200))
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    licence: Mapped[str | None] = mapped_column(String(200), nullable=True)
    attribution: Mapped[str | None] = mapped_column(Text, nullable=True)
    data_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    data_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PricePaidTransaction(Base):
    """A residential sale from HM Land Registry Price Paid Data."""

    __tablename__ = "price_paid_transactions"
    __table_args__ = (
        Index("ix_ppd_district_date", "postcode_district", "date_of_transfer"),
        Index("ix_ppd_sector_date", "postcode_sector", "date_of_transfer"),
        Index("ix_ppd_local_authority", "local_authority"),
    )

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    transaction_id: Mapped[str] = mapped_column(String(38), unique=True)
    price: Mapped[int] = mapped_column(Integer)
    date_of_transfer: Mapped[date] = mapped_column(Date, index=True)
    postcode: Mapped[str | None] = mapped_column(String(10), nullable=True)
    postcode_district: Mapped[str | None] = mapped_column(String(5), nullable=True)
    postcode_sector: Mapped[str | None] = mapped_column(String(7), nullable=True)
    property_type: Mapped[str] = mapped_column(String(1))
    new_build: Mapped[bool] = mapped_column(Boolean)
    tenure: Mapped[str] = mapped_column(String(1))
    paon: Mapped[str] = mapped_column(String(120), default="")
    saon: Mapped[str] = mapped_column(String(120), default="")
    street: Mapped[str] = mapped_column(String(120), default="")
    locality: Mapped[str] = mapped_column(String(120), default="")
    town: Mapped[str] = mapped_column(String(120), default="")
    local_authority: Mapped[str] = mapped_column(String(120), default="")
    county: Mapped[str] = mapped_column(String(120), default="")
    ppd_category: Mapped[str] = mapped_column(String(1))
    import_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("data_imports.id", ondelete="SET NULL"), nullable=True
    )


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    analysis_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("analyses.id", ondelete="SET NULL"), nullable=True)
    comparison_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("comparisons.id", ondelete="SET NULL"), nullable=True
    )
    kind: Mapped[str] = mapped_column(String(10))  # pdf | csv
    title: Mapped[str] = mapped_column(String(200))
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    content: Mapped[bytes] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
