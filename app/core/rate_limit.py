from slowapi import Limiter
from slowapi.util import get_remote_address

# Per-IP keying is sufficient for this small internal app. In-memory storage
# (slowapi's default) is fine for now — counts reset per worker process and
# aren't shared across replicas, but that's an acceptable tradeoff until this
# actually needs to scale beyond a single process.
limiter = Limiter(key_func=get_remote_address)
