"""Identifiers shared by workflow audit records."""

import uuid


def trace_id():
    return f"trc_{uuid.uuid4().hex[:12]}"
