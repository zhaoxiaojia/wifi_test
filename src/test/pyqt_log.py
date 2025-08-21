import json


def pyqt_log(tag: str, fixture: str, params):
    def default(o):
        try:
            return str(o)
        except Exception:
            return repr(o)
    payload = json.dumps({"fixture": fixture, "params": params}, default=default, ensure_ascii=False)
    print(f"[PYQT_{tag}]{payload}", flush=True)
