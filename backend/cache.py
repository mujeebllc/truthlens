import hashlib

# In-memory dictionary cache representing a Redis key-value store.
#
# Redis Upgrade Path:
# To replace this with Redis, you can swap this module's functions with a redis-py client instance:
#
# import redis
# _client = redis.Redis(host='localhost', port=6379, db=0)
#
# def get(key: str) -> str | None:
#     val = _client.get(key)
#     return val.decode('utf-8') if val else None
#
# def set(key: str, value: str) -> None:
#     _client.set(key, value)

_cache = {}

def get_cache_key(text: str) -> str:
    """Normalize and hash the claim text to produce a consistent cache key."""
    # Normalize: lowercase, strip punctuation, and strip whitespace
    normalized = "".join(char for char in text.lower() if char.isalnum() or char.isspace()).strip()
    # Return MD5 hash as a key
    return hashlib.md5(normalized.encode("utf-8")).hexdigest()

def get(key: str) -> str | None:
    """Retrieve string value from cache by key. Returns None if key is missing."""
    return _cache.get(key)

def set(key: str, value: str) -> None:
    """Store string value in cache under the given key."""
    _cache[key] = value
