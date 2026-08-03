"""Bridge legacy staff → tenant gbconstruction."""
from legacy_tenant import (
    GB_TENANT_ID,
    GB_TENANT_SLUG,
    claims_for_user,
    map_legacy_user,
)


def test_map_admin_to_owner_uuid():
    u = map_legacy_user(
        {"email": "admin@gbconstruction.it", "role": "admin", "auth_provider": "legacy"}
    )
    assert u["supabase_user_id"] == "f1000000-0000-4000-8000-000000000001"
    assert u["app_tenants"][0]["t"] == GB_TENANT_ID
    assert u["app_tenants"][0]["r"] == "owner"
    assert u["app_tenants"][0]["slug"] == GB_TENANT_SLUG


def test_claims_have_sub():
    claims = claims_for_user({"email": "staff@gbconstruction.it", "role": "staff"})
    assert claims["sub"] == "f1000000-0000-4000-8000-000000000002"
    assert claims["role"] == "authenticated"
