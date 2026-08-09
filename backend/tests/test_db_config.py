import db


DB_ENV_KEYS = (
    "CONNECTION_STRING_SUPABASE",
    "CONNECT_STRINGSUPABASE",
    "SUPABASE_DB_URL",
    "DATABASE_URL",
)


def _clear_db_env(monkeypatch):
    for key in DB_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def test_resolve_db_url_supports_connect_stringsupabase(monkeypatch):
    _clear_db_env(monkeypatch)
    monkeypatch.setenv("CONNECT_STRINGSUPABASE", '"postgresql://example.invalid/db"')

    assert db.resolve_db_url() == "postgresql://example.invalid/db"


def test_resolve_db_url_keeps_standard_name_priority(monkeypatch):
    _clear_db_env(monkeypatch)
    monkeypatch.setenv("CONNECTION_STRING_SUPABASE", "postgresql://standard.invalid/db")
    monkeypatch.setenv("CONNECT_STRINGSUPABASE", "postgresql://compat.invalid/db")

    assert db.resolve_db_url() == "postgresql://standard.invalid/db"


def test_resolve_db_url_prefers_explicit_supabase_url_to_compat_alias(monkeypatch):
    _clear_db_env(monkeypatch)
    monkeypatch.setenv("SUPABASE_DB_URL", "postgresql://supabase.invalid/db")
    monkeypatch.setenv("CONNECT_STRINGSUPABASE", "postgresql://compat.invalid/db")

    assert db.resolve_db_url() == "postgresql://supabase.invalid/db"
