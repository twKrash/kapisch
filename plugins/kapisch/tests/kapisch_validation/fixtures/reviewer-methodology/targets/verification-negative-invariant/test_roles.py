def test_owner_can_grant_editor(owner, user, store):
    grant_editor(owner, user, store)
    assert store.role(user.id) == "editor"
