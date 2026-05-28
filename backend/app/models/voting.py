import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import VotingAccessType, VotingStatus
from app.database.base import Base


class Voting(Base):
    __tablename__ = "votings"
    __table_args__ = (
        CheckConstraint(
            "end_date_time > start_date_time",
            name="ck_votings_end_after_start",
        ),
        Index("ix_votings_status_end_date_time", "status", "end_date_time"),
        Index("ix_votings_created_by_status", "created_by", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    access_type: Mapped[VotingAccessType] = mapped_column(
        SAEnum(VotingAccessType, name="voting_access_type"),
        nullable=False,
    )
    is_anonymous: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    invitation_code: Mapped[Optional[str]] = mapped_column(
        String(64),
        unique=True,
        nullable=True,
    )

    start_date_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    end_date_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    status: Mapped[VotingStatus] = mapped_column(
        SAEnum(VotingStatus, name="voting_status"),
        nullable=False,
        default=VotingStatus.draft,
        server_default="draft",
        index=True,
    )

    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    publish_tx_hash: Mapped[Optional[str]] = mapped_column(
        String(66),
        nullable=True,
    )
    finalize_tx_hash: Mapped[Optional[str]] = mapped_column(
        String(66),
        nullable=True,
    )
