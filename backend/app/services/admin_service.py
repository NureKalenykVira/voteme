import json
import logging
import uuid
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import Role, VotingAccessType, VotingStatus
from app.core.security import hash_password
from app.models.user import User
from app.models.voting import Voting
from app.repositories.admin_stats_repository import AdminStatsRepository
from app.repositories.audit_repository import AuditRepository
from app.repositories.system_settings_repository import SystemSettingsRepository
from app.repositories.user_repository import UserRepository
from app.schemas.admin import (
    CreateUserRequest,
    RestoreResponse,
    SettingsResponse,
    SettingsUpdateRequest,
    StatsResponse,
)

logger = logging.getLogger(__name__)

_BACKUP_DIR = Path("uploads/backups")

# Default values used when a settings key is missing from the DB.
_SETTINGS_DEFAULTS: dict[str, str] = {
    "max_free_votings_per_month": "12",
    "maintenance_mode": "false",
    "require_email_verification": "true",
    "session_timeout_minutes": "2880",
}


def _parse_settings(raw: dict[str, str]) -> SettingsResponse:
    merged = {**_SETTINGS_DEFAULTS, **raw}
    return SettingsResponse(
        max_free_votings_per_month=int(merged["max_free_votings_per_month"]),
        maintenance_mode=merged["maintenance_mode"].lower() == "true",
        require_email_verification=merged["require_email_verification"].lower() == "true",
        session_timeout_minutes=int(merged["session_timeout_minutes"]),
    )


class AdminService:
    def __init__(self) -> None:
        self._users = UserRepository()
        self._audit = AuditRepository()
        self._settings_repo = SystemSettingsRepository()
        self._stats_repo = AdminStatsRepository()

    # ------------------------------------------------------------------
    # Users
    # ------------------------------------------------------------------

    async def list_users(
        self,
        session: AsyncSession,
        page: int,
        page_size: int,
        role: Optional[Role] = None,
        search: Optional[str] = None,
    ) -> tuple[list[User], int]:
        from sqlalchemy import func

        q = select(User)
        count_q = select(func.count()).select_from(User)

        # Include deleted users in admin list — admin may need to inspect them.
        if role is not None:
            q = q.where(User.role == role)
            count_q = count_q.where(User.role == role)

        if search:
            pattern = f"%{search}%"
            filter_expr = or_(
                User.email.ilike(pattern),
                User.full_name.ilike(pattern),
            )
            q = q.where(filter_expr)
            count_q = count_q.where(filter_expr)

        total: int = (await session.execute(count_q)).scalar_one()

        q = q.order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        items = list((await session.execute(q)).scalars().all())
        return items, total

    async def create_user(
        self,
        session: AsyncSession,
        payload: CreateUserRequest,
        actor_id: object,
    ) -> User:
        existing = await self._users.get_by_email(session, str(payload.email))
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered",
            )

        hashed = hash_password(payload.password)
        # Admin-created users are confirmed immediately — no email loop needed.
        confirmation_token = secrets.token_urlsafe(32)
        user = User(
            email=str(payload.email).lower(),
            hashed_password=hashed,
            full_name=payload.full_name,
            role=payload.role,
            is_confirmed=True,
            confirmation_token=confirmation_token,
        )
        session.add(user)
        await session.flush()

        await self._audit.create_entry(
            session,
            "ADMIN_USER_CREATED",
            actor_id=actor_id,  # type: ignore[arg-type]
            data={"email": user.email, "role": payload.role.value, "user_id": str(user.id)},
        )
        await session.commit()
        await session.refresh(user)
        return user

    async def patch_user_role(
        self,
        session: AsyncSession,
        user_id: object,
        new_role: Role,
        actor_id: object,
    ) -> User:
        user = await session.get(User, user_id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        previous_role = user.role.value
        if new_role.value == previous_role:
            return user
        user.role = new_role
        await session.flush()

        await self._audit.create_entry(
            session,
            "ADMIN_USER_ROLE_CHANGED",
            actor_id=actor_id,  # type: ignore[arg-type]
            data={
                "user_id": str(user_id),
                "previous_role": previous_role,
                "new_role": new_role.value,
            },
        )
        await session.commit()
        await session.refresh(user)
        return user

    async def delete_user(
        self,
        session: AsyncSession,
        user_id: object,
        actor_id: object,
    ) -> None:
        if str(user_id) == str(actor_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admins cannot delete their own account via the admin panel",
            )

        user = await session.get(User, user_id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        now = datetime.now(timezone.utc)
        # Audit BEFORE soft-delete so FK is still resolvable.
        await self._audit.create_entry(
            session,
            "ADMIN_USER_DELETED",
            actor_id=actor_id,  # type: ignore[arg-type]
            data={"user_id": str(user_id), "email": user.email},
        )

        ts = int(now.timestamp())
        user.is_deleted = True
        user.deleted_at = now
        user.email = f"deleted_{user.id}_{ts}@deleted.local"
        user.full_name = None
        user.confirmation_token = None
        await session.flush()
        await session.commit()

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    async def get_stats(self, session: AsyncSession) -> StatsResponse:
        raw = await self._stats_repo.get_stats(session)
        return StatsResponse(
            total_users=raw["total_users"],
            total_votings=raw["total_votings"],
            votes_cast=raw["votes_cast"],
            active_votings=raw["active_votings"],
            new_users_this_month=raw["new_users_this_month"],
            avg_participation_pct=raw["avg_participation_pct"],
            votings_per_day=raw["votings_per_day"],
            votes_per_day=raw["votes_per_day"],
            users_by_role=raw["users_by_role"],
            top_votings=raw["top_votings"],
            blockchain_total=raw["blockchain_total"],
            blockchain_confirmed=raw["blockchain_confirmed"],
            blockchain_failed=raw["blockchain_failed"],
            blockchain_published=raw["blockchain_published"],
            blockchain_finalized=raw["blockchain_finalized"],
            emails_total=raw["emails_total"],
            emails_sent=raw["emails_sent"],
            emails_failed=raw["emails_failed"],
        )

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    async def get_settings(self, session: AsyncSession) -> SettingsResponse:
        raw = await self._settings_repo.get_all(session)
        return _parse_settings(raw)

    async def update_settings(
        self,
        session: AsyncSession,
        payload: SettingsUpdateRequest,
        actor_id: object,
    ) -> SettingsResponse:
        updates: dict[str, str] = {}
        if payload.max_free_votings_per_month is not None:
            updates["max_free_votings_per_month"] = str(payload.max_free_votings_per_month)
        if payload.maintenance_mode is not None:
            updates["maintenance_mode"] = str(payload.maintenance_mode).lower()
        if payload.require_email_verification is not None:
            updates["require_email_verification"] = str(payload.require_email_verification).lower()
        if payload.session_timeout_minutes is not None:
            updates["session_timeout_minutes"] = str(payload.session_timeout_minutes)

        if updates:
            await self._settings_repo.bulk_upsert(session, updates)
            await self._audit.create_entry(
                session,
                "ADMIN_SETTINGS_UPDATED",
                actor_id=actor_id,  # type: ignore[arg-type]
                data={"updated_keys": list(updates.keys())},
            )
            await session.commit()

        raw = await self._settings_repo.get_all(session)
        return _parse_settings(raw)

    # ------------------------------------------------------------------
    # Backup
    # ------------------------------------------------------------------

    async def create_backup(
        self,
        session: AsyncSession,
        actor_id: object,
    ) -> dict:
        _BACKUP_DIR.mkdir(parents=True, exist_ok=True)

        users_rows = (await session.execute(select(User))).scalars().all()
        votings_rows = (await session.execute(select(Voting))).scalars().all()

        def _serialize_user(u: User) -> dict:
            return {
                "id": str(u.id),
                "email": u.email,
                "full_name": u.full_name,
                "role": u.role.value,
                "is_confirmed": u.is_confirmed,
                "is_deleted": u.is_deleted,
                "created_at": u.created_at.isoformat() if u.created_at else None,
                # hashed_password intentionally omitted
            }

        def _serialize_voting(v: Voting) -> dict:
            return {
                "id": str(v.id),
                "title": v.title,
                "description": v.description,
                "status": v.status.value,
                "access_type": v.access_type.value,
                "is_anonymous": v.is_anonymous,
                "start_date_time": v.start_date_time.isoformat() if v.start_date_time else None,
                "end_date_time": v.end_date_time.isoformat() if v.end_date_time else None,
                "created_by": str(v.created_by),
                "created_at": v.created_at.isoformat() if v.created_at else None,
                "is_deleted": v.is_deleted,
                "publish_tx_hash": v.publish_tx_hash,
                "finalize_tx_hash": v.finalize_tx_hash,
            }

        now = datetime.now(timezone.utc)
        timestamp = now.strftime("%Y%m%d_%H%M%S")
        filename = f"backup_{timestamp}.json"
        filepath = _BACKUP_DIR / filename

        payload_data = {
            "created_at": now.isoformat(),
            "users": [_serialize_user(u) for u in users_rows],
            "votings": [_serialize_voting(v) for v in votings_rows],
        }

        filepath.write_text(
            json.dumps(payload_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        await self._audit.create_entry(
            session,
            "ADMIN_BACKUP_CREATED",
            actor_id=actor_id,  # type: ignore[arg-type]
            data={"filename": filename},
        )
        await session.commit()

        return {"filename": filename, "created_at": now.isoformat()}

    def get_latest_backup(self) -> Optional[Path]:
        if not _BACKUP_DIR.exists():
            return None
        backups = sorted(_BACKUP_DIR.glob("backup_*.json"))
        return backups[-1] if backups else None

    def get_latest_backup_info(self) -> dict | None:
        """Returns {filename, created_at} for the latest backup, or None."""
        path = self.get_latest_backup()
        if path is None:
            return None
        import os
        ts = os.path.getmtime(path)
        created_at = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
        return {"filename": path.name, "created_at": created_at}

    # ------------------------------------------------------------------
    # Restore
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_dt(value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        return datetime.fromisoformat(value)

    async def restore_backup(
        self,
        session: AsyncSession,
        raw_bytes: bytes,
        actor_id: object,
    ) -> RestoreResponse:
        """
        Import users (without passwords) and votings from a backup JSON.

        Idempotent: existing users (by id or email) and existing votings (by id) are skipped.
        Restored users receive an unusable placeholder password and must use the password-reset
        flow to recover. Votes, ballots, voter lists, blockchain records and audit logs are not
        imported by design.
        """
        try:
            data = json.loads(raw_bytes.decode("utf-8"))
            users_in = data.get("users", [])
            votings_in = data.get("votings", [])
            if not isinstance(users_in, list) or not isinstance(votings_in, list):
                raise ValueError("users/votings must be lists")
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError, AttributeError) as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid backup file",
            ) from exc

        users_imported = 0
        users_skipped = 0
        votings_imported = 0
        votings_skipped = 0

        try:
            # Track which user ids exist (pre-existing or just-imported) for FK resolution.
            known_user_ids: set[str] = set()

            for u in users_in:
                user_id = u.get("id")
                email = (u.get("email") or "").strip().lower()
                if not user_id or not email:
                    users_skipped += 1
                    continue

                existing_by_id = await session.get(User, uuid.UUID(str(user_id)))
                existing_by_email = await self._users.get_by_email(session, email)
                if existing_by_id is not None or existing_by_email is not None:
                    known_user_ids.add(str(user_id))
                    users_skipped += 1
                    continue

                # Unusable placeholder password — user must reset to log in.
                placeholder = hash_password(secrets.token_urlsafe(32))
                user = User(
                    id=uuid.UUID(str(user_id)),
                    email=email,
                    full_name=u.get("full_name"),
                    hashed_password=placeholder,
                    role=Role(u.get("role", Role.voter.value)),
                    is_confirmed=bool(u.get("is_confirmed", False)),
                    is_deleted=bool(u.get("is_deleted", False)),
                    confirmation_token=secrets.token_urlsafe(32),
                )
                session.add(user)
                await session.flush()
                known_user_ids.add(str(user_id))
                users_imported += 1

            for v in votings_in:
                voting_id = v.get("id")
                created_by = v.get("created_by")
                if not voting_id or not created_by:
                    votings_skipped += 1
                    continue

                existing = await session.get(Voting, uuid.UUID(str(voting_id)))
                if existing is not None:
                    votings_skipped += 1
                    continue

                # FK created_by -> users.id (RESTRICT): skip if the owner is unknown.
                if str(created_by) not in known_user_ids:
                    if await session.get(User, uuid.UUID(str(created_by))) is None:
                        logger.warning(
                            "restore: skipping voting %s — unknown created_by %s",
                            voting_id,
                            created_by,
                        )
                        votings_skipped += 1
                        continue
                    known_user_ids.add(str(created_by))

                start_dt = self._parse_dt(v.get("start_date_time"))
                end_dt = self._parse_dt(v.get("end_date_time"))
                # CheckConstraint ck_votings_end_after_start.
                if start_dt is None or end_dt is None or end_dt <= start_dt:
                    votings_skipped += 1
                    continue

                voting = Voting(
                    id=uuid.UUID(str(voting_id)),
                    title=v.get("title"),
                    description=v.get("description"),
                    access_type=VotingAccessType(v.get("access_type")),
                    is_anonymous=bool(v.get("is_anonymous", False)),
                    start_date_time=start_dt,
                    end_date_time=end_dt,
                    status=VotingStatus(v.get("status", VotingStatus.draft.value)),
                    created_by=uuid.UUID(str(created_by)),
                    is_deleted=bool(v.get("is_deleted", False)),
                    publish_tx_hash=v.get("publish_tx_hash"),
                    finalize_tx_hash=v.get("finalize_tx_hash"),
                )
                session.add(voting)
                await session.flush()
                votings_imported += 1

            await self._audit.create_entry(
                session,
                "ADMIN_RESTORE_PERFORMED",
                actor_id=actor_id,  # type: ignore[arg-type]
                data={
                    "users_imported": users_imported,
                    "users_skipped": users_skipped,
                    "votings_imported": votings_imported,
                    "votings_skipped": votings_skipped,
                },
            )
            await session.commit()
        except HTTPException:
            await session.rollback()
            raise
        except Exception as exc:
            await session.rollback()
            logger.error("restore_backup failed: %s", exc, exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to restore backup",
            ) from exc

        return RestoreResponse(
            users_imported=users_imported,
            users_skipped=users_skipped,
            votings_imported=votings_imported,
            votings_skipped=votings_skipped,
        )

    # ------------------------------------------------------------------
    # Elections
    # ------------------------------------------------------------------

    async def list_elections(
        self,
        session: AsyncSession,
        page: int,
        page_size: int,
        status: Optional[str] = None,
        search: Optional[str] = None,
    ) -> tuple[list, int]:
        from app.models.voting import Voting
        from app.models.user import User
        from sqlalchemy import select, func
        from app.core.enums import VotingStatus

        offset = (page - 1) * page_size

        q = (
            select(Voting, User.full_name, User.email)
            .join(User, User.id == Voting.created_by, isouter=True)
            .where(Voting.is_deleted == False)
        )
        if status:
            try:
                q = q.where(Voting.status == VotingStatus(status))
            except ValueError:
                pass
        if search:
            q = q.where(Voting.title.ilike(f"%{search}%"))

        count_q = select(func.count()).select_from(q.subquery())
        total = (await session.execute(count_q)).scalar_one()

        rows = (await session.execute(q.order_by(Voting.created_at.desc()).offset(offset).limit(page_size))).all()

        items = []
        for voting, org_name, org_email in rows:
            items.append({
                "id": voting.id,
                "title": voting.title,
                "status": voting.status.value,
                "organizer_name": org_name,
                "organizer_email": org_email,
                "start_date_time": voting.start_date_time,
                "end_date_time": voting.end_date_time,
                "created_by": voting.created_by,
            })
        return items, total

    async def force_delete_voting(
        self,
        session: AsyncSession,
        voting_id: object,
        actor_id: object,
    ) -> None:
        from app.repositories.voting_repository import VotingRepository

        voting = await VotingRepository().get_by_id(session, voting_id)  # type: ignore[arg-type]
        if voting is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Election not found",
            )

        # Audit BEFORE soft-delete so FK is still resolvable.
        await self._audit.create_entry(
            session,
            "ELECTION_DELETED",
            actor_id=actor_id,  # type: ignore[arg-type]
            data={
                "voting_id": str(voting_id),
                "title": voting.title,
                "forced_by_admin": True,
            },
        )
        voting.is_deleted = True
        voting.deleted_at = datetime.now(timezone.utc)
        await session.commit()
