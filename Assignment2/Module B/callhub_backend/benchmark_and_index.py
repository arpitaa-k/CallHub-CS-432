import os
import random
import string
import time
import requests
from faker import Faker
from dotenv import load_dotenv
import mysql.connector  # Use psycopg2 for PostgreSQL

# --- Load .env ---
load_dotenv()
DB_CONFIG = {
    'host': os.getenv('MYSQL_HOST'),
    'user': os.getenv('MYSQL_USER'),
    'password': os.getenv('MYSQL_PASSWORD'),
    'database': os.getenv('MYSQL_DB')
}
API_BASE_URL = "http://localhost:5000"  # Added back for API timing

# --- ENUMS and Reference Data ---
GENDERS = ['M', 'F', 'O']
CONTACT_TYPES = ['Mobile', 'Personal Email', 'Landline', 'Official Email']
LOCATION_TYPES = ['Office', 'Hostel Room', 'Lab', 'Residence', 'Post']
ACTION_TYPES = ['INSERT', 'UPDATE', 'DELETE', 'SOFT_DELETE']
RELATIONS = ['Father', 'Mother', 'Brother', 'Sister', 'Spouse', 'Husband', 'Wife']
DEPT_CODES = ['CSE', 'EE', 'ME', 'CE', 'CHEM', 'BIO', 'PHY', 'MATH', 'ADMIN', 'HSTL', 'MED', 'SEC', 'LIB', 'SPORT', 'MAINT']

fake = Faker()

def get_connection():
    return mysql.connector.connect(**DB_CONFIG)

def generate_departments(cur):
    # Only if table is empty
    cur.execute("SELECT COUNT(*) FROM Departments")
    if cur.fetchone()[0] == 0:
        # Insert your fixed department data here (see your schema)
        pass  # Already in your schema, skip for random

def generate_data_categories(cur):
    # Only if table is empty
    cur.execute("SELECT COUNT(*) FROM Data_Categories")
    if cur.fetchone()[0] == 0:
        # Insert your fixed categories here
        pass

def generate_roles(cur):
    # Only if table is empty
    cur.execute("SELECT COUNT(*) FROM Roles")
    if cur.fetchone()[0] == 0:
        # Insert your fixed roles here
        pass

def get_ids(cur, table, id_col):
    cur.execute(f"SELECT {id_col} FROM {table}")
    return [row[0] for row in cur.fetchall()]

def generate_members(cur, n=5000):
    dept_ids = get_ids(cur, "Departments", "dept_id")
    members = []
    # 1 HOD per dept
    for dept_id in dept_ids:
        name = fake.name()
        cur.execute(
            "INSERT INTO Members (full_name, designation, age, gender, dept_id, join_date) VALUES (%s, %s, %s, %s, %s, %s)",
            (name, f"HOD", random.randint(35, 65), random.choice(GENDERS), dept_id, fake.date_between(start_date='-10y', end_date='today'))
        )
        members.append((cur.lastrowid, dept_id, "HOD"))
    # 3 Professors per dept
    for dept_id in dept_ids:
        for _ in range(3):
            name = fake.name()
            cur.execute(
                "INSERT INTO Members (full_name, designation, age, gender, dept_id, join_date) VALUES (%s, %s, %s, %s, %s, %s)",
                (name, "Professor", random.randint(30, 65), random.choice(GENDERS), dept_id, fake.date_between(start_date='-10y', end_date='today'))
            )
            members.append((cur.lastrowid, dept_id, "Professor"))
    # 2 Staff per dept
    for dept_id in dept_ids:
        for _ in range(2):
            name = fake.name()
            cur.execute(
                "INSERT INTO Members (full_name, designation, age, gender, dept_id, join_date) VALUES (%s, %s, %s, %s, %s, %s)",
                (name, "Staff", random.randint(25, 60), random.choice(GENDERS), dept_id, fake.date_between(start_date='-10y', end_date='today'))
            )
            members.append((cur.lastrowid, dept_id, "Staff"))
    # 10 Students (UG) per dept
    for dept_id in dept_ids:
        for _ in range(10):
            name = fake.name()
            cur.execute(
                "INSERT INTO Members (full_name, designation, age, gender, dept_id, join_date) VALUES (%s, %s, %s, %s, %s, %s)",
                (name, "Student (UG)", random.randint(17, 25), random.choice(GENDERS), dept_id, fake.date_between(start_date='-6y', end_date='today'))
            )
            members.append((cur.lastrowid, dept_id, "Student (UG)"))
    # 5 Students (PG/PhD) per dept
    for dept_id in dept_ids:
        for _ in range(5):
            name = fake.name()
            cur.execute(
                "INSERT INTO Members (full_name, designation, age, gender, dept_id, join_date) VALUES (%s, %s, %s, %s, %s, %s)",
                (name, "Student (PG/PhD)", random.randint(22, 35), random.choice(GENDERS), dept_id, fake.date_between(start_date='-8y', end_date='today'))
            )
            members.append((cur.lastrowid, dept_id, "Student (PG/PhD)"))
    # Fill up to n with random staff
    while len(members) < n:
        dept_id = random.choice(dept_ids)
        name = fake.name()
        designation = random.choice(["Staff", "Lab Assistant", "Clerk", "Technician"])
        cur.execute(
            "INSERT INTO Members (full_name, designation, age, gender, dept_id, join_date) VALUES (%s, %s, %s, %s, %s, %s)",
            (name, designation, random.randint(22, 60), random.choice(GENDERS), dept_id, fake.date_between(start_date='-10y', end_date='today'))
        )
        members.append((cur.lastrowid, dept_id, designation))
    return members

def generate_member_roles(cur, members):
    cur.execute("SELECT role_id, role_title FROM Roles")
    role_map = {row[1]: row[0] for row in cur.fetchall()}
    for member_id, dept_id, designation in members:
        # Assign role based on designation
        if "HOD" in designation and "HOD" in role_map:
            cur.execute("INSERT INTO Member_Role_Assignments (member_id, role_id) VALUES (%s, %s)", (member_id, role_map["HOD"]))
        elif "Professor" in designation and "Professor" in role_map:
            cur.execute("INSERT INTO Member_Role_Assignments (member_id, role_id) VALUES (%s, %s)", (member_id, role_map["Professor"]))
        elif "Student (UG)" in designation and "Student (UG)" in role_map:
            cur.execute("INSERT INTO Member_Role_Assignments (member_id, role_id) VALUES (%s, %s)", (member_id, role_map["Student (UG)"]))
        elif "Student (PG/PhD)" in designation and "Student (PG/PhD)" in role_map:
            cur.execute("INSERT INTO Member_Role_Assignments (member_id, role_id) VALUES (%s, %s)", (member_id, role_map["Student (PG/PhD)"]))
        elif "Staff" in designation and "Medical Staff" in role_map:
            cur.execute("INSERT INTO Member_Role_Assignments (member_id, role_id) VALUES (%s, %s)", (member_id, role_map["Medical Staff"]))
        else:
            # Assign random role if nothing matches
            cur.execute("INSERT INTO Member_Role_Assignments (member_id, role_id) VALUES (%s, %s)", (member_id, random.choice(list(role_map.values()))))

def generate_contacts(cur, n=5000):
    member_ids = get_ids(cur, "Members", "member_id")
    cat_ids = get_ids(cur, "Data_Categories", "category_id")
    for _ in range(n):
        cur.execute(
            "INSERT INTO Contact_Details (member_id, contact_type, contact_value, category_id, is_primary) VALUES (%s, %s, %s, %s, %s)",
            (random.choice(member_ids), random.choice(CONTACT_TYPES), fake.email(), random.choice(cat_ids), random.choice([0, 1]))
        )

def generate_locations(cur, n=5000):
    member_ids = get_ids(cur, "Members", "member_id")
    cat_ids = get_ids(cur, "Data_Categories", "category_id")
    for _ in range(n):
        cur.execute(
            "INSERT INTO Locations (member_id, location_type, building_name, room_number, category_id) VALUES (%s, %s, %s, %s, %s)",
            (random.choice(member_ids), random.choice(LOCATION_TYPES), fake.company(), fake.building_number(), random.choice(cat_ids))
        )

def generate_emergency_contacts(cur, n=5000):
    member_ids = get_ids(cur, "Members", "member_id")
    cat_ids = get_ids(cur, "Data_Categories", "category_id")
    for _ in range(n):
        phone = fake.phone_number()[:20]  # Truncate to 20 chars
        cur.execute(
            "INSERT INTO Emergency_Contacts (member_id, contact_person_name, relation, emergency_phone, category_id) VALUES (%s, %s, %s, %s, %s)",
            (random.choice(member_ids), fake.name(), random.choice(RELATIONS), phone, random.choice(cat_ids))
        )

def generate_search_logs(cur, n=5000):
    member_ids = get_ids(cur, "Members", "member_id")
    for _ in range(n):
        cur.execute(
            "INSERT INTO Search_Logs (searched_term, searched_by_member_id, results_found_count) VALUES (%s, %s, %s)",
            (fake.word(), random.choice(member_ids), random.randint(0, 10))
        )

def generate_audit_trail(cur, n=5000):
    member_ids = get_ids(cur, "Members", "member_id")
    for _ in range(n):
        cur.execute(
            "INSERT INTO Audit_Trail (actor_id, target_table, target_record_id, action_type) VALUES (%s, %s, %s, %s)",
            (random.choice(member_ids), random.choice(['Members', 'Contact_Details', 'Locations']), random.randint(1, 10000), random.choice(ACTION_TYPES))
        )

def generate_all_data():
    conn = get_connection()
    cur = conn.cursor()
    print("Generating Members...")
    members = generate_members(cur, n=5000)
    print("Generating Member Roles...")
    generate_member_roles(cur, members)
    print("Generating Contacts...")
    generate_contacts(cur, n=5000)
    print("Generating Locations...")
    generate_locations(cur, n=5000)
    print("Generating Emergency Contacts...")
    generate_emergency_contacts(cur, n=5000)
    print("Generating Search Logs...")
    generate_search_logs(cur, n=5000)
    print("Generating Audit Trail...")
    generate_audit_trail(cur, n=5000)
    conn.commit()
    cur.close()
    conn.close()
    print("Data generation complete.")

def time_api_endpoints():
    endpoints = [
        "/members", "/members/1", "/portfolio/1", "/login"
        # Add all your endpoints here
    ]
    print("\n--- API Response Times ---")
    times = []
    for ep in endpoints:
        url = API_BASE_URL + ep
        start = time.time()
        try:
            r = requests.get(url)
            elapsed = time.time() - start
            print(f"{ep}: {elapsed:.3f}s (status {r.status_code})")
            times.append((ep, elapsed))
        except Exception as e:
            print(f"{ep}: ERROR {e}")
            times.append((ep, float('inf')))
    slowest = max(times, key=lambda x: x[1])
    print(f"\nSlowest endpoint: {slowest[0]} ({slowest[1]:.3f}s)")
    return times

def profile_queries():
    conn = get_connection()
    cur = conn.cursor()
    # Real queries from your API routes (based on member_routes.py and portfolio_routes.py)
    queries = [
        ("SELECT member_id, full_name, designation, age, gender, dept_id, join_date, is_active FROM Members WHERE member_id = 1 AND is_deleted = 0", "Portfolio: Get member info"),
        ("SELECT DISTINCT rp.category_id FROM Member_Role_Assignments mra JOIN Role_Permissions rp ON mra.role_id = rp.role_id WHERE mra.member_id = 1 AND rp.can_view = 1", "Portfolio: Get allowed categories"),
        ("SELECT can_edit_others FROM Roles WHERE role_title = 'Professor'", "Members: Check edit permission"),
        ("SELECT role_id, role_title FROM Roles ORDER BY role_title", "Members: Get editable roles"),
        ("SELECT * FROM Members WHERE full_name LIKE '%John%'", "Members: Search by name"),
        ("SELECT * FROM Members WHERE designation = 'Registrar'", "Members: Filter by designation"),
    ]
    print("\n--- SQL Query Profiling (EXPLAIN and Execution Time) ---")
    for query, desc in queries:
        print(f"\nQuery ({desc}): {query}")
        # EXPLAIN
        cur.execute(f"EXPLAIN {query}")
        explain_rows = cur.fetchall()
        for row in explain_rows:
            print(row)
        # Execution time
        start = time.time()
        cur.execute(query)
        results = cur.fetchall()
        elapsed = time.time() - start
        print(f"Execution Time: {elapsed:.4f}s (Rows returned: {len(results)})")
    cur.close()
    conn.close()

def apply_indexes():
    conn = get_connection()
    cur = conn.cursor()
    print("\n--- Applying Indexes ---")
    index_queries = [
        "CREATE INDEX idx_members_member_id ON Members(member_id)",
        "CREATE INDEX idx_members_full_name ON Members(full_name)",
        "CREATE INDEX idx_members_designation ON Members(designation)",
        "CREATE INDEX idx_members_is_deleted ON Members(is_deleted)",
        "CREATE INDEX idx_roles_role_title ON Roles(role_title)",
        "CREATE INDEX idx_mra_member_id ON Member_Role_Assignments(member_id)",
        "CREATE INDEX idx_rp_role_id ON Role_Permissions(role_id)",
        "CREATE INDEX idx_rp_category_id ON Role_Permissions(category_id)",
    ]
    for index_sql in index_queries:
        try:
            cur.execute(index_sql)
            print(f"Created: {index_sql}")
        except mysql.connector.errors.ProgrammingError as e:
            if "Duplicate key name" not in str(e):
                raise
            else:
                print(f"Index already exists: {index_sql}")
    conn.commit()
    cur.close()
    conn.close()
    print("Indexes applied.")

def main():
    # 1. Generate random data
    generate_all_data()

    # 2. Record API response times and profile queries BEFORE indexing
    time_api_endpoints()
    profile_queries()

    # 3. Apply indexes
    apply_indexes()

    # 4. Record API response times and profile queries AFTER indexing
    time_api_endpoints()
    profile_queries()

if __name__ == "__main__":
    main()