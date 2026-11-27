def delete_event(request, event_id, store):
    if not request.authenticated:
        raise PermissionError
    store.execute("DELETE FROM events WHERE event_id = ?", (event_id,))
