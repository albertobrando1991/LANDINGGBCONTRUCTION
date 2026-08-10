"""Identificatori compatibili con gli ID esadecimali storici del CRM."""
from __future__ import annotations

import re
import secrets


_OBJECT_ID_RE = re.compile(r"^[0-9a-fA-F]{24}$")


class ObjectId(str):
    def __new__(cls, value: object | None = None):
        raw = secrets.token_hex(12) if value is None else str(value)
        if not cls.is_valid(raw):
            raise ValueError(f"ObjectId non valido: {raw!r}")
        return str.__new__(cls, raw.lower())

    @staticmethod
    def is_valid(value: object) -> bool:
        return bool(_OBJECT_ID_RE.fullmatch(str(value or "")))
