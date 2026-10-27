from auth import require_active_user

def profile_endpoint(username: str) -> dict:
    """Return the profile for an active user."""
    user = require_active_user(username)
    return {"username": user.username}

def health_endpoint() -> dict:
    return {"status": "ok"}
