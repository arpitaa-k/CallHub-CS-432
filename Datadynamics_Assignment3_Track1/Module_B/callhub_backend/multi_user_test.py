import argparse
import json
import random
import statistics
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, UTC
from pathlib import Path

import requests


class ConcurrentUsageTester:
	def __init__(self, base_url: str, users: list[dict], target_member_id: int, workers: int = 20):
		self.base_url = base_url.rstrip("/")
		self.users = users
		self.target_member_id = target_member_id
		self.workers = workers
		self._created_member_ids: list[int] = []
		self._created_ids_lock = threading.Lock()

	def _new_session(self) -> requests.Session:
		session = requests.Session()
		session.headers.update({"Content-Type": "application/json"})
		return session

	def _admin_users(self) -> list[dict]:
		admins = []
		for user in self.users:
			session = self._new_session()
			ok, _ = self._login(session, user["username"], user["password"])
			if not ok:
				continue
			try:
				res = session.get(f"{self.base_url}/check-admin", timeout=10)
				if bool(res.json().get("is_admin")):
					admins.append(user)
			except Exception:
				pass
		return admins

	def _login(self, session: requests.Session, username: str, password: str) -> tuple[bool, dict]:
		t0 = time.perf_counter()
		try:
			response = session.post(
				f"{self.base_url}/login",
				json={"username": username, "password": password},
				timeout=15,
			)
			try:
				body = response.json()
			except Exception:
				body = {"raw": response.text[:120]}
			return response.status_code == 200, {"status": response.status_code, "response": body}
		except Exception as exc:
			return False, {"status": None, "response": {"error": str(exc)}}

	def _read_member(self, session: requests.Session, actor: str, member_id: int) -> dict:
		t0 = time.perf_counter()
		try:
			response = session.get(
				f"{self.base_url}/member/{member_id}/portfolio",
				timeout=15,
			)
			elapsed_ms = (time.perf_counter() - t0) * 1000
			data = {}
			try:
				data = response.json()
			except Exception:
				pass
			return {
				"operation": "read",
				"actor": actor,
				"status_code": response.status_code,
				"ok": response.status_code == 200,
				"time_ms": elapsed_ms,
				"response": data,
			}
		except Exception as exc:
			elapsed_ms = (time.perf_counter() - t0) * 1000
			return {
				"operation": "read",
				"actor": actor,
				"status_code": None,
				"ok": False,
				"time_ms": elapsed_ms,
				"error": str(exc),
			}

	def _update_member(self, session: requests.Session, actor: str, tag: str) -> dict:
		t0 = time.perf_counter()
		try:
			current = session.get(
				f"{self.base_url}/members/{self.target_member_id}",
				timeout=15,
			)
			if current.status_code != 200:
				elapsed_ms = (time.perf_counter() - t0) * 1000
				return {
					"operation": "update",
					"actor": actor,
					"status_code": current.status_code,
					"ok": False,
					"time_ms": elapsed_ms,
					"error": "prefetch failed",
					"payload_tag": tag,
				}

			payload = current.json()
			payload["full_name"] = f"Concurrent {tag}"

			response = session.put(
				f"{self.base_url}/members/{self.target_member_id}",
				json=payload,
				timeout=15,
			)
			elapsed_ms = (time.perf_counter() - t0) * 1000
			body = {}
			try:
				body = response.json()
			except Exception:
				pass

			return {
				"operation": "update",
				"actor": actor,
				"status_code": response.status_code,
				"ok": response.status_code == 200,
				"time_ms": elapsed_ms,
				"response": body,
				"payload_tag": tag,
			}
		except Exception as exc:
			elapsed_ms = (time.perf_counter() - t0) * 1000
			return {
				"operation": "update",
				"actor": actor,
				"status_code": None,
				"ok": False,
				"time_ms": elapsed_ms,
				"error": str(exc),
				"payload_tag": tag,
			}

	def _create_member(self, session: requests.Session, actor: str, tag: str, category_name: str, role_title: str) -> dict:
		t0 = time.perf_counter()
		payload = {
			"dept_id": 1,
			"category_name": category_name,
			"role_title": role_title,
			"full_name": f"Concurrent_Create_{tag}",
			"designation": "Concurrent Tester",
			"age": 25,
			"gender": "F",
			"join_date": "2026-04-01",
			"assign_date": "2026-04-01",
			"contact_type": "Official Email",
			"contact_value": f"concurrent_{tag}@example.com",
			"location_type": "Office",
			"building_name": "Test Block",
			"room_number": f"C-{random.randint(100, 999)}",
			"emergency_name": "Test Contact",
			"relation": "Friend",
			"emergency_contact": f"9{random.randint(100000000, 999999999)}",
			"username": f"concurrent_user_{tag}",
			"password": "Pass@123",
		}
		try:
			response = session.post(f"{self.base_url}/members", json=payload, timeout=15)
			elapsed_ms = (time.perf_counter() - t0) * 1000
			body = {}
			try:
				body = response.json()
			except Exception:
				pass

			created_id = body.get("member_id") if isinstance(body, dict) else None
			if response.status_code == 200 and isinstance(created_id, int):
				with self._created_ids_lock:
					self._created_member_ids.append(created_id)

			return {
				"operation": "create",
				"actor": actor,
				"status_code": response.status_code,
				"ok": response.status_code == 200,
				"time_ms": elapsed_ms,
				"response": body,
				"payload_tag": tag,
				"created_member_id": created_id,
			}
		except Exception as exc:
			elapsed_ms = (time.perf_counter() - t0) * 1000
			return {
				"operation": "create",
				"actor": actor,
				"status_code": None,
				"ok": False,
				"time_ms": elapsed_ms,
				"error": str(exc),
				"payload_tag": tag,
			}

	def _delete_member(self, session: requests.Session, actor: str, delete_member_id: int) -> dict:
		t0 = time.perf_counter()
		try:
			response = session.delete(f"{self.base_url}/members/{delete_member_id}", timeout=15)
			elapsed_ms = (time.perf_counter() - t0) * 1000
			body = {}
			try:
				body = response.json()
			except Exception:
				pass
			return {
				"operation": "delete",
				"actor": actor,
				"status_code": response.status_code,
				"ok": response.status_code == 200,
				"time_ms": elapsed_ms,
				"response": body,
				"delete_member_id": delete_member_id,
			}
		except Exception as exc:
			elapsed_ms = (time.perf_counter() - t0) * 1000
			return {
				"operation": "delete",
				"actor": actor,
				"status_code": None,
				"ok": False,
				"time_ms": elapsed_ms,
				"error": str(exc),
				"delete_member_id": delete_member_id,
			}

	def _run_single(
		self,
		user: dict,
		mode: str,
		iteration: int,
		create_category_name: str = "Public",
		create_role_title: str = "Member",
		delete_member_id: int | None = None,
	) -> list[dict]:
		session = self._new_session()
		username = user["username"]
		password = user["password"]

		login_ok, login_info = self._login(session, username, password)
		result = [{"operation": "login", "actor": username, "ok": login_ok, "info": login_info}]

		if not login_ok:
			return result

		member_id = None
		if isinstance(login_info, dict):
			member_id = login_info.get("response", {}).get("member_id")
		if not isinstance(member_id, int):
			result.append({"operation": "read", "actor": username, "status_code": None, "ok": False, "time_ms": 0, "error": "member_id missing from login response"})
			return result

		if mode == "read":
			result.append(self._read_member(session, username, member_id))
		elif mode == "update":
			tag = f"{username}_{iteration}_{random.randint(1000, 9999)}"
			result.append(self._update_member(session, username, tag))
		elif mode == "create":
			result.append({"operation": "create", "actor": username, "status_code": None, "ok": False, "time_ms": 0, "error": "create not used in the simplified concurrent test"})
		elif mode == "delete":
			result.append({"operation": "delete", "actor": username, "status_code": None, "ok": False, "time_ms": 0, "error": "delete not used in the simplified concurrent test"})
		else:
			result.append(self._read_member(session, username, member_id))

		return result

	@staticmethod
	def _timing_stats(values: list[float]) -> dict:
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

	def _run_scenario(
		self,
		mode: str,
		total_requests: int,
		create_category_name: str = "Public",
		create_role_title: str = "Member",
		delete_member_id: int | None = None,
	) -> dict:
		records: list[dict] = []
		futures = []

		with ThreadPoolExecutor(max_workers=self.workers) as pool:
			for i in range(total_requests):
				user = self.users[i % len(self.users)]
				futures.append(
					pool.submit(
						self._run_single,
						user,
						mode,
						i,
						create_category_name,
						create_role_title,
						delete_member_id,
					)
				)

			for future in as_completed(futures):
				try:
					records.extend(future.result())
				except Exception as exc:
					records.append({"operation": "internal", "ok": False, "error": str(exc)})

		logins = [r for r in records if r.get("operation") == "login"]
		ops = [r for r in records if r.get("operation") in ("read", "update", "create", "delete")]
		timings = [r["time_ms"] for r in ops if isinstance(r.get("time_ms"), (float, int))]

		status_distribution = {}
		for record in ops:
			code = str(record.get("status_code"))
			status_distribution[code] = status_distribution.get(code, 0) + 1

		summary = {
			"mode": mode,
			"total_requests": total_requests,
			"workers": self.workers,
			"login_success": sum(1 for r in logins if r.get("ok")),
			"login_fail": sum(1 for r in logins if not r.get("ok")),
			"op_success": sum(1 for r in ops if r.get("ok")),
			"op_fail": sum(1 for r in ops if not r.get("ok")),
			"status_code_distribution": status_distribution,
			"timing_ms": self._timing_stats(timings),
		}

		return {"summary": summary, "records": records}

	def _final_state(self, check_user: dict) -> dict:
		session = self._new_session()
		login_ok, login_info = self._login(session, check_user["username"], check_user["password"])
		if not login_ok:
			return {"ok": False, "error": f"Unable to login for final-state check: {login_info}"}

		member_id = None
		if isinstance(login_info, dict):
			member_id = login_info.get("response", {}).get("member_id")
		if not isinstance(member_id, int):
			return {"ok": False, "error": "member_id missing from login response"}

		return self._read_member(session, check_user["username"], member_id)

	def run_all(
		self,
		read_requests: int,
		update_requests: int,
		mixed_requests: int,
		create_requests: int,
		delete_requests: int,
		create_category_name: str,
		create_role_title: str,
	) -> dict:
		report = {
			"timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
			"base_url": self.base_url,
			"target_member_id": self.target_member_id,
			"users_count": len(self.users),
			"scenarios": {
				"concurrent_own_profile_reads": self._run_scenario("read", read_requests),
			},
			"final_member_state": self._final_state(self.users[0]),
			"notes": [
				"Own-profile data may show empty contacts/locations for some roles due to category-based RBAC filtering.",
			],
		}

		if update_requests > 0:
			admins = self._admin_users()
			if admins:
				original_users = self.users
				self.users = admins
				report["scenarios"]["concurrent_shared_member_updates"] = self._run_scenario("update", update_requests)
				self.users = original_users
			else:
				report["scenarios"]["concurrent_shared_member_updates"] = {
					"summary": {
						"mode": "update",
						"total_requests": update_requests,
						"workers": self.workers,
						"login_success": 0,
						"login_fail": 0,
						"op_success": 0,
						"op_fail": update_requests,
						"status_code_distribution": {},
						"timing_ms": {"count": 0, "min": None, "avg": None, "p95": None, "max": None},
					},
					"records": [{"operation": "update", "ok": False, "error": "No admin users available for shared update scenario"}],
				}
				report["notes"].append("Shared update scenario requires at least one admin user.")

		return report


def load_users(path: Path) -> list[dict]:
	users = json.loads(path.read_text(encoding="utf-8"))
	if not isinstance(users, list) or not users:
		raise ValueError("users file must contain a non-empty list")
	for user in users:
		if "username" not in user or "password" not in user:
			raise ValueError("each user must have username and password")
	return users


def build_verdict(report: dict) -> dict:
	scenarios = report.get("scenarios", {})
	checks = {}
	for name, scenario in scenarios.items():
		summary = scenario.get("summary", {})
		checks[name] = (
			summary.get("login_fail", 0) == 0
			and summary.get("op_fail", 0) == 0
			and summary.get("op_success", 0) == summary.get("total_requests", 0)
		)
	overall_ok = all(checks.values()) if checks else False
	return {
		"overall": "PASS" if overall_ok else "FAIL",
		"checks": checks,
		"note": "Own-profile reads validate concurrent usage for all users. Shared updates (when enabled) validate concurrent modifications on the same record.",
	}


def compact_report(report: dict) -> dict:
	compact_scenarios = {}
	for name, scenario in report.get("scenarios", {}).items():
		compact_scenarios[name] = scenario.get("summary", {})

	result = {
		"timestamp": report.get("timestamp"),
		"base_url": report.get("base_url"),
		"users_count": report.get("users_count"),
		"scenarios": compact_scenarios,
		"final_member_state": report.get("final_member_state"),
		"notes": report.get("notes", []),
	}
	result["verdict"] = build_verdict(report)
	return result


def print_concise_report(report: dict) -> None:
	verdict = report.get("verdict", {})
	reads = report.get("scenarios", {}).get("concurrent_own_profile_reads", {})
	summary = reads.get("summary", {})
	print("Concurrent usage test complete")
	print(f"Timestamp: {report.get('timestamp')}")
	print(f"Users used: {report.get('users_count')}")
	print(f"Verdict: {verdict.get('overall', 'UNKNOWN')}")
	print(
		f"Own-profile reads: requests={summary.get('total_requests', 0)} "
		f"ok={summary.get('op_success', 0)} fail={summary.get('op_fail', 0)} "
		f"status={summary.get('status_code_distribution', {})}"
	)
	shared = report.get("scenarios", {}).get("concurrent_shared_member_updates", {})
	if shared:
		shared_summary = shared.get("summary", {})
		print(
			f"Shared updates: requests={shared_summary.get('total_requests', 0)} "
			f"ok={shared_summary.get('op_success', 0)} fail={shared_summary.get('op_fail', 0)} "
			f"status={shared_summary.get('status_code_distribution', {})}"
		)
	if report.get("final_member_state"):
		print(f"Final state check: {report['final_member_state']}")
	if verdict.get("note"):
		print(f"Note: {verdict['note']}")
	for note in report.get("notes", []):
		print(f"Info: {note}")


def main() -> None:
	parser = argparse.ArgumentParser(description="Simple concurrent usage test")
	parser.add_argument("--base-url", default="http://127.0.0.1:5000")
	parser.add_argument("--users-file", default="test_users.json")
	parser.add_argument("--target-member-id", type=int, default=1)
	parser.add_argument("--read-requests", type=int, default=200)
	parser.add_argument("--update-requests", type=int, default=100)
	parser.add_argument("--workers", type=int, default=20)
	parser.add_argument("--out-file", default="../benchmarks/concurrent_usage_report.json")
	parser.add_argument("--include-records", action="store_true", help="Include full per-request records in the JSON report")
	args = parser.parse_args()

	users = load_users(Path(args.users_file))
	tester = ConcurrentUsageTester(args.base_url, users, args.target_member_id, workers=args.workers)
	report = tester.run_all(
		read_requests=args.read_requests,
		update_requests=args.update_requests,
		mixed_requests=0,
		create_requests=0,
		delete_requests=0,
		create_category_name="Public",
		create_role_title="Member",
	)

	report["verdict"] = build_verdict(report)
	out_report = report if args.include_records else compact_report(report)
	out_path = Path(args.out_file)
	out_path.parent.mkdir(parents=True, exist_ok=True)
	out_path.write_text(json.dumps(out_report, indent=2), encoding="utf-8")

	print_concise_report(out_report)
	print(f"Saved: {out_path.resolve()}")


if __name__ == "__main__":
	main()

