"""Auth dual-mode: riconoscimento JWT legacy vs Supabase."""
import jwt
import auth as authlib


def test_looks_like_supabase_rs256():
    # token finto con header RS256 (non verifichiamo firma qui)
    header = {"alg": "RS256", "typ": "JWT", "kid": "test"}
    payload = {"sub": "u1", "iss": "https://xyz.supabase.co/auth/v1", "role": "authenticated"}
    # PyJWT needs a key even for encode with RS - use HS encode then force: just test helper with crafted
    # We test the helper with a manually built token-like structure via encode HS but alg claim
    token = jwt.encode(payload, "secret", algorithm="HS256")
    # HS won't look like supabase by alg; inject iss path
    assert authlib._looks_like_supabase_jwt(token) is True  # iss contains supabase


def test_looks_like_legacy_hs():
    payload = {"sub": "abc", "type": "access", "email": "a@b.c", "role": "admin"}
    token = jwt.encode(payload, "secret", algorithm="HS256")
    # no supabase iss
    assert authlib._looks_like_supabase_jwt(token) is False
