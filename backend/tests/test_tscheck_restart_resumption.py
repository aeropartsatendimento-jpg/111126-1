"""Criterion P1.7: a mission caught mid-flight by a backend restart resumes to completion
without duplicating its mission, delegation message, or delivery/summary messages."""

import os
import subprocess
import time

import httpx

API_URL = f"{os.environ.get('BACKEND_URL', 'http://localhost:8001')}/api"


def _wait_for_status(client: httpx.Client, mission_id: str, statuses: set[str], timeout: float) -> dict:
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        resp = client.get("/missions")
        assert resp.status_code == 200
        for m in resp.json():
            if m["id"] == mission_id:
                last = m
                if m["status"] in statuses:
                    return m
        time.sleep(0.5)
    raise AssertionError(f"mission {mission_id} never reached {statuses}, last seen: {last}")


def test_mission_survives_backend_restart_without_duplicating(client):
    text = f"tscheck-restart-mission-{int(time.time())}"
    created = client.post("/missions", json={"text": text})
    assert created.status_code == 200, created.text
    mission_id = created.json()["id"]

    # Wait for the mission to reach "delegating" (plan done, tasks about to execute).
    mid_flight = _wait_for_status(client, mission_id, {"delegating", "completed"}, timeout=20)
    assert mid_flight["status"] in {"delegating", "completed"}

    # Restart the backend process mid-flight.
    subprocess.run(["sudo", "supervisorctl", "restart", "backend"], check=True, timeout=60)

    # Give the backend time to come back up and the recovery routine to resume the mission.
    deadline = time.time() + 30
    with httpx.Client(base_url=API_URL, timeout=10.0) as probe:
        while time.time() < deadline:
            try:
                if probe.get("/system").status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(1)

    with httpx.Client(base_url=API_URL, timeout=30.0) as fresh_client:
        final = _wait_for_status(fresh_client, mission_id, {"completed", "failed"}, timeout=30)
        assert final["status"] == "completed", final

        # No duplicate mission with this exact text.
        all_missions = fresh_client.get("/missions").json()
        matches = [m for m in all_missions if m["text"] == text]
        assert len(matches) == 1, f"expected exactly 1 mission with text={text!r}, got {len(matches)}"

        # No duplicate delegation/delivery/summary room messages for this mission.
        room = fresh_client.get("/room/messages").json()
        related = [m for m in room if m.get("mission_id") == mission_id]
        ids = [m["id"] for m in related]
        assert len(ids) == len(set(ids)), f"duplicate room message ids for mission {mission_id}: {ids}"
        delegation_msgs = [m for m in related if m["id"] == f"mission-delegation-{mission_id}"]
        assert len(delegation_msgs) == 1
