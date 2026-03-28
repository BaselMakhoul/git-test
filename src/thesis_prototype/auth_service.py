from __future__ import annotations

import hashlib
import hmac
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import uuid4

from .permissions import Role


@dataclass
class User:
    user_id: str
    username: str
    password_hash: str
    display_name: str
    role: Role
    active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class AuthService:
    def __init__(self) -> None:
        self._users_by_id: Dict[str, User] = {}
        self._users_by_username: Dict[str, str] = {}

    def create_user(self, username: str, password: str, display_name: str, role: Role, active: bool = True) -> User:
        normalized = username.strip().lower()
        if not normalized:
            raise ValueError("username is required")
        if normalized in self._users_by_username:
            raise ValueError("username already exists")
        if len(password) < 4:
            raise ValueError("password must be at least 4 characters for demo use")

        user = User(
            user_id=f"usr-{uuid4().hex[:10]}",
            username=normalized,
            password_hash=self.hash_password(password),
            display_name=display_name.strip() or normalized,
            role=role,
            active=active,
        )
        self._users_by_id[user.user_id] = user
        self._users_by_username[user.username] = user.user_id
        return user

    def list_users(self) -> List[User]:
        return list(self._users_by_id.values())

    def get_user_by_username(self, username: str) -> User:
        normalized = username.strip().lower()
        if normalized not in self._users_by_username:
            raise KeyError("user not found")
        return self._users_by_id[self._users_by_username[normalized]]

    def get_user_by_id(self, user_id: str) -> User:
        if user_id not in self._users_by_id:
            raise KeyError("user not found")
        return self._users_by_id[user_id]

    def set_user_active(self, user_id: str, active: bool) -> User:
        user = self.get_user_by_id(user_id)
        user.active = active
        return user

    def assign_role(self, user_id: str, role: Role) -> User:
        user = self.get_user_by_id(user_id)
        user.role = role
        return user

    def authenticate(self, username: str, password: str) -> User:
        user = self.get_user_by_username(username)
        if not user.active:
            raise PermissionError("user is inactive")
        if not self.verify_password(password, user.password_hash):
            raise PermissionError("invalid credentials")
        return user

    @staticmethod
    def hash_password(password: str) -> str:
        salt = os.urandom(16)
        iterations = 200_000
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        return f"pbkdf2_sha256${iterations}${salt.hex()}${digest.hex()}"

    @staticmethod
    def verify_password(password: str, encoded: str) -> bool:
        algo, iterations, salt_hex, digest_hex = encoded.split("$")
        if algo != "pbkdf2_sha256":
            return False
        candidate = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt_hex),
            int(iterations),
        ).hex()
        return hmac.compare_digest(candidate, digest_hex)
