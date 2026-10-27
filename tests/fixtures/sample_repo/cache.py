"""Small in-memory cache. It does not use Redis."""
CACHE: dict[str, str] = {}

def cache_result(key: str, value: str) -> None:
    CACHE[key] = value

def get_cached_result(key: str) -> str | None:
    return CACHE.get(key)
