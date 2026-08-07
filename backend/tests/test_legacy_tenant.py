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


def test_info_accounts_map_to_supabase_admin_memberships():
    expected = {
        "info@gbconstruction.it": "3573af1c-1be2-4296-8c59-cb5bd2ed3eb3",
        "info@alantis.it": "cd543ef2-cbae-49fc-bd34-db5739be0fda",
    }
    for email, user_id in expected.items():
        mapped = map_legacy_user(
            {"id": "6a235c957b3c08a131d4277a", "email": email, "role": "admin"}
        )
        assert mapped["id"] == user_id
        assert mapped["supabase_user_id"] == user_id
        assert mapped["app_tenants"] == [
            {"t": GB_TENANT_ID, "r": "admin", "slug": GB_TENANT_SLUG}
        ]
