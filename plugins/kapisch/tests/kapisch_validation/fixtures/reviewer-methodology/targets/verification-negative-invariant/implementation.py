def grant_editor(actor, user, store):
    store.update_role(user.id, "editor")
