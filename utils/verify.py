import hmac
import hashlib
import json
from os import environ

PAYOS_CHECKSUM_KEY = environ.get("PAYOS_CHECKSUM_KEY")

def convert_obj_to_query_str(obj: dict) -> str:
    query_string = []

    for key, value in obj.items():
        if isinstance(value, (int, float, bool)):
            value_as_string = str(value)
        elif value in [None, "null", "NULL"]:
            value_as_string = ""
        else:
            value_as_string = str(value)
        query_string.append(f"{key}={value_as_string}")

    return "&".join(query_string)

def sort_obj_by_key(obj: dict) -> dict:
    return dict(sorted(obj.items()))

def is_valid_signature(data: dict, signature: str) -> bool:
    sorted_data = sort_obj_by_key(data)
    query_str = convert_obj_to_query_str(sorted_data)

    hmac_signature = hmac.new(
        PAYOS_CHECKSUM_KEY.encode("utf-8"),
        msg=query_str.encode("utf-8"),
        digestmod=hashlib.sha256
    ).hexdigest()

    return hmac_signature == signature
