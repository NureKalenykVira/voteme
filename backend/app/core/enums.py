from enum import Enum


class Role(str, Enum):
    global_admin = "global_admin"
    organizer = "organizer"
    voter = "voter"
    auditor = "auditor"
