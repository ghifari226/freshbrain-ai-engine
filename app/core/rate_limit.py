from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import get_settings

# Per-IP keying is sufficient for this small internal app; Redis here is only
# used for rate-limit storage for now — other uses can land later as needed.
limiter = Limiter(key_func=get_remote_address, storage_uri=get_settings().rate_limit_storage_uri)
