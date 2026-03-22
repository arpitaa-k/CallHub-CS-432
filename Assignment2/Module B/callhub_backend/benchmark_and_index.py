import time
import requests
import json
import random
import os
from faker import Faker
from datetime import datetime
from config import *
import mysql.connector

API_BASE_URL = "http://127.0.0.1:5000"
SAVE_DIR = os.path.join("..", "benchmarks")
fake = Faker()

if not os.path.exists(SAVE_DIR):
    os.makedirs(SAVE_DIR)

def get_connection():
    return mysql.connector.connect(
        host=MYSQL_HOST,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DB
    )

def drop_indexes():
    conn = get_connection()
    cur = conn.cursor()
    print("Dropping indexes for clean state...")
    to_drop = [
        ("Members", "idx_members_name"),
        ("Members", "idx_members_lookup"),
        ("Member_Role_Assignments", "idx_mra_comp"),
        ("Role_Permissions", "idx_rp_comp")
    ]
    for table, idx in to_drop:
        try:
            cur.execute(f"ALTER TABLE {table} DROP INDEX {idx}")
        except:
            pass
    conn.commit()
    cur.close()
    conn.close()

def generate_all_data(count=5000):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT dept_id FROM Departments")
    dept_ids = [row[0] for row in cur.fetchall()]
    
    if not dept_ids:
        print("Error: Departments table empty")
        return

    print(f"Generating {count} members...")
    designations = ["Professor", "Staff", "Student (UG)", "Student (PG/PhD)", "Registrar"]
    member_data = []
    for _ in range(count):
        member_data.append((
            fake.name(), random.choice(designations), random.randint(19, 65),
            random.choice(['M', 'F', 'O']), random.choice(dept_ids), 
            fake.date_between(start_date='-10y', end_date='today')
        ))

    cur.executemany(
        "INSERT INTO Members (full_name, designation, age, gender, dept_id, join_date) VALUES (%s, %s, %s, %s, %s, %s)",
        member_data
    )
    conn.commit()
    cur.close()
    conn.close()

def time_api_endpoints(session=None):
    if session is None:
        session = requests.Session()
        login_payload = {"username": "Prof. Arvind Mishra", "password": "arvind"}
        session.post(f"{API_BASE_URL}/login", json=login_payload)

    endpoints = [
        ("/keepalive", "POST", {}),
        ("/check-admin", "GET", None),
        ("/members/search?name=a", "GET", None),
        ("/members", "GET", None),
        ("/members/1", "GET", None),
        ("/editable-roles", "GET", None),
        ("/member/1/portfolio", "GET", None)
    ]
    
    results = []
    for ep, method, payload in endpoints:
        start = time.time()
        if method == "POST":
            r = session.post(API_BASE_URL + ep, json=payload)
        else:
            r = session.get(API_BASE_URL + ep)
        elapsed = time.time() - start
        results.append({'endpoint': ep, 'time': elapsed, 'status': r.status_code})
    
    return results

def profile_queries():
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    queries = [
        ("SELECT * FROM Members WHERE full_name LIKE 'A%'", "Name Search"),
        ("SELECT * FROM Members WHERE designation = 'Professor' AND is_deleted = 0", "Designation Filter"),
        ("""SELECT DISTINCT rp.category_id FROM Member_Role_Assignments mra 
            JOIN Role_Permissions rp ON mra.role_id = rp.role_id 
            WHERE mra.member_id = 1 AND rp.can_view = 1""", "Privacy Engine Join")
    ]
    
    results = []
    for sql, desc in queries:
        cur.execute(f"EXPLAIN {sql}")
        explain = cur.fetchall()
        start = time.time()
        cur.execute(sql)
        cur.fetchall()
        elapsed = time.time() - start
        results.append({'desc': desc, 'query': sql, 'time': elapsed, 'explain': explain})
    
    cur.close()
    conn.close()
    return results

def apply_indexes():
    conn = get_connection()
    cur = conn.cursor()
    print("Applying Indexes...")
    index_sql = [
        "CREATE INDEX idx_members_name ON Members(full_name)",
        "CREATE INDEX idx_members_lookup ON Members(designation, is_deleted)",
        "CREATE INDEX idx_mra_comp ON Member_Role_Assignments(member_id, role_id)",
        "CREATE INDEX idx_rp_comp ON Role_Permissions(role_id, can_view)"
    ]
    for sql in index_sql:
        try:
            cur.execute(sql)
        except:
            pass
    conn.commit()
    cur.close()
    conn.close()

def print_slowest(data, title):
    print(f"\nSlowest {title}")
    sorted_data = sorted(data, key=lambda x: x.get('time', 0), reverse=True)
    for item in sorted_data[:3]:
        name = item.get('endpoint') or item.get('desc')
        print(f"{name}: {item['time']:.4f}s")

def main():
    drop_indexes()
    generate_all_data(5000)

    print("\nWarming up database cache for accurate comparison...")
    for _ in range(3):
        time_api_endpoints()
        profile_queries()

    print("\nSTAGE 1: BEFORE INDEXING (WARM CACHE)")
    session = requests.Session()
    session.post(f"{API_BASE_URL}/login", json={"username": "Prof. Arvind Mishra", "password": "arvind"})
    
    api_bef = time_api_endpoints(session)
    prof_bef = profile_queries()
    
    print_slowest(api_bef, "API Endpoints")
    print_slowest(prof_bef, "SQL Queries")

    with open(os.path.join(SAVE_DIR, "api_times_before.json"), "w") as f:
        json.dump(api_bef, f, indent=4, default=str)
    with open(os.path.join(SAVE_DIR, "benchmark_profile_before.json"), "w") as f:
        json.dump(prof_bef, f, indent=4, default=str)

    apply_indexes()

    print("\nSTAGE 2: AFTER INDEXING")
    api_aft = time_api_endpoints(session)
    prof_aft = profile_queries()
    
    print_slowest(api_aft, "API Endpoints")
    print_slowest(prof_aft, "SQL Queries")

    with open(os.path.join(SAVE_DIR, "api_times_after.json"), "w") as f:
        json.dump(api_aft, f, indent=4, default=str)
    with open(os.path.join(SAVE_DIR, "benchmark_profile_after.json"), "w") as f:
        json.dump(prof_aft, f, indent=4, default=str)

    print(f"\nBenchmark complete. Files saved in {SAVE_DIR}")

if __name__ == "__main__":
    main()