"""Locust workload for CallHub stress testing.

This is the canonical stress-test entrypoint.
It does three things:
- logs users in
- checks whether they are admins
- runs a mix of reads, updates, and denied unauthorized updates

At the end of the run, it writes a compact JSON summary to the benchmarks folder.
"""

from __future__ import annotations

import json
import os
import random
import threading
from pathlib import Path

from locust import HttpUser, between, events, task


TARGET_MEMBER_ID = int(os.getenv("TARGET_MEMBER_ID", "1"))
USERS_FILE = os.getenv("USERS_FILE", "test_users.json")
SUMMARY_FILE = os.getenv("STRESS_SUMMARY_FILE", "../benchmarks/locust_stress_summary.json")
UPDATE_EVERY = max(1, int(os.getenv("UPDATE_EVERY", "4")))
UNAUTH_UPDATE_EVERY = max(1, int(os.getenv("UNAUTH_UPDATE_EVERY", "10")))

_lock = threading.Lock()
_users_cache: list[dict] | None = None
_metrics = {
    "login_ok": 0,
    "login_fail": 0,
    "admin_read_ok": 0,
    "admin_read_fail": 0,
    "admin_update_ok": 0,
    "admin_update_fail": 0,
    "unauth_update_denied": 0,
    "unauth_update_other": 0,
    "infra_errors": 0,
    "updated_names": [],
}


def load_users() -> list[dict]:
    """Load and cache test users from the JSON file."""
    global _users_cache
    if _users_cache is not None:
        return _users_cache

    path = Path(USERS_FILE)
    users = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(users, list) or not users:
        raise ValueError("USERS_FILE must contain a non-empty JSON list")

    for user in users:
        if "username" not in user or "password" not in user:
            raise ValueError("Each user requires 'username' and 'password'")

    _users_cache = users
    return users


def safe_json(response):
    try:
        return response.json()
    except Exception:
        return {"raw": response.text[:200]}


class CallHubStressUser(HttpUser):
    """A single simulated user that performs the stress workload."""

    wait_time = between(0.15, 0.6)

    def on_start(self) -> None:
        self.username = None
        self.password = None
        self.member_id = None
        self.is_admin = False
        self.target_snapshot = None

        creds = random.choice(load_users())
        self.username = creds["username"]
        self.password = creds["password"]

        login_response = self.client.post(
            "/login",
            json={"username": self.username, "password": self.password},
            name="POST /login",
        )
        if login_response.status_code != 200:
            with _lock:
                _metrics["login_fail"] += 1
            return

        with _lock:
            _metrics["login_ok"] += 1

        login_data = safe_json(login_response)
        self.member_id = login_data.get("member_id")

        admin_response = self.client.get("/check-admin", name="GET /check-admin")
        if admin_response.status_code == 200:
            self.is_admin = bool(safe_json(admin_response).get("is_admin"))

        if self.is_admin:
            snapshot = self.client.get(
                f"/members/{TARGET_MEMBER_ID}",
                name="GET /members/:id (prefetch)",
            )
            if snapshot.status_code == 200:
                self.target_snapshot = safe_json(snapshot)

    @staticmethod
    def _infra_status(status_code: int | None) -> bool:
        return status_code in (None, 0)

    def _read_target(self) -> None:
        with self.client.get(
            f"/members/{TARGET_MEMBER_ID}",
            name="GET /members/:id (admin)",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                with _lock:
                    _metrics["admin_read_ok"] += 1
                response.success()
            else:
                with _lock:
                    _metrics["admin_read_fail"] += 1
                    if self._infra_status(response.status_code):
                        _metrics["infra_errors"] += 1
                response.failure(f"unexpected status {response.status_code}")

    def _admin_update(self) -> None:
        if not self.target_snapshot:
            with _lock:
                _metrics["admin_update_fail"] += 1
                _metrics["infra_errors"] += 1
            return

        new_name = f"LocustStress_{self.username}_{random.randint(1000, 9999)}"
        payload = {
            "full_name": new_name,
        }

        with self.client.put(
            f"/members/{TARGET_MEMBER_ID}",
            json=payload,
            name="PUT /members/:id (admin)",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                with _lock:
                    _metrics["admin_update_ok"] += 1
                    _metrics["updated_names"].append(new_name)
                response.success()
            else:
                with _lock:
                    _metrics["admin_update_fail"] += 1
                    if self._infra_status(response.status_code):
                        _metrics["infra_errors"] += 1
                response.failure(f"unexpected status {response.status_code}")

    def _unauthorized_update(self) -> None:
        if self.member_id is None:
            return

        payload = {
            "full_name": f"Unauthorized_{self.member_id}_{random.randint(1000, 9999)}",
        }

        with self.client.put(
            f"/members/{TARGET_MEMBER_ID}",
            json=payload,
            name="PUT /members/:id (unauthorized)",
            catch_response=True,
        ) as response:
            if response.status_code == 403:
                with _lock:
                    _metrics["unauth_update_denied"] += 1
                response.success()
            else:
                with _lock:
                    _metrics["unauth_update_other"] += 1
                    if self._infra_status(response.status_code):
                        _metrics["infra_errors"] += 1
                response.failure(f"expected 403, got {response.status_code}")

    @task
    def workload(self) -> None:
        """Run a simple read/update workload depending on the logged-in role."""
        if self.member_id is None:
            return

        if self.is_admin:
            if random.random() < (1 / UPDATE_EVERY):
                self._admin_update()
            else:
                self._read_target()
            return

        if random.random() < (1 / UNAUTH_UPDATE_EVERY):
            self._unauthorized_update()
        else:
            with self.client.get(
                f"/members/{self.member_id}",
                name="GET /members/:id (self)",
                catch_response=True,
            ) as response:
                if response.status_code == 200:
                    response.success()
                else:
                    with _lock:
                        if self._infra_status(response.status_code):
                            _metrics["infra_errors"] += 1
                    response.failure(f"unexpected status {response.status_code}")


@events.test_stop.add_listener
def write_summary(environment, **kwargs):
    """Write a compact JSON report after the Locust run completes."""
    total = environment.stats.total
    summary = {
        "target_member_id": TARGET_MEMBER_ID,
        "metrics": {
            "login_ok": _metrics["login_ok"],
            "login_fail": _metrics["login_fail"],
            "admin_read_ok": _metrics["admin_read_ok"],
            "admin_read_fail": _metrics["admin_read_fail"],
            "admin_update_ok": _metrics["admin_update_ok"],
            "admin_update_fail": _metrics["admin_update_fail"],
            "unauth_update_denied": _metrics["unauth_update_denied"],
            "unauth_update_other": _metrics["unauth_update_other"],
            "infra_errors": _metrics["infra_errors"],
        },
        "verification": {
            "admin_updates_succeeded": _metrics["admin_update_ok"] > 0,
            "unauthorized_updates_blocked": _metrics["unauth_update_other"] == 0,
            "no_infra_errors": _metrics["infra_errors"] == 0,
            "login_healthy": _metrics["login_fail"] == 0,
            "note": "403 on unauthorized updates is expected; any status0 or 5xx indicates a real problem.",
        },
        "locust_stats": {
            "total_requests": total.num_requests,
            "total_failures": total.num_failures,
            "avg_response_time_ms": total.avg_response_time,
            "p95_response_time_ms": total.get_response_time_percentile(0.95),
            "requests_per_sec": total.current_rps,
        },
        "sample_successful_update_names": _metrics["updated_names"][-20:],
    }

    out = Path(SUMMARY_FILE)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\nLocust summary written to: {out.resolve()}\n")
