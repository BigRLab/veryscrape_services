import asyncio
from functools import wraps


def synchronous(f):
    """Wrapper function allowing unittest to run asynchronous test functions as if they were normal test functions"""
    @wraps(f)
    def wrapper(*args, **kwargs):
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(f(*args, **kwargs))
    return wrapper
