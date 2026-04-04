import json
import os
import random
import threading
import time
from pathlib import Path

import requests
from locust import between, events, task
from locust.contrib.fasthttp import FastHttpUser


TARGET_MEMBER_ID = int(os.getenv("TARGET_MEMBER_ID", "1"))
USERS_FILE = os.getenv("USERS_FILE", "test_users.json")
SUMMARY_FILE = os.getenv("STRESS_SUMMARY_FILE", "../benchmarks/locust_stress_summary.json")

_lock = threading.Lock()
_users_cache = None
_metrics = {
    "admin_read_ok": 0,
    "admin_read_fail": 0,
    "admin_read_status0": 0,
    "admin_read_5xx": 0,
    "admin_update_ok": 0,
    "admin_update_fail": 0,
    "admin_update_status0": 0,
    "admin_update_5xx": 0,
    "unauth_update_denied": 0,
    "unauth_update_other": 0,
    "unauth_update_status0": 0,
    "unauth_update_5xx": 0,
    "infra_errors": 0,
    "admin_update_names": [],
}


def load_users() -> list[dict]:
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


class CallHubStressUser(FastHttpUser):
    wait_time = between(0.1, 0.5)

    def on_start(self) -> None:
        self.username = None
        self.password = None
        self.member_id = None
        self.is_admin = False
        self.update_payload_template = None

        creds = random.choice(load_users())
        self.username = creds["username"]
        self.password = creds["password"]

        login_response = self.client.post(
            "/login",
            json={"username": self.username, "password": self.password},
            name="POST /login",
        )
        if login_response.status_code != 200:
            return

        try:
            self.member_id = login_response.json().get("member_id")
        except Exception:
            self.member_id = None

        admin_response = self.client.get("/check-admin", name="GET /check-admin")
        if admin_response.status_code == 200:
            try:
                self.is_admin = bool(admin_response.json().get("is_admin"))
            except Exception:
                self.is_admin = False

        if self.is_admin:
            prefetch = self.client.get(
                f"/members/{TARGET_MEMBER_ID}",
                name="GET /members/:id (prefetch)",
            )
            if prefetch.status_code == 200:
                try:
                    self.update_payload_template = prefetch.json()
                except Exception:
                    self.update_payload_template = None

    @staticmethod
    def _is_infra_status(status_code: int | None) -> bool:
        return status_code in (None, 0)

    @task(5)
    def read_operation(self) -> None:
        # Admin reads shared target; regular reads own row to keep read path valid.
        member_id = TARGET_MEMBER_ID if self.is_admin else self.member_id
        if member_id is None:
            return

        with self.client.get(f"/members/{member_id}", name="GET /members/:id", catch_response=True) as response:
            if response.status_code == 200:
                with _lock:
                    _metrics["admin_read_ok"] += 1
                response.success()
            else:
                with _lock:
                    _metrics["admin_read_fail"] += 1
                    if self._is_infra_status(response.status_code):
                        _metrics["admin_read_status0"] += 1
                        _metrics["infra_errors"] += 1
                    elif 500 <= int(response.status_code) <= 599:
                        _metrics["admin_read_5xx"] += 1
                response.failure(f"unexpected status {response.status_code}")

    @task(3)
    def update_operation(self) -> None:
        if self.member_id is None:
            return

        # Non-admin users intentionally try to update target to verify isolation.
        if not self.is_admin:
            with self.client.put(
                f"/members/{TARGET_MEMBER_ID}",
                json={"full_name": f"Unauthorized_{int(time.time()*1000)}"},
                name="PUT /members/:id (unauthorized)",
                catch_response=True,
            ) as response:
                with _lock:
                    if response.status_code == 403:
                        _metrics["unauth_update_denied"] += 1
                        response.success()
                    else:
                        _metrics["unauth_update_other"] += 1
                        if self._is_infra_status(response.status_code):
                            _metrics["unauth_update_status0"] += 1
                            _metrics["infra_errors"] += 1
                        elif 500 <= int(response.status_code) <= 599:
                            _metrics["unauth_update_5xx"] += 1
                        response.failure(f"expected 403, got {response.status_code}")
            return

        # Admin update path reuses a cached valid payload to avoid extra prefetch overhead.
        if self.update_payload_template is None:
            with _lock:
                _metrics["admin_update_fail"] += 1
                _metrics["infra_errors"] += 1
            return

        payload = dict(self.update_payload_template)

        new_name = f"LocustStress_{self.username}_{int(time.time()*1000)}"
        payload["full_name"] = new_name

        with self.client.put(
            f"/members/{TARGET_MEMBER_ID}",
            json=payload,
            name="PUT /members/:id (admin)",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                with _lock:
                    _metrics["admin_update_ok"] += 1
                    _metrics["admin_update_names"].append(new_name)
                response.success()
            else:
                with _lock:
                    _metrics["admin_update_fail"] += 1
                    if self._is_infra_status(response.status_code):
                        _metrics["admin_update_status0"] += 1
                        _metrics["infra_errors"] += 1
                    elif 500 <= int(response.status_code) <= 599:
                        _metrics["admin_update_5xx"] += 1
                response.failure(f"unexpected status {response.status_code}")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    summary = {
        "target_member_id": TARGET_MEMBER_ID,
        "metrics": {
            "admin_read_ok": _metrics["admin_read_ok"],
            "admin_read_fail": _metrics["admin_read_fail"],
            "admin_read_status0": _metrics["admin_read_status0"],
            "admin_read_5xx": _metrics["admin_read_5xx"],
            "admin_update_ok": _metrics["admin_update_ok"],
            "admin_update_fail": _metrics["admin_update_fail"],
            "admin_update_status0": _metrics["admin_update_status0"],
            "admin_update_5xx": _metrics["admin_update_5xx"],
            "unauth_update_denied": _metrics["unauth_update_denied"],
            "unauth_update_other": _metrics["unauth_update_other"],
            "unauth_update_status0": _metrics["unauth_update_status0"],
            "unauth_update_5xx": _metrics["unauth_update_5xx"],
            "infra_errors": _metrics["infra_errors"],
        },
        "verification": {
            "atomicity_proxy": _metrics["admin_update_fail"] == 0 and _metrics["infra_errors"] == 0,
            "consistency_proxy": True,
            "isolation": _metrics["unauth_update_other"] == 0,
            "durability_hint": "Check final member full_name in SQL; it should match one of successful update names",
        },
        "classification": {
            "expected_access_denied_403": _metrics["unauth_update_denied"],
            "unexpected_status0": (
                _metrics["admin_read_status0"]
                + _metrics["admin_update_status0"]
                + _metrics["unauth_update_status0"]
            ),
            "unexpected_5xx": (
                _metrics["admin_read_5xx"]
                + _metrics["admin_update_5xx"]
                + _metrics["unauth_update_5xx"]
            ),
            "note": "403 on unauthorized updates is expected and treated as success; status0/5xx are real failures",
        },
        "sample_successful_update_names": _metrics["admin_update_names"][-20:],
        "locust_stats": {
            "total_requests": environment.stats.total.num_requests,
            "total_failures": environment.stats.total.num_failures,
            "avg_response_time_ms": environment.stats.total.avg_response_time,
            "p95_response_time_ms": environment.stats.total.get_response_time_percentile(0.95),
            "requests_per_sec": environment.stats.total.current_rps,
        },
    }

    for stat in environment.stats.entries.values():
        if stat.num_failures > 0 and stat.name != "PUT /members/:id (unauthorized)":
            summary["verification"]["consistency_proxy"] = False
            break

    out = Path(SUMMARY_FILE)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\nLocust summary written to: {out.resolve()}\n")

    host = environment.host
    if _metrics["admin_update_names"] and host and _metrics["infra_errors"] == 0:
        try:
            users = load_users()
            admin_found = None
            for user in users:
                s = requests.Session()
                login = s.post(
                    f"{host.rstrip('/')}/login",
                    json={"username": user["username"], "password": user["password"]},
                    timeout=10,
                )
                if login.status_code != 200:
                    continue
                chk = s.get(f"{host.rstrip('/')}/check-admin", timeout=10)
                if chk.status_code == 200 and chk.json().get("is_admin"):
                    admin_found = s
                    break
                s.close()

            if admin_found is not None:
                final_row = admin_found.get(f"{host.rstrip('/')}/members/{TARGET_MEMBER_ID}", timeout=10)
                if final_row.status_code == 200:
                    body = final_row.json()
                    final_name = body.get("full_name")
                    dur_ok = final_name in _metrics["admin_update_names"]

                    summary["durability_check"] = {
                        "final_name": final_name,
                        "matches_successful_update": dur_ok,
                    }
                    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        except Exception as ex:
            summary["durability_check"] = {"error": str(ex)}
            out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
