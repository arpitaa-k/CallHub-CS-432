import argparse
import random
import re
from datetime import date, timedelta

import bcrypt
import mysql.connector
from faker import Faker

from config import MYSQL_DB, MYSQL_HOST, MYSQL_PASSWORD, MYSQL_USER


ADMIN_ROLES = {"Director", "Dean Academics", "Dean Student Welfare", "Registrar"}
ROLE_ORDER = [
    "HOD",
    "Professor",
    "Asst. Professor",
    "Student (UG)",
    "Student (PG/PhD)",
    "Warden",
    "Security Guard",
    "Medical Staff",
]

CONTACT_CATEGORY_PREFERENCE = ["Public", "Residential", "Academic", "Confidential", "Emergency"]
LOCATION_CATEGORY_PREFERENCE = ["Residential", "Public", "Academic", "Confidential", "Emergency"]
EMERGENCY_CATEGORY_PREFERENCE = ["Emergency", "Public", "Residential", "Academic", "Confidential"]

ACADEMIC_DEPT_CODES = {"CSE", "EE", "ME", "CE", "CHEM", "BIO", "PHY", "MATH"}
ROLE_DEPT_CODE_HINTS = {
    "HOD": ["PHY", "CSE", "EE", "ME", "BIO", "MATH"],
    "Professor": ["CSE", "EE", "ME", "CE", "CHEM", "BIO", "PHY", "MATH"],
    "Asst. Professor": ["CSE", "EE", "ME", "CE", "CHEM", "BIO", "PHY", "MATH"],
    "Student (UG)": ["CSE", "EE", "ME", "CE", "CHEM", "BIO", "PHY", "MATH"],
    "Student (PG/PhD)": ["CSE", "EE", "ME", "CE", "CHEM", "BIO", "PHY", "MATH"],
    "Warden": ["HSTL"],
    "Security Guard": ["SEC"],
    "Medical Staff": ["MED"],
}

ROLE_DESIGNATIONS = {
    "HOD": lambda code: f"HOD {code}",
    "Professor": lambda code: f"Professor {code}",
    "Asst. Professor": lambda code: f"Asst. Professor {code}",
    "Student (UG)": lambda code: f"BTech {code} Student",
    "Student (PG/PhD)": lambda code: f"PG {code} Scholar",
    "Warden": lambda code: "Warden",
    "Security Guard": lambda code: "Security Guard",
    "Medical Staff": lambda code: "Medical Staff",
}


def connect_db():
    return mysql.connector.connect(
        host=MYSQL_HOST,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DB,
        autocommit=False,
    )


def slugify(value):
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return value.strip("_")


def pick_category(category_map, allowed_names, preference_list):
    allowed = [name for name in preference_list if name in allowed_names]
    if allowed:
        return category_map[allowed[0]]
    return category_map[next(iter(allowed_names))]


def load_lookups(cur):
    cur.execute("SELECT dept_id, dept_code, dept_name FROM Departments")
    departments = cur.fetchall()
    dept_by_code = {row[1]: {"dept_id": row[0], "dept_code": row[1], "dept_name": row[2]} for row in departments}

    cur.execute("SELECT role_id, role_title FROM Roles")
    role_by_title = {row[1]: row[0] for row in cur.fetchall()}

    cur.execute("SELECT category_id, category_name FROM Data_Categories")
    category_by_name = {row[1]: row[0] for row in cur.fetchall()}

    cur.execute(
        """
        SELECT r.role_title, dc.category_name
        FROM Role_Permissions rp
        JOIN Roles r ON r.role_id = rp.role_id
        JOIN Data_Categories dc ON dc.category_id = rp.category_id
        WHERE rp.can_view = 1
        ORDER BY r.role_title, dc.category_id
        """
    )
    allowed_categories = {}
    for role_title, category_name in cur.fetchall():
        allowed_categories.setdefault(role_title, []).append(category_name)

    return dept_by_code, role_by_title, category_by_name, allowed_categories


def build_member_payload(fake, index, role_title, dept_by_code, category_by_name, allowed_categories):
    role_hint_codes = ROLE_DEPT_CODE_HINTS[role_title]
    chosen_code = random.choice(role_hint_codes)
    department = dept_by_code[chosen_code]

    full_name = fake.name()
    display_name = slugify(full_name)
    username = f"{display_name}_{index:03d}"
    password = f"CallHub@{index:03d}"
    gender = random.choice(["M", "F", "O"])
    age = random.randint(18, 62) if "Student" not in role_title else random.randint(18, 28)
    join_date = fake.date_between(start_date="-6y", end_date="today")
    assigned_date = join_date + timedelta(days=random.randint(0, 20))

    if role_title == "Student (UG)":
        year = random.choice(["1st Yr", "2nd Yr", "3rd Yr", "4th Yr"])
        designation = f"BTech {department['dept_code']} {year}"
        contact_type = "Mobile"
        contact_value = f"9{random.randint(100000000, 999999999)}"
        location_type = "Hostel Room"
        building_name = random.choice(["Himalaya Hostel", "Ganga Hostel", "Nilgiri Hostel"])
        room_number = f"H-{random.randint(100, 599)}"
    elif role_title == "Student (PG/PhD)":
        program = random.choice(["MTech", "PhD", "MS Research"])
        designation = f"{program} {department['dept_code']}"
        contact_type = "Mobile"
        contact_value = f"9{random.randint(100000000, 999999999)}"
        location_type = "Hostel Room"
        building_name = random.choice(["Married Scholar Apts", "Himalaya Hostel", "Ganga Hostel"])
        room_number = f"A-{random.randint(1, 99)}"
    elif role_title in {"HOD", "Professor", "Asst. Professor"}:
        designation = ROLE_DESIGNATIONS[role_title](department["dept_code"])
        contact_type = "Official Email"
        contact_value = f"{slugify(full_name)}@{department['dept_code'].lower()}.inst.ac.in"
        location_type = "Office"
        building_name = random.choice(["Ada Lovelace Block", "Tesla Hall", "Newton Block", "Ramanujan Building"])
        room_number = f"{department['dept_code']}-{random.randint(101, 499)}"
    elif role_title == "Warden":
        designation = "Warden"
        contact_type = random.choice(["Mobile", "Official Email", "Landline"])
        contact_value = f"9{random.randint(100000000, 999999999)}" if contact_type == "Mobile" else f"warden{index}@inst.ac.in"
        location_type = "Office"
        building_name = random.choice(["Himalaya Hostel", "Ganga Hostel"])
        room_number = "Warden Office"
    elif role_title == "Security Guard":
        designation = "Security Guard"
        contact_type = random.choice(["Landline", "Mobile"])
        contact_value = f"079-{random.randint(2000000, 9999999)}" if contact_type == "Landline" else f"9{random.randint(100000000, 999999999)}"
        location_type = "Post"
        building_name = "Main Gate Complex"
        room_number = f"Post-{random.randint(1, 5)}"
    else:
        designation = "Medical Staff"
        contact_type = random.choice(["Mobile", "Official Email", "Landline"])
        contact_value = f"9{random.randint(100000000, 999999999)}" if contact_type == "Mobile" else f"medical{index}@inst.ac.in"
        location_type = "Office"
        building_name = "Dhanvantari Medical Unit"
        room_number = random.choice(["OPD-1", "Nursing Stn", "Room-2"])

    emergency_name = fake.name()
    emergency_relation = random.choice(["Father", "Mother", "Brother", "Sister", "Spouse", "Guardian"])
    emergency_phone = f"9{random.randint(100000000, 999999999)}"

    contact_category_id = pick_category(category_by_name, allowed_categories[role_title], CONTACT_CATEGORY_PREFERENCE)
    location_category_id = pick_category(category_by_name, allowed_categories[role_title], LOCATION_CATEGORY_PREFERENCE)
    emergency_category_id = pick_category(category_by_name, allowed_categories[role_title], EMERGENCY_CATEGORY_PREFERENCE)

    return {
        "full_name": full_name,
        "designation": designation,
        "gender": gender,
        "age": age,
        "dept_id": department["dept_id"],
        "join_date": join_date,
        "assigned_date": assigned_date,
        "role_id": None,
        "role_title": role_title,
        "username": username,
        "password": password,
        "contacts": [
            {
                "contact_type": contact_type,
                "contact_value": contact_value,
                "category_id": contact_category_id,
            }
        ],
        "locations": [
            {
                "location_type": location_type,
                "building_name": building_name,
                "room_number": room_number,
                "category_id": location_category_id,
            }
        ],
        "emergency_contacts": [
            {
                "contact_person_name": emergency_name,
                "relation": emergency_relation,
                "emergency_phone": emergency_phone,
                "category_id": emergency_category_id,
            }
        ],
    }


def main():
    parser = argparse.ArgumentParser(description="Generate 200 additional members for Module B testing")
    parser.add_argument("--count", type=int, default=200, help="Number of members to generate")
    parser.add_argument("--password", default="CallHub@123", help="Plain password for generated users")
    args = parser.parse_args()

    fake = Faker()
    conn = connect_db()
    cur = conn.cursor()

    try:
        dept_by_code, role_by_title, category_by_name, allowed_categories = load_lookups(cur)

        eligible_roles = [role for role in ROLE_ORDER if role in role_by_title and role not in ADMIN_ROLES]
        if not eligible_roles:
            raise RuntimeError("No eligible roles found in Roles table")

        generated = 0
        for index in range(1, args.count + 1):
            role_title = eligible_roles[(index - 1) % len(eligible_roles)]
            payload = build_member_payload(fake, index, role_title, dept_by_code, category_by_name, allowed_categories)
            payload["password"] = args.password
            payload["role_id"] = role_by_title[role_title]

            cur.execute(
                """
                INSERT INTO Members (full_name, designation, age, gender, dept_id, join_date)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    payload["full_name"],
                    payload["designation"],
                    payload["age"],
                    payload["gender"],
                    payload["dept_id"],
                    payload["join_date"],
                ),
            )
            member_id = cur.lastrowid

            for contact in payload["contacts"]:
                cur.execute(
                    """
                    INSERT INTO Contact_Details (member_id, contact_type, contact_value, category_id, is_primary)
                    VALUES (%s, %s, %s, %s, 1)
                    """,
                    (member_id, contact["contact_type"], contact["contact_value"], contact["category_id"]),
                )

            for location in payload["locations"]:
                cur.execute(
                    """
                    INSERT INTO Locations (member_id, location_type, building_name, room_number, category_id)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (member_id, location["location_type"], location["building_name"], location["room_number"], location["category_id"]),
                )

            for emergency in payload["emergency_contacts"]:
                cur.execute(
                    """
                    INSERT INTO Emergency_Contacts (member_id, contact_person_name, relation, emergency_phone, category_id)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        member_id,
                        emergency["contact_person_name"],
                        emergency["relation"],
                        emergency["emergency_phone"],
                        emergency["category_id"],
                    ),
                )

            hashed_password = bcrypt.hashpw(payload["password"].encode(), bcrypt.gensalt()).decode()
            cur.execute(
                """
                INSERT INTO User_Credentials (member_id, username, password_hash)
                VALUES (%s, %s, %s)
                """,
                (member_id, payload["username"], hashed_password),
            )

            cur.execute(
                """
                INSERT INTO Member_Role_Assignments (member_id, role_id, assigned_date)
                VALUES (%s, %s, %s)
                """,
                (member_id, payload["role_id"], payload["assigned_date"]),
            )

            generated += 1

        conn.commit()
        print(f"Inserted {generated} members")
        print(f"Default password for generated users: {args.password}")
        print("Roles used: " + ", ".join(eligible_roles))

    except Exception as exc:
        conn.rollback()
        raise SystemExit(f"Seed generation failed: {exc}")
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()