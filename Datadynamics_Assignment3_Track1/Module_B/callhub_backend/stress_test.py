import argparse
import json
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path

import requests


def now_tag() -> str:
    return datetime.now(UTC).strftime("%Y%m%d%H%M%S")


def new_session(base_url: str) -> requests.Session:
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    s.base_url = base_url.rstrip("/")
    return s


def login(session: requests.Session, username: str, password: str) -> tuple[bool, int, dict]:
    r = session.post(
        f"{session.base_url}/login",
        json={"username": username, "password": password},
        timeout=15,
    )
    try:
        data = r.json()
    except Exception:
        data = {"raw": r.text[:200]}
    return r.status_code == 200, r.status_code, data


def is_admin(session: requests.Session) -> bool:
    r = session.get(f"{session.base_url}/check-admin", timeout=10)
    try:
        return bool(r.json().get("is_admin"))
    except Exception:
        return False


def get_member(session: requests.Session, member_id: int) -> tuple[int, dict]:
    r = session.get(f"{session.base_url}/members/{member_id}", timeout=20)
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, {"raw": r.text[:200]}


def update_member_name(session: requests.Session, member_id: int, new_name: str) -> tuple[int, dict]:
    code, payload = get_member(session, member_id)
    if code != 200:
        return code, {"error": "prefetch failed", "prefetch": payload}

    payload["full_name"] = new_name
    r = session.put(f"{session.base_url}/members/{member_id}", json=payload, timeout=25)
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, {"raw": r.text[:200]}


def create_member(session: requests.Session, body: dict) -> tuple[int, dict]:
    r = session.post(f"{session.base_url}/members", json=body, timeout=25)
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, {"raw": r.text[:200]}


def delete_member(session: requests.Session, member_id: int) -> tuple[int, dict]:
    r = session.delete(f"{session.base_url}/members/{member_id}", timeout=20)
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, {"raw": r.text[:200]}


def list_members(session: requests.Session) -> tuple[int, list[dict] | dict]:
    r = session.get(f"{session.base_url}/members", timeout=25)
    try:
        data = r.json()
    except Exception:
        return r.status_code, {"raw": r.text[:200]}
    return r.status_code, data


def build_create_payload(tag: str, username: str, password: str, full_name: str, category_name: str, role_title: str) -> dict:
    return {
        "dept_id": 1,
        "category_name": category_name,
        "role_title": role_title,
        "full_name": full_name,
        "designation": "Stress Tester",
        "age": 25,
        "gender": "M",
        "join_date": "2024-01-01",
        "assign_date": "2024-01-01",
        "contact_type": "Official Email",
        "contact_value": f"{username}@example.com",
        "location_type": "Office",
        "building_name": "LoadTest",
        "room_number": f"S{tag[-4:]}",
        "emergency_name": "Emergency Contact",
        "relation": "Friend",
        "emergency_contact": "9999999999",
        "username": username,
        "password": password,
    }


def timing_stats(values: list[float]) -> dict:
    if not values:
        return {"count": 0, "min": None, "avg": None, "p95": None, "max": None}
    values_sorted = sorted(values)
    p95_index = max(0, int(0.95 * len(values_sorted)) - 1)
    return {
        "count": len(values_sorted),
        "min": round(values_sorted[0], 3),
        "avg": round(statistics.mean(values_sorted), 3),
        "p95": round(values_sorted[p95_index], 3),
        "max": round(values_sorted[-1], 3),
    }


def load_users(path: Path) -> list[dict]:
    users = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(users, list) or not users:
        raise ValueError("users file must contain a non-empty list")
    for user in users:
        if "username" not in user or "password" not in user:
            raise ValueError("each user must have username and password")
    return users


def classify_users(base_url: str, users: list[dict]) -> tuple[list[dict], list[dict]]:
    admins = []
    regular = []
    for user in users:
        s = new_session(base_url)
        ok, _, _ = login(s, user["username"], user["password"])
        if not ok:
            continue
        if is_admin(s):
            admins.append(user)
        else:
            regular.append(user)
    return admins, regular


def run_load(
    base_url: str,
    admins: list[dict],
    regular: list[dict],
    target_member_id: int,
    total_requests: int,
    workers: int,
    update_every: int,
    unauth_update_every: int,
) -> dict:
    if not admins:
        return {"error": "No admin users available for stress test"}

    records = []
    successful_update_names = []

    def task(i: int) -> dict:
        if regular and unauth_update_every > 0 and i % unauth_update_every == 0:
            op = "unauthorized_update"
            actor = regular[i % len(regular)]
        elif update_every > 0 and i % update_every == 0:
            op = "admin_update"
            actor = admins[i % len(admins)]
        else:
            op = "admin_read"
            actor = admins[i % len(admins)]

        session = new_session(base_url)
        ok, login_code, login_data = login(session, actor["username"], actor["password"])
        if not ok:
            return {
                "i": i,
                "op": "login",
                "actor": actor["username"],
                "ok": False,
                "status": login_code,
                "time_ms": 0,
                "response": login_data,
            }

        t0 = time.perf_counter()
        if op == "admin_read":
            status, data = get_member(session, target_member_id)
            dt = round((time.perf_counter() - t0) * 1000, 3)
            return {
                "i": i,
                "op": op,
                "actor": actor["username"],
                "ok": status == 200,
                "status": status,
                "time_ms": dt,
                "response": data,
            }

        if op == "admin_update":
            new_name = f"StressUpdate_{i}_{now_tag()}"
            status, data = update_member_name(session, target_member_id, new_name)
            dt = round((time.perf_counter() - t0) * 1000, 3)
            result = {
                "i": i,
                "op": op,
                "actor": actor["username"],
                "ok": status == 200,
                "status": status,
                "time_ms": dt,
                "name": new_name,
                "response": data,
            }
            if result["ok"]:
                successful_update_names.append(new_name)
            return result

        new_name = f"UnauthorizedAttempt_{i}_{now_tag()}"
        status, data = update_member_name(session, target_member_id, new_name)
        dt = round((time.perf_counter() - t0) * 1000, 3)
        return {
            "i": i,
            "op": op,
            "actor": actor["username"],
            "ok": status == 403,
            "status": status,
            "time_ms": dt,
            "name": new_name,
            "response": data,
        }

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(task, i) for i in range(total_requests)]
        for future in as_completed(futures):
            records.append(future.result())
    duration = round(time.perf_counter() - started, 3)

    status_distribution = {}
    for record in records:
        key = str(record.get("status"))
        status_distribution[key] = status_distribution.get(key, 0) + 1

    op_groups = {
        "admin_read": [r for r in records if r.get("op") == "admin_read"],
        "admin_update": [r for r in records if r.get("op") == "admin_update"],
        "unauthorized_update": [r for r in records if r.get("op") == "unauthorized_update"],
    }

    timing_by_op = {
        op: timing_stats([r["time_ms"] for r in group if isinstance(r.get("time_ms"), (int, float))])
        for op, group in op_groups.items()
    }

    return {
        "total_requests": total_requests,
        "workers": workers,
        "duration_sec": duration,
        "throughput_req_per_sec": round(total_requests / duration, 3) if duration > 0 else None,
        "status_distribution": status_distribution,
        "ok": sum(1 for r in records if r.get("ok")),
        "fail": sum(1 for r in records if not r.get("ok")),
        "timing_ms_by_op": timing_by_op,
        "successful_update_names": successful_update_names,
        "records": records,
    }


def verify_atomicity_and_rollback(base_url: str, admin_user: dict, category_name: str, role_title: str) -> dict:
    session = new_session(base_url)
    ok, _, _ = login(session, admin_user["username"], admin_user["password"])
    if not ok:
        return {"error": "Admin login failed for rollback verification"}

    tag = now_tag()
    username = f"stress_dup_{tag}"
    seed_name = f"StressSeed_{tag}"
    fail_name = f"StressRollback_{tag}"

    seed_payload = build_create_payload(tag, username, "SeedPass123!", seed_name, category_name, role_title)
    c1_status, c1_data = create_member(session, seed_payload)
    seed_member_id = c1_data.get("member_id") if isinstance(c1_data, dict) else None

    fail_payload = build_create_payload(tag, username, "AnotherPass123!", fail_name, category_name, role_title)
    c2_status, c2_data = create_member(session, fail_payload)

    lm_status, lm_data = list_members(session)
    failed_name_exists = False
    if lm_status == 200 and isinstance(lm_data, list):
        failed_name_exists = any(str(member.get("full_name")) == fail_name for member in lm_data)

    cleanup = {"status": None, "data": {"message": "cleanup skipped"}}
    if seed_member_id:
        d_status, d_data = delete_member(session, int(seed_member_id))
        cleanup = {"status": d_status, "data": d_data}

    seed_ok = c1_status == 200
    forced_failed = c2_status != 200
    rollback_verified = seed_ok and forced_failed and (not failed_name_exists)

    return {
        "seed_create": {"status": c1_status, "data": c1_data},
        "forced_failure": {"status": c2_status, "data": c2_data},
        "verification": {
            "seed_create_succeeded": seed_ok,
            "forced_failure_was_not_success": forced_failed,
            "failed_create_did_not_leave_member_row": not failed_name_exists,
            "rollback_verified": rollback_verified,
        },
        "cleanup_seed": cleanup,
    }


def verify_durability(base_url: str, admin_user: dict, target_member_id: int, delay_sec: int) -> dict:
    session1 = new_session(base_url)
    ok1, _, _ = login(session1, admin_user["username"], admin_user["password"])
    if not ok1:
        return {"error": "Initial admin login failed for durability check"}

    s1_status, s1_data = get_member(session1, target_member_id)
    first_name = s1_data.get("full_name") if isinstance(s1_data, dict) else None

    time.sleep(max(0, delay_sec))

    session2 = new_session(base_url)
    ok2, _, _ = login(session2, admin_user["username"], admin_user["password"])
    if not ok2:
        return {"error": "Second admin login failed for durability check"}

    s2_status, s2_data = get_member(session2, target_member_id)
    second_name = s2_data.get("full_name") if isinstance(s2_data, dict) else None

    return {
        "first_read": {"status": s1_status, "full_name": first_name},
        "second_read": {"status": s2_status, "full_name": second_name},
        "persisted_after_delay": (s1_status == 200 and s2_status == 200 and first_name == second_name),
    }


def slim_load_records(load_result: dict) -> dict:
    if "records" not in load_result:
        return load_result
    copy = dict(load_result)
    copy.pop("records", None)
    return copy


def build_verdict(report: dict) -> dict:
    load_result = report.get("load_test", {})
    verification = report.get("verification", {})

    if "error" in load_result:
        return {
            "overall": "FAIL",
            "reasons": [f"load_test_error: {load_result['error']}"]
        }

    if "error" in verification:
        return {
            "overall": "FAIL",
            "reasons": [f"verification_error: {verification['error']}"]
        }

    atomicity_ok = bool(verification.get("atomicity", {}).get("rollback_verified"))
    consistency = verification.get("consistency", {})
    consistency_ok = bool(consistency.get("no_5xx_in_load")) and bool(consistency.get("final_name_from_successful_updates"))
    isolation_ok = bool(verification.get("isolation", {}).get("isolation_verified"))
    durability_ok = bool(verification.get("durability", {}).get("persisted_after_delay"))

    checks = {
        "atomicity": atomicity_ok,
        "consistency": consistency_ok,
        "isolation": isolation_ok,
        "durability": durability_ok,
    }

    reasons = [name for name, ok in checks.items() if not ok]
    return {
        "overall": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "reasons": reasons,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Stress test for Module B")
    parser.add_argument("--base-url", default="http://127.0.0.1:5000")
    parser.add_argument("--users-file", default="test_users.json")
    parser.add_argument("--target-member-id", type=int, required=True)
    parser.add_argument("--requests", type=int, default=1000)
    parser.add_argument("--workers", type=int, default=50)
    parser.add_argument("--update-every", type=int, default=4)
    parser.add_argument("--unauth-update-every", type=int, default=10)
    parser.add_argument("--durability-delay-sec", type=int, default=3)
    parser.add_argument("--category-name", default="Public")
    parser.add_argument("--role-title", default="Director")
    parser.add_argument("--include-records", action="store_true", help="Include per-request records in load_test output")
    parser.add_argument("--out-file", default="../benchmarks/stress_test_report.json")
    args = parser.parse_args()

    users = load_users(Path(args.users_file))
    admins, regular = classify_users(args.base_url, users)

    report = {
        "timestamp": datetime.now(UTC).isoformat(),
        "base_url": args.base_url,
        "target_member_id": args.target_member_id,
        "input": {
            "requests": args.requests,
            "workers": args.workers,
            "update_every": args.update_every,
            "unauth_update_every": args.unauth_update_every,
        },
        "user_pool": {
            "provided": len(users),
            "admins": len(admins),
            "regular": len(regular),
        },
    }

    load_result = run_load(
        base_url=args.base_url,
        admins=admins,
        regular=regular,
        target_member_id=args.target_member_id,
        total_requests=args.requests,
        workers=args.workers,
        update_every=args.update_every,
        unauth_update_every=args.unauth_update_every,
    )
    report["load_test"] = load_result

    if admins and "error" not in load_result:
        atomicity = verify_atomicity_and_rollback(
            base_url=args.base_url,
            admin_user=admins[0],
            category_name=args.category_name,
            role_title=args.role_title,
        )
        durability = verify_durability(
            base_url=args.base_url,
            admin_user=admins[0],
            target_member_id=args.target_member_id,
            delay_sec=args.durability_delay_sec,
        )

        final_name = None
        if load_result.get("successful_update_names"):
            session = new_session(args.base_url)
            ok, _, _ = login(session, admins[0]["username"], admins[0]["password"])
            if ok:
                status, data = get_member(session, args.target_member_id)
                if status == 200 and isinstance(data, dict):
                    final_name = data.get("full_name")

        isolation_denied = sum(
            1
            for r in load_result.get("records", [])
            if r.get("op") == "unauthorized_update" and r.get("status") == 403
        )
        isolation_attempts = sum(
            1 for r in load_result.get("records", []) if r.get("op") == "unauthorized_update"
        )

        report["verification"] = {
            "atomicity": atomicity.get("verification", {}),
            "consistency": {
                "no_5xx_in_load": all(int(r.get("status") or 0) < 500 for r in load_result.get("records", [])),
                "final_name_from_successful_updates": (
                    final_name in load_result.get("successful_update_names", [])
                    if final_name
                    else False
                ),
            },
            "isolation": {
                "unauthorized_updates_denied": isolation_denied,
                "unauthorized_updates_attempted": isolation_attempts,
                "isolation_verified": isolation_attempts == isolation_denied,
            },
            "durability": durability,
        }
        report["atomicity_probe"] = atomicity
    else:
        report["verification"] = {
            "error": "Verification skipped because no admin users were available or load test failed"
        }

    if not args.include_records and "load_test" in report:
        report["load_test"] = slim_load_records(report["load_test"])

    report["verdict"] = build_verdict(report)

    out_path = Path(args.out_file)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("Stress test complete")
    print(f"Saved: {out_path.resolve()}")
    if "error" in load_result:
        print(f"[load] error={load_result['error']}")
        return

    print(
        f"[load] ok={load_result['ok']} fail={load_result['fail']} "
        f"throughput={load_result['throughput_req_per_sec']} req/s"
    )
    if "verification" in report and "error" not in report["verification"]:
        print(f"[verification.atomicity] {report['verification']['atomicity']}")
        print(f"[verification.consistency] {report['verification']['consistency']}")
        print(f"[verification.isolation] {report['verification']['isolation']}")
        print(f"[verification.durability] {report['verification']['durability']}")
    print(f"[verdict] overall={report['verdict']['overall']} checks={report['verdict'].get('checks', {})}")
    if report["verdict"].get("reasons"):
        print(f"[verdict_reasons] {report['verdict']['reasons']}")


if __name__ == "__main__":
    main()
