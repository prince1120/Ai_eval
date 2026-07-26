from slowapi import Limiter
from slowapi.util import get_remote_address

# Defined in its own module (rather than in main.py) so route files can
# import it for @limiter.limit(...) decorators without a circular import.
limiter = Limiter(key_func=get_remote_address)
