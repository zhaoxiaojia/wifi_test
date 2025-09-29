import json
import functools
import inspect
from collections.abc import Mapping, Sequence
import pytest


_ACTUAL_PARAMS_ATTR = "_pyqt_actual_fixture_params"


def _ensure_actual_params(node):
    actual_params = getattr(node, _ACTUAL_PARAMS_ATTR, None)
    if actual_params is None:
        actual_params = {}
        setattr(node, _ACTUAL_PARAMS_ATTR, actual_params)
    return actual_params


def _store_actual_params(request, fixture_name, params):
    if request is None:
        return
    node = getattr(request, "node", None)
    if node is None:
        return
    actual_params = _ensure_actual_params(node)
    actual_params[fixture_name] = params
    try:
        node.user_properties.append((f"{fixture_name}.params", params))
    except Exception:
        # user_properties 可能不存在或不可写，忽略
        pass


def _should_skip_log_value(value):
    if value is None:
        return True
    if isinstance(value, str):
        normalized = value.strip()
        if not normalized:
            return True
        if normalized.lower() in {'none', 'null', 'default'}:
            return True
    return False


def _format_fixture_param_for_log(params):
    placeholder = '--'

    if hasattr(params, '_asdict'):
        items = []
        for key, value in params._asdict().items():
            if _should_skip_log_value(value):
                continue
            items.append(f'{key}={value}')
        if items:
            return ', '.join(items)
        return placeholder

    if isinstance(params, Mapping) and not isinstance(params, (str, bytes, bytearray)):
        items = []
        for key, value in params.items():
            if _should_skip_log_value(value):
                continue
            items.append(f'{key}={value}')
        if items:
            return ', '.join(items)
        return placeholder

    if isinstance(params, Sequence) and not isinstance(params, (str, bytes, bytearray)):
        items = [str(value) for value in params if not _should_skip_log_value(value)]
        if items:
            return ', '.join(items)
        return placeholder

    if _should_skip_log_value(params):
        return placeholder

    return str(params)


def get_fixture_actual_params(request, fixture_name, default):
    if request is None:
        return default
    node = getattr(request, "node", None)
    if node is None:
        return default
    actual_params = getattr(node, _ACTUAL_PARAMS_ATTR, None)
    if not actual_params:
        return default
    return actual_params.get(fixture_name, default)


def update_fixture_params(request, params, *, tag="FIX", name=None, log=True):
    """更新 fixture 的实际参数，并可选地重新输出 PyQt 日志。"""

    if request is None:
        return
    fixture_name = name or getattr(request, "fixturename", None)
    if fixture_name is None:
        fixture_name = "<UNKNOWN_FIXTURE>"

    _store_actual_params(request, fixture_name, params)

    formatted_params = _format_fixture_param_for_log(params)

    if log:
        pyqt_log(tag, fixture_name, formatted_params)


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
            fixture_name = name or getattr(request, "fixturename", func.__name__)

            try:
                raw_param = getattr(request, "param", "<NO_PARAM>")
            except Exception:
                raw_param = "<PARAM_ERROR>"

            params_to_log = get_fixture_actual_params(request, fixture_name, raw_param)
            formatted_params = _format_fixture_param_for_log(params_to_log)
            pyqt_log(tag, fixture_name, formatted_params)

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
