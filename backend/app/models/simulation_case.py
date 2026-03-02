import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class SimulationCase(Base):
    __tablename__ = "simulation_cases"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    nodes: Mapped[dict] = mapped_column(JSONB, default=list)
    edges: Mapped[dict] = mapped_column(JSONB, default=list)
    simulation_basis: Mapped[dict] = mapped_column(JSONB, default=dict)
    property_package: Mapped[str] = mapped_column(String(50), default="PengRobinson")
    results: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
