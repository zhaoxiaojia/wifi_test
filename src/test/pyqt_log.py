import json
import functools
import pytest


def pyqt_log(tag: str, fixture: str, params):
    def default(o):
        try:
            return str(o)
        except Exception:
            return repr(o)
    payload = json.dumps({"fixture": fixture, "params": params}, default=default, ensure_ascii=False)
    print(f"[PYQT_{tag}]{payload}", flush=True)


def log_fixture_params(tag="FIX", name=None):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            request = kwargs.get("request") or args[0]
            pyqt_log(tag, name or func.__name__, str(request.param))
            return func(*args, **kwargs)

        return wrapper

    return decorator
