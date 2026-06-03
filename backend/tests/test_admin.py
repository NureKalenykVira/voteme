import json
import uuid
from datetime import datetime, timedelta, timezone
from io import BytesIO

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import Role, VotingStatus
from app.core.security import create_access_token, hash_password
from app.models.user import User
from app.models.voting import Voting


pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _make_user(
    db_session: AsyncSession,
    email: str,
    role: Role = Role.global_admin,
) -> User:
    user = User(
        email=email.lower(),
        hashed_password=hash_password("Password123"),
        full_name="Admin User",
        role=role,
        is_confirmed=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


def _auth(user: User) -> dict[str, str]:
    token = create_access_token(sub=str(user.id), role=user.role)
    return {"Authorization": f"Bearer {token}"}


async def _make_voting(
    db_session: AsyncSession,
    owner: User,
    *,
    status: VotingStatus = VotingStatus.draft,
) -> Voting:
    from app.core.enums import VotingAccessType

    start = datetime.now(timezone.utc) + timedelta(hours=1)
    end = start + timedelta(hours=2)
    voting = Voting(
        title="Admin Election",
        description="d",
        access_type=VotingAccessType.public,
        is_anonymous=False,
        start_date_time=start,
        end_date_time=end,
        status=status,
        created_by=owner.id,
        invitation_code=uuid.uuid4().hex,
    )
    db_session.add(voting)
    await db_session.commit()
    await db_session.refresh(voting)
    return voting


class TestListUsers:
    async def test_admin_lists_users(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        admin = await _make_user(db_session, "adm_list_admin@example.com")
        await _make_user(db_session, "adm_list_u1@example.com", Role.voter)
        response = await client.get("/admin/users", headers=_auth(admin))
        assert response.status_code == 200
        body = response.json()
        assert body["total"] >= 2
        assert "items" in body

    async def test_non_admin_forbidden(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        organizer = await _make_user(
            db_session, "adm_list_org@example.com", Role.organizer
        )
        response = await client.get("/admin/users", headers=_auth(organizer))
        assert response.status_code == 403

    async def test_without_token_returns_401(self, client: AsyncClient):
        response = await client.get("/admin/users")
        assert response.status_code == 401

    async def test_role_filter(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        admin = await _make_user(db_session, "adm_filter_admin@example.com")
        await _make_user(db_session, "adm_filter_v@example.com", Role.voter)
        response = await client.get(
            "/admin/users?role=voter", headers=_auth(admin)
        )
        assert response.status_code == 200
        assert all(u["role"] == "voter" for u in response.json()["items"])


class TestCreateUser:
    async def test_create_user_returns_201(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        admin = await _make_user(db_session, "adm_create_admin@example.com")
        response = await client.post(
            "/admin/users",
            headers=_auth(admin),
            json={
                "full_name": "Created",
                "email": "adm_created1@example.com",
                "role": "organizer",
                "password": "Password123",
            },
        )
        assert response.status_code == 201
        body = response.json()
        assert body["email"] == "adm_created1@example.com"
        assert body["role"] == "organizer"
        assert body["is_confirmed"] is True

    async def test_create_duplicate_email_returns_409(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        admin = await _make_user(db_session, "adm_dup_admin@example.com")
        await _make_user(db_session, "adm_dup_existing@example.com", Role.voter)
        response = await client.post(
            "/admin/users",
            headers=_auth(admin),
            json={
                "email": "adm_dup_existing@example.com",
                "role": "voter",
                "password": "Password123",
            },
        )
        assert response.status_code == 409

    async def test_create_user_non_admin_forbidden(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        organizer = await _make_user(
            db_session, "adm_create_org@example.com", Role.organizer
        )
        response = await client.post(
            "/admin/users",
            headers=_auth(organizer),
            json={
                "email": "adm_x@example.com",
                "role": "voter",
                "password": "Password123",
            },
        )
        assert response.status_code == 403


class TestPatchUserRole:
    async def test_patch_role_returns_200(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        admin = await _make_user(db_session, "adm_patch_admin@example.com")
        target = await _make_user(db_session, "adm_patch_t@example.com", Role.voter)
        response = await client.patch(
            f"/admin/users/{target.id}",
            headers=_auth(admin),
            json={"role": "organizer"},
        )
        assert response.status_code == 200
        assert response.json()["role"] == "organizer"

    async def test_patch_unknown_user_returns_404(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        admin = await _make_user(db_session, "adm_patch_admin2@example.com")
        response = await client.patch(
            f"/admin/users/{uuid.uuid4()}",
            headers=_auth(admin),
            json={"role": "organizer"},
        )
        assert response.status_code == 404

    async def test_patch_role_non_admin_forbidden(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        organizer = await _make_user(
            db_session, "adm_patch_org@example.com", Role.organizer
        )
        target = await _make_user(db_session, "adm_patch_t2@example.com", Role.voter)
        response = await client.patch(
            f"/admin/users/{target.id}",
            headers=_auth(organizer),
            json={"role": "organizer"},
        )
        assert response.status_code == 403


class TestDeleteUser:
    async def test_delete_user_returns_204(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        admin = await _make_user(db_session, "adm_del_admin@example.com")
        target = await _make_user(db_session, "adm_del_t@example.com", Role.voter)
        target_id = target.id
        response = await client.delete(
            f"/admin/users/{target_id}", headers=_auth(admin)
        )
        assert response.status_code == 204

        db_session.expire_all()
        result = await db_session.execute(select(User).where(User.id == target_id))
        refreshed = result.scalar_one()
        assert refreshed.is_deleted is True

    async def test_delete_self_returns_403(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        admin = await _make_user(db_session, "adm_del_self@example.com")
        response = await client.delete(
            f"/admin/users/{admin.id}", headers=_auth(admin)
        )
        assert response.status_code == 403

    async def test_delete_unknown_user_returns_404(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        admin = await _make_user(db_session, "adm_del_admin2@example.com")
        response = await client.delete(
            f"/admin/users/{uuid.uuid4()}", headers=_auth(admin)
        )
        assert response.status_code == 404


class TestListElections:
    async def test_admin_lists_elections(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        admin = await _make_user(db_session, "adm_el_admin@example.com")
        owner = await _make_user(db_session, "adm_el_owner@example.com", Role.organizer)
        await _make_voting(db_session, owner)
        response = await client.get("/admin/elections", headers=_auth(admin))
        assert response.status_code == 200
        body = response.json()
        assert body["total"] >= 1
        assert "items" in body

    async def test_list_elections_non_admin_forbidden(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        organizer = await _make_user(
            db_session, "adm_el_org@example.com", Role.organizer
        )
        response = await client.get("/admin/elections", headers=_auth(organizer))
        assert response.status_code == 403


class TestForceDeleteElection:
    async def test_force_delete_returns_204(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        admin = await _make_user(db_session, "adm_fd_admin@example.com")
        owner = await _make_user(db_session, "adm_fd_owner@example.com", Role.organizer)
        voting = await _make_voting(
            db_session, owner, status=VotingStatus.active
        )
        voting_id = voting.id
        response = await client.delete(
            f"/admin/elections/{voting_id}", headers=_auth(admin)
        )
        assert response.status_code == 204

        db_session.expire_all()
        result = await db_session.execute(
            select(Voting).where(Voting.id == voting_id)
        )
        refreshed = result.scalar_one()
        assert refreshed.is_deleted is True

    async def test_force_delete_unknown_returns_404(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        admin = await _make_user(db_session, "adm_fd_admin2@example.com")
        response = await client.delete(
            f"/admin/elections/{uuid.uuid4()}", headers=_auth(admin)
        )
        assert response.status_code == 404

    async def test_force_delete_non_admin_forbidden(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        organizer = await _make_user(
            db_session, "adm_fd_org@example.com", Role.organizer
        )
        voting = await _make_voting(db_session, organizer)
        response = await client.delete(
            f"/admin/elections/{voting.id}", headers=_auth(organizer)
        )
        assert response.status_code == 403


class TestStats:
    async def test_stats_returns_200(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        admin = await _make_user(db_session, "adm_stats_admin@example.com")
        response = await client.get("/admin/stats", headers=_auth(admin))
        assert response.status_code == 200
        body = response.json()
        assert "total_users" in body
        assert "total_votings" in body
        assert "votes_cast" in body
        assert isinstance(body["users_by_role"], list)

    async def test_stats_non_admin_forbidden(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        voter = await _make_user(db_session, "adm_stats_v@example.com", Role.voter)
        response = await client.get("/admin/stats", headers=_auth(voter))
        assert response.status_code == 403


class TestSettings:
    async def test_get_settings_returns_defaults(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        admin = await _make_user(db_session, "adm_set_admin@example.com")
        response = await client.get("/admin/settings", headers=_auth(admin))
        assert response.status_code == 200
        body = response.json()
        assert body["max_free_votings_per_month"] == 12
        assert body["maintenance_mode"] is False
        assert body["require_email_verification"] is True

    async def test_update_settings_persists(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        admin = await _make_user(db_session, "adm_set_upd_admin@example.com")
        response = await client.post(
            "/admin/settings",
            headers=_auth(admin),
            json={"max_free_votings_per_month": 99},
        )
        assert response.status_code == 200
        assert response.json()["max_free_votings_per_month"] == 99

        follow = await client.get("/admin/settings", headers=_auth(admin))
        assert follow.json()["max_free_votings_per_month"] == 99

    async def test_settings_non_admin_forbidden(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        voter = await _make_user(db_session, "adm_set_v@example.com", Role.voter)
        response = await client.get("/admin/settings", headers=_auth(voter))
        assert response.status_code == 403


class TestBackup:
    async def test_create_backup_returns_filename(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        admin = await _make_user(db_session, "adm_bk_admin@example.com")
        response = await client.post("/admin/backup", headers=_auth(admin))
        assert response.status_code == 200
        body = response.json()
        assert "filename" in body
        assert body["filename"].startswith("backup_")
        assert "created_at" in body

    async def test_backup_non_admin_forbidden(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        voter = await _make_user(db_session, "adm_bk_v@example.com", Role.voter)
        response = await client.post("/admin/backup", headers=_auth(voter))
        assert response.status_code == 403

    async def test_backup_info_after_create(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        admin = await _make_user(db_session, "adm_bk_info_admin@example.com")
        await client.post("/admin/backup", headers=_auth(admin))
        response = await client.get("/admin/backup/info", headers=_auth(admin))
        assert response.status_code == 200
        body = response.json()
        assert body is not None
        assert "filename" in body

    async def test_backup_latest_downloads_json(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        admin = await _make_user(db_session, "adm_bk_dl_admin@example.com")
        await client.post("/admin/backup", headers=_auth(admin))
        response = await client.get("/admin/backup/latest", headers=_auth(admin))
        assert response.status_code == 200
        payload = json.loads(response.content)
        assert "users" in payload
        assert "votings" in payload

    async def test_backup_info_non_admin_forbidden(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        voter = await _make_user(db_session, "adm_bk_info_v@example.com", Role.voter)
        response = await client.get("/admin/backup/info", headers=_auth(voter))
        assert response.status_code == 403


class TestRestore:
    async def test_restore_imports_user_and_voting(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        admin = await _make_user(db_session, "adm_rs_admin@example.com")

        new_user_id = str(uuid.uuid4())
        new_voting_id = str(uuid.uuid4())
        start = datetime.now(timezone.utc) + timedelta(hours=1)
        end = start + timedelta(hours=2)
        backup = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "users": [
                {
                    "id": new_user_id,
                    "email": "restored_user@example.com",
                    "full_name": "Restored",
                    "role": "organizer",
                    "is_confirmed": True,
                    "is_deleted": False,
                }
            ],
            "votings": [
                {
                    "id": new_voting_id,
                    "title": "Restored Election",
                    "description": "d",
                    "status": "draft",
                    "access_type": "public",
                    "is_anonymous": False,
                    "start_date_time": start.isoformat(),
                    "end_date_time": end.isoformat(),
                    "created_by": new_user_id,
                    "is_deleted": False,
                }
            ],
        }
        raw = json.dumps(backup).encode("utf-8")
        response = await client.post(
            "/admin/restore",
            headers=_auth(admin),
            files={"file": ("backup.json", BytesIO(raw), "application/json")},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["users_imported"] == 1
        assert body["votings_imported"] == 1

    async def test_restore_skips_existing(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        admin = await _make_user(db_session, "adm_rs_skip_admin@example.com")
        existing = await _make_user(
            db_session, "adm_rs_existing@example.com", Role.voter
        )
        backup = {
            "users": [
                {
                    "id": str(existing.id),
                    "email": existing.email,
                    "full_name": "X",
                    "role": "voter",
                    "is_confirmed": True,
                    "is_deleted": False,
                }
            ],
            "votings": [],
        }
        raw = json.dumps(backup).encode("utf-8")
        response = await client.post(
            "/admin/restore",
            headers=_auth(admin),
            files={"file": ("backup.json", BytesIO(raw), "application/json")},
        )
        assert response.status_code == 200
        assert response.json()["users_skipped"] == 1

    async def test_restore_invalid_json_returns_400(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        admin = await _make_user(db_session, "adm_rs_bad_admin@example.com")
        response = await client.post(
            "/admin/restore",
            headers=_auth(admin),
            files={"file": ("backup.json", BytesIO(b"not json"), "application/json")},
        )
        assert response.status_code == 400

    async def test_restore_non_admin_forbidden(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        voter = await _make_user(db_session, "adm_rs_v@example.com", Role.voter)
        raw = json.dumps({"users": [], "votings": []}).encode("utf-8")
        response = await client.post(
            "/admin/restore",
            headers=_auth(voter),
            files={"file": ("backup.json", BytesIO(raw), "application/json")},
        )
        assert response.status_code == 403
