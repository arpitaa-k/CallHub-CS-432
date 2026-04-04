import argparse
import json
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


def login(session: requests.Session, username: str, password: str) -> tuple[bool, dict]:
    r = session.post(f"{session.base_url}/login", json={"username": username, "password": password}, timeout=15)
    data = {}
    try:
        data = r.json()
    except Exception:
        data = {"raw": r.text[:200]}
    return r.status_code == 200, {"status": r.status_code, "response": data}


def is_admin(session: requests.Session) -> bool:
    r = session.get(f"{session.base_url}/check-admin", timeout=15)
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
        return code, {"error": "cannot fetch member for update", "details": payload}

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
    r = session.get(f"{session.base_url}/members", timeout=20)
    try:
        data = r.json()
    except Exception:
        return r.status_code, {"raw": r.text[:200]}
    return r.status_code, data


def build_create_payload(tag: str, username: str, password: str, category_name: str, role_title: str, full_name: str) -> dict:
    return {
        "dept_id": 1,
        "category_name": category_name,
        "role_title": role_title,
        "full_name": full_name,
        "designation": "Concurrent Tester",
        "age": 25,
        "gender": "M",
        "join_date": "2024-01-01",
        "assign_date": "2024-01-01",
        "contact_type": "Official Email",
        "contact_value": f"{username}@example.com",
        "location_type": "Office",
        "building_name": "TestBlock",
        "room_number": f"R{tag[-4:]}",
        "emergency_name": "Emergency Contact",
        "relation": "Friend",
        "emergency_contact": "9999999999",
        "username": username,
        "password": password,
    }


def run_race_update(base_url: str, users: list[dict], target_member_id: int, attempts: int, workers: int) -> dict:
    # Keep only admin users because update endpoint is admin-only.
    admin_users = []
    for u in users:
        s = new_session(base_url)
        ok, _ = login(s, u["username"], u["password"])
        if ok and is_admin(s):
            admin_users.append(u)

    if not admin_users:
        return {
            "error": "No admin user available for race update test",
            "attempts": attempts,
            "workers": workers,
        }

    # Capture original value so we can restore it after the race test.
    original_name = None
    baseline_session = new_session(base_url)
    baseline_ok, _ = login(baseline_session, admin_users[0]["username"], admin_users[0]["password"])
    if baseline_ok:
        base_status, base_data = get_member(baseline_session, target_member_id)
        if base_status == 200 and isinstance(base_data, dict):
            original_name = base_data.get("full_name")

    results = []
    successful_names = []

    def task(i: int) -> dict:
        actor = admin_users[i % len(admin_users)]
        s = new_session(base_url)
        ok, login_info = login(s, actor["username"], actor["password"])
        if not ok:
            return {"i": i, "op": "login", "ok": False, "status": login_info["status"], "details": login_info}

        new_name = f"RaceUpdate_{i}_{now_tag()}"
        t0 = time.perf_counter()
        code, data = update_member_name(s, target_member_id, new_name)
        dt = round((time.perf_counter() - t0) * 1000, 3)

        return {
            "i": i,
            "op": "update",
            "ok": code == 200,
            "status": code,
            "time_ms": dt,
            "name": new_name,
            "response": data,
        }

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = [ex.submit(task, i) for i in range(attempts)]
        for f in as_completed(futures):
            r = f.result()
            results.append(r)
            if r.get("ok") and r.get("name"):
                successful_names.append(r["name"])

    # Final state check
    final_session = new_session(base_url)
    ok, _ = login(final_session, admin_users[0]["username"], admin_users[0]["password"])
    final = {"status": None, "data": {"error": "final read skipped"}}
    if ok:
        status, data = get_member(final_session, target_member_id)
        final = {"status": status, "data": data}

    final_name = final["data"].get("full_name") if isinstance(final.get("data"), dict) else None
    successful_update_count = len(successful_names)

    timing_values = [r.get("time_ms") for r in results if isinstance(r.get("time_ms"), (int, float))]
    timing_values = sorted(float(v) for v in timing_values)
    p95 = None
    if timing_values:
        p95_index = max(0, int(0.95 * len(timing_values)) - 1)
        p95 = round(timing_values[p95_index], 3)

    restore = {
        "attempted": bool(original_name),
        "ok": False,
        "status": None,
    }
    if original_name:
        restore_session = new_session(base_url)
        restore_ok, _ = login(restore_session, admin_users[0]["username"], admin_users[0]["password"])
        if restore_ok:
            r_status, _ = update_member_name(restore_session, target_member_id, original_name)
            restore["status"] = r_status
            restore["ok"] = r_status == 200

    return {
        "attempts": attempts,
        "workers": workers,
        "admin_users_used": len(admin_users),
        "ok": sum(1 for r in results if r.get("ok")),
        "fail": sum(1 for r in results if not r.get("ok")),
        "status_distribution": {
            str(code): sum(1 for r in results if str(r.get("status")) == str(code))
            for code in sorted({r.get("status") for r in results}, key=lambda x: str(x))
        },
        "correctness": {
            "all_attempts_accounted_for": len(results) == attempts,
            "no_5xx": all(int(r.get("status") or 0) < 500 for r in results),
            # For this assignment level, last-write-wins is acceptable. This check ensures
            # the final winner was one of the successful concurrent writes.
            "last_write_wins_legitimate": final_name in successful_names if final_name else False,
            "successful_update_count": successful_update_count,
        },
        "timing_ms": {
            "count": len(timing_values),
            "min": round(timing_values[0], 3) if timing_values else None,
            "avg": round(sum(timing_values) / len(timing_values), 3) if timing_values else None,
            "p95": p95,
            "max": round(timing_values[-1], 3) if timing_values else None,
        },
        "final_member": final,
        "cleanup_restore_target_name": restore,
        "records": results,
    }


def run_failure_rollback(base_url: str, users: list[dict], category_name: str, role_title: str) -> dict:
    # Need admin for create/delete.
    admin = None
    admin_session = None
    for u in users:
        s = new_session(base_url)
        ok, _ = login(s, u["username"], u["password"])
        if ok and is_admin(s):
            admin = u
            admin_session = s
            break

    if not admin or not admin_session:
        return {"error": "No admin user available for failure simulation"}

    tag = now_tag()
    dup_username = f"rf_dup_{tag}"

    good_name = f"FailureSeed_{tag}"
    good_password = "SeedPass123!"
    good_payload = build_create_payload(tag, dup_username, good_password, category_name, role_title, good_name)

    # Step 1: successful create (seed)
    c1_status, c1_data = create_member(admin_session, good_payload)
    seed_member_id = c1_data.get("member_id") if isinstance(c1_data, dict) else None

    # Step 2: forced failure create using same username (unique violation expected)
    bad_name = f"FailureShouldRollback_{tag}"
    bad_payload = build_create_payload(tag, dup_username, "AnotherPass123!", category_name, role_title, bad_name)
    c2_status, c2_data = create_member(admin_session, bad_payload)

    # Step 3: verify rollback/no partial member row with failed full_name
    lm_status, lm_data = list_members(admin_session)
    failed_name_exists = False
    if lm_status == 200 and isinstance(lm_data, list):
        failed_name_exists = any(str(m.get("full_name")) == bad_name for m in lm_data)

    # Step 4: cleanup seed member
    cleanup = {"status": None, "data": {"message": "cleanup skipped"}}
    if seed_member_id:
        d_status, d_data = delete_member(admin_session, int(seed_member_id))
        cleanup = {"status": d_status, "data": d_data}

    seed_ok = c1_status == 200
    forced_failed = c2_status != 200
    rollback_verified = seed_ok and forced_failed and (not failed_name_exists)

    return {
        "seed_create": {"status": c1_status, "data": c1_data},
        "forced_failure_create": {"status": c2_status, "data": c2_data},
        "verification": {
            "seed_create_succeeded": seed_ok,
            "forced_failure_was_not_success": forced_failed,
            "failed_create_did_not_leave_member_row": not failed_name_exists,
            "rollback_test_valid": seed_ok,
            "rollback_verified": rollback_verified,
        },
        "cleanup_seed": cleanup,
    }


def build_verdict(race: dict, failure: dict) -> dict:
    if "error" in race:
        return {
            "module_b_part": "race_condition_and_failure_simulation",
            "overall": "FAIL",
            "reasons": [f"race_condition_test_error: {race['error']}"]
        }

    if "error" in failure:
        return {
            "module_b_part": "race_condition_and_failure_simulation",
            "overall": "FAIL",
            "reasons": [f"failure_simulation_test_error: {failure['error']}"]
        }

    race_ok = (
        race.get("correctness", {}).get("all_attempts_accounted_for")
        and race.get("correctness", {}).get("no_5xx")
        and race.get("correctness", {}).get("last_write_wins_legitimate")
    )
    failure_ok = failure.get("verification", {}).get("rollback_verified")

    reasons = []
    if not race.get("correctness", {}).get("all_attempts_accounted_for"):
        reasons.append("Race test did not return all attempted requests")
    if not race.get("correctness", {}).get("no_5xx"):
        reasons.append("Race test produced at least one 5xx response")
    if not race.get("correctness", {}).get("last_write_wins_legitimate"):
        reasons.append("Final member state did not match any successful concurrent update")
    if not failure_ok:
        reasons.append("Failure simulation did not verify rollback")

    return {
        "module_b_part": "race_condition_and_failure_simulation",
        "overall": "PASS" if (race_ok and failure_ok) else "FAIL",
        "checks": {
            "race_last_write_wins_sanity": bool(race_ok),
            "failure_rollback": bool(failure_ok),
        },
        "acid_mapping": {
            "atomicity": "failure_rollback",
            "consistency": "last_write_wins_legitimate + no_5xx",
            "isolation": "basic concurrent sanity only (does not detect lost updates)",
            "durability": "not validated by this script",
        },
        "notes": [
            "last-write-wins is treated as acceptable for this assignment level",
            "this script validates winner legitimacy, not strict conflict-serializable isolation",
        ],
        "reasons": reasons,
    }


def slim_race_records(race: dict) -> dict:
    if "records" not in race:
        return race
    race_copy = dict(race)
    race_copy.pop("records", None)
    return race_copy


def load_users(path: Path) -> list[dict]:
    users = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(users, list) or not users:
        raise ValueError("users file must contain a non-empty list")
    for u in users:
        if "username" not in u or "password" not in u:
            raise ValueError("each user must have username and password")
    return users


def main() -> None:
    p = argparse.ArgumentParser(description="Race Condition + Failure Simulation test")
    p.add_argument("--base-url", default="http://127.0.0.1:5000")
    p.add_argument("--users-file", default="test_users.json")
    p.add_argument("--target-member-id", type=int, required=True)
    p.add_argument("--race-attempts", type=int, default=60)
    p.add_argument("--workers", type=int, default=20)
    p.add_argument("--category-name", default="Public")
    p.add_argument("--role-title", default="Admin")
    p.add_argument("--include-records", action="store_true", help="Include per-request records in JSON report")
    p.add_argument("--out-file", default="../benchmarks/race_failure_report.json")
    args = p.parse_args()

    users = load_users(Path(args.users_file))

    race = run_race_update(
        base_url=args.base_url,
        users=users,
        target_member_id=args.target_member_id,
        attempts=args.race_attempts,
        workers=args.workers,
    )
    failure = run_failure_rollback(
        base_url=args.base_url,
        users=users,
        category_name=args.category_name,
        role_title=args.role_title,
    )

    if not args.include_records and "records" in race:
        race = slim_race_records(race)

    report = {
        "timestamp": datetime.now(UTC).isoformat(),
        "base_url": args.base_url,
        "target_member_id": args.target_member_id,
        "race_condition_test": race,
        "failure_simulation_test": failure,
        "verdict": build_verdict(race, failure),
    }

    out_path = Path(args.out_file)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    race = report["race_condition_test"]
    failure = report["failure_simulation_test"]
    verdict = report["verdict"]

    print("Race + failure tests complete")
    print(f"Saved: {out_path.resolve()}")
    if "error" in race:
        print(f"[race_condition] error={race['error']}")
    else:
        print(f"[race_condition] ok={race['ok']} fail={race['fail']} status={race['status_distribution']}")
        print(f"[race_timing_ms] {race.get('timing_ms')}")
        print(f"[race_correctness] {race['correctness']}")
    if "error" in failure:
        print(f"[failure_simulation] error={failure['error']}")
    else:
        print(f"[failure_simulation] seed_create={failure['seed_create']['status']} forced_failure={failure['forced_failure_create']['status']}")
        print(f"[failure_verification] {failure['verification']}")
    print(f"[verdict] overall={verdict['overall']} checks={verdict.get('checks', {})}")
    if verdict.get("reasons"):
        print(f"[verdict_reasons] {verdict['reasons']}")


if __name__ == "__main__":
    main()
