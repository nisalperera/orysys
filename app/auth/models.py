"""Roles, users and the data-access tier each role may read (tool permissions come in T4)."""
from dataclasses import dataclass
from enum import Enum


class Role(str, Enum):
    VIEWER = "viewer"
    ANALYST = "analyst"
    ADMIN = "admin"


ROLE_ACCESS_LEVELS: dict[Role, tuple[str, ...]] = {
    Role.VIEWER: ("public", "internal"),
    Role.ANALYST: ("public", "internal", "confidential"),
    Role.ADMIN: ("public", "internal", "confidential", "restricted"),
}


@dataclass(frozen=True)
class User:
    user_id: str
    name: str
    role: Role
    department: str

    @property
    def access_levels(self) -> tuple[str, ...]:
        return ROLE_ACCESS_LEVELS[self.role]


USERS: dict[str, User] = {
    "viewer1": User("viewer1", "Vihanga (Viewer)", Role.VIEWER, "retail"),
    "analyst1": User("analyst1", "Amaya (Analyst)", Role.ANALYST, "payments"),
    "admin1": User("admin1", "Asanka (Admin)", Role.ADMIN, "platform"),
}
