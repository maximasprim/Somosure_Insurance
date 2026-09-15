"""Shared slowapi Limiter instance. Lives here (not in main.py) so route
modules can import and use @limiter.limit(...) directly without importing
main.py, which would create a circular import (main.py imports the route
routers).
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])
