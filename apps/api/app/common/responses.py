from typing import Any


def success(data: Any) -> dict:
    return {"success": True, "data": data}
