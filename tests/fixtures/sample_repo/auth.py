"""Authentication helpers for a tiny service."""
from dataclasses import dataclass

@dataclass
class User:
    username: str
    active: bool

def get_user(username: str) -> User | None:
    """Look up a user by username."""
    if username == "ada":
        return User(username="ada", active=True)
    return None

def authenticate_user(username: str) -> User | None:
    """Only active known users pass authentication."""
    user = get_user(username)
    if user is None or not user.active:
        return None
    return user

def require_active_user(username: str) -> User:
    user = authenticate_user(username)
    if user is None:
        raise PermissionError("inactive or unknown user")
    return user
