import json

try:
    import orjson
except ImportError:
    orjson = None

try:
    import rapidjson
except ImportError:
    rapidjson = None


def try_json_decode(block: bytes | str):
    if orjson:
        try:
            return orjson.loads(block)
        except Exception:
            pass
    if rapidjson:
        try:
            return rapidjson.loads(
                block, parse_mode=rapidjson.PM_COMMENTS | rapidjson.PM_TRAILING_COMMAS
            )
        except Exception:
            pass
    if json:
        try:
            return json.loads(block)
        except Exception:
            pass
    return None


# def json_encode(block:Any):
