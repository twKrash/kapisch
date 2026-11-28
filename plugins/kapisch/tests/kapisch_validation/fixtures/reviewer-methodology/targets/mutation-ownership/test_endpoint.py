def test_owner_deletes_own_event(client, seeded_event):
    response = client.delete(f"/events/{seeded_event.event_id}")
    assert response.status_code == 204
    assert not seeded_event.exists()
