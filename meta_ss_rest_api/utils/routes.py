# -*- coding: utf-8 -*-


def get_pagination(payload):
    """Return (limit, offset, page, page_size) from API payload."""
    try:
        page = int(payload.get("page", 1))
    except (TypeError, ValueError):
        page = 1
    try:
        page_size = int(payload.get("page_size", 20))
    except (TypeError, ValueError):
        page_size = 20

    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    limit = page_size
    offset = (page - 1) * page_size
    return limit, offset, page, page_size


def parse_active_filter(payload):
    """Return a boolean active filter value from common API payload formats."""
    active = payload.get("active", True)
    if isinstance(active, bool):
        return active
    if isinstance(active, str):
        return active.strip().lower() not in ("0", "false", "no")
    return bool(active)
