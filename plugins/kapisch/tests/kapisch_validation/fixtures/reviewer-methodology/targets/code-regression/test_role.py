def test_admin_claim_remains_admin():
    assert role_for({"role": "admin"}) == "admin"
