import json
import functools
import inspect
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
            # ——拿 request（尽量简单，不花哨）——
            request = kwargs.get("request")
            if request is None and args:
                # 大多数 fixture 的第一个参数就是 request
                candidate = args[0]
                if hasattr(candidate, "param"):
                    request = candidate

            # ——记录日志（容错即可）——
            try:
                param_str = str(getattr(request, "param", "<NO_PARAM>"))
            except Exception:
                param_str = "<PARAM_ERROR>"
            pyqt_log(tag, name or func.__name__, param_str)

            # ——调用原函数，并保持其生成器/返回值语义——
            result = func(*args, **kwargs)

            # 情况 A：yield-style fixture（生成器）
            if inspect.isgenerator(result):
                # 直接把产物与 teardown 交还给 pytest
                yield from result
                return

            # 情况 B：return-style fixture
            yield result

        return wrapper
    return decorator
