"""Criterion: PATCH /api/agents/{key} swaps provider/model/brain in real time."""


def test_patch_agent_updates_provider_model_and_reflects_in_list(client):
    # Use a seeded agent key (jarvis) and revert to its original provider/model afterwards.
    before = client.get("/agents")
    assert before.status_code == 200
    jarvis_before = next(a for a in before.json() if a["key"] == "jarvis")
    original = {"provider": jarvis_before["provider"], "model": jarvis_before["model"], "brain": jarvis_before["brain"]}

    try:
        patch = client.patch(
            "/agents/jarvis",
            json={"provider": "anthropic", "model": "claude-sonnet-5-5", "brain": "tscheck-brain-label"},
        )
        assert patch.status_code == 200, patch.text
        body = patch.json()
        assert body["provider"] == "anthropic"
        assert body["model"] == "claude-sonnet-5-5"
        assert body["brain"] == "tscheck-brain-label"

        listing = client.get("/agents")
        assert listing.status_code == 200
        jarvis_after = next(a for a in listing.json() if a["key"] == "jarvis")
        assert jarvis_after["provider"] == "anthropic"
        assert jarvis_after["model"] == "claude-sonnet-5-5"
        assert jarvis_after["brain"] == "tscheck-brain-label"
    finally:
        # Restore the seeded agent's original configuration so other tests/checks are unaffected.
        client.patch("/agents/jarvis", json=original)


def test_patch_agent_missing_key_returns_404(client):
    resp = client.patch(
        "/agents/tscheck-nonexistent-agent",
        json={"provider": "openai", "model": "gpt-5.4"},
    )
    assert resp.status_code == 404, resp.text


def test_patch_agent_invalid_provider_returns_422(client):
    resp = client.patch(
        "/agents/jarvis",
        json={"provider": "not-a-real-provider", "model": "gpt-5.4"},
    )
    assert resp.status_code == 422, resp.text
