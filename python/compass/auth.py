# -*- coding: utf-8 -*-
"""Personal access tokens (PAT) and handles.

A PAT is an identity/accounting credential, not an AI credit. It is only used
to authorize writes to this service.
"""
from __future__ import annotations

import hashlib
import re
import secrets

HANDLE_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,30}[a-z0-9]$")


def new_token() -> str:
    return "cmp_pat_" + secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def valid_handle(handle: str) -> bool:
    return bool(HANDLE_RE.match(handle or ""))


def new_share_slug() -> str:
    return secrets.token_urlsafe(9).replace("_", "").replace("-", "")[:12]
