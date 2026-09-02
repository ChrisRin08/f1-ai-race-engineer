def test_health_returns_ok(client) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_is_deterministic_and_fastf1_independent(client) -> None:
    responses = [client.get("/health") for _ in range(3)]

    assert [response.status_code for response in responses] == [200, 200, 200]
    assert [response.json() for response in responses] == [
        {"status": "ok"},
        {"status": "ok"},
        {"status": "ok"},
    ]
