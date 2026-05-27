from enum import Enum


class Role(str, Enum):
    global_admin = "global_admin"
    organizer = "organizer"
    voter = "voter"
    auditor = "auditor"


class VotingStatus(str, Enum):
    draft = "draft"
    published = "published"
    active = "active"
    finished = "finished"
    archived = "archived"


class VotingAccessType(str, Enum):
    public = "public"
    private = "private"


class VotingEvent(str, Enum):
    publish = "publish"
    start_tick = "start_tick"
    end_tick = "end_tick"
    archive = "archive"


class BlockchainRecordStatus(str, Enum):
    pending = "pending"
    confirmed = "confirmed"
    failed = "failed"
