import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import BlockchainRecordStatus
from app.database.base import Base


class BlockchainRecord(Base):
    __tablename__ = "blockchain_records"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
        nullable=False,
    )
    vote_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("votes.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    tx_hash: Mapped[Optional[str]] = mapped_column(
        String(66),
        nullable=True,
        index=True,
    )
    status: Mapped[BlockchainRecordStatus] = mapped_column(
        SAEnum(BlockchainRecordStatus, name="blockchain_record_status"),
        nullable=False,
        default=BlockchainRecordStatus.pending,
        server_default="pending",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
