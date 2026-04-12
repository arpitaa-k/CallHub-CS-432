"""
Database Schema Definition
Initializes all tables for Module A with proper data types and constraints.
"""

from db_manager import DatabaseManager


def initialize_module_a_schema(dm: DatabaseManager, db_name: str = "Module_A1_Final"):
    """
    Initialize the complete database schema for Module A.
    Creates all 12 tables with proper schemas and relationships.
    """
    
    # Create database
    dm.create_database(db_name)
    print(f"\n[SCHEMA] Creating database '{db_name}'")
    
    # 1. Departments Table
    dm.create_table(
        db_name, "Departments",
        {
            'dept_id': int,
            'dept_code': str,
            'dept_name': str,
            'building_location': str,
            'is_academic': bool
        },
        search_key='dept_id'
    )
    
    # 2. Data_Categories Table
    dm.create_table(
        db_name, "Data_Categories",
        {
            'category_id': int,
            'category_name': str
        },
        search_key='category_id'
    )
    
    # 3. Roles Table
    dm.create_table(
        db_name, "Roles",
        {
            'role_id': int,
            'role_title': str,
            'can_edit_others': bool,
            'can_view_logs': bool
        },
        search_key='role_id'
    )
    
    # 4. Role_Permissions Table
    dm.create_table(
        db_name, "Role_Permissions",
        {
            'permission_id': int,
            'role_id': int,
            'category_id': int,
            'can_view': bool
        },
        search_key='permission_id'
    )
    
    # 5. Members Table (CORE)
    dm.create_table(
        db_name, "Members",
        {
            'member_id': int,
            'full_name': str,
            'designation': str,
            'profile_image_url': str,
            'age': int,
            'gender': str,
            'dept_id': int,
            'join_date': str,
            'is_active': int,
            'is_deleted': bool,
            'deleted_at': (str, type(None))  # Allow None for soft-deleted records
        },
        search_key='member_id'
    )
    
    # 6. Member_Role_Assignments Table
    dm.create_table(
        db_name, "Member_Role_Assignments",
        {
            'assignment_id': int,
            'member_id': int,
            'role_id': int,
            'assigned_date': str
        },
        search_key='assignment_id'
    )
    
    # 7. Contact_Details Table
    dm.create_table(
        db_name, "Contact_Details",
        {
            'contact_id': int,
            'member_id': int,
            'contact_type': str,
            'contact_value': str,
            'category_id': int,
            'is_primary': bool
        },
        search_key='contact_id'
    )
    
    # 8. Locations Table
    dm.create_table(
        db_name, "Locations",
        {
            'location_id': int,
            'member_id': int,
            'location_type': str,
            'building_name': str,
            'room_number': str,
            'category_id': int
        },
        search_key='location_id'
    )
    
    # 9. Emergency_Contacts Table
    dm.create_table(
        db_name, "Emergency_Contacts",
        {
            'record_id': int,
            'member_id': int,
            'contact_person_name': str,
            'relation': str,
            'emergency_phone': str,
            'category_id': int
        },
        search_key='record_id'
    )
    
    # 10. Search_Logs Table
    dm.create_table(
        db_name, "Search_Logs",
        {
            'log_id': int,
            'searched_term': str,
            'searched_by_member_id': int,
            'results_found_count': int,
            'search_timestamp': str
        },
        search_key='log_id'
    )
    
    # 11. Audit_Trail Table
    dm.create_table(
        db_name, "Audit_Trail",
        {
            'audit_id': int,
            'actor_id': int,
            'target_table': str,
            'target_record_id': int,
            'action_type': str,
            'action_timestamp': str
        },
        search_key='audit_id'
    )
    
    # 12. User_Credentials Table
    dm.create_table(
        db_name, "User_Credentials",
        {
            'user_id': int,
            'member_id': int,
            'username': str,
            'password_hash': str
        },
        search_key='user_id'
    )
    
    print(f"[SCHEMA] Successfully created 12 tables in '{db_name}'\n")
    return True


def populate_sample_data(txm, db_name: str):
    """
    Populate sample data from the SQL schema.
    Creates multi-relation transactions to demonstrate ACID properties.
    """
    print(f"\n[DATA] Populating sample data in '{db_name}'")
    
    # Transaction 1: Insert Department
    txn_id = txm.begin_transaction()
    txm.insert(txn_id, db_name, "Departments", {
        'dept_id': 1,
        'dept_code': 'CSE',
        'dept_name': 'Computer Science & Engg',
        'building_location': 'Ada Lovelace Block',
        'is_academic': True
    })
    
    txm.insert(txn_id, db_name, "Data_Categories", {
        'category_id': 1,
        'category_name': 'Public'
    })
    
    txm.insert(txn_id, db_name, "Data_Categories", {
        'category_id': 2,
        'category_name': 'Residential'
    })
    
    txm.insert(txn_id, db_name, "Data_Categories", {
        'category_id': 5,
        'category_name': 'Emergency'
    })
    
    txm.insert(txn_id, db_name, "Roles", {
        'role_id': 1,
        'role_title': 'Director',
        'can_edit_others': True,
        'can_view_logs': True
    })
    
    txm.insert(txn_id, db_name, "Roles", {
        'role_id': 8,
        'role_title': 'Student',
        'can_edit_others': False,
        'can_view_logs': False
    })
    
    txm.commit(txn_id, db_name)
    
    # Transaction 2: Insert Member
    txn_id = txm.begin_transaction()
    txm.insert(txn_id, db_name, "Members", {
        'member_id': 1,
        'full_name': 'Prof. Arvind Mishra',
        'designation': 'Director',
        'profile_image_url': 'default_avatar.png',
        'age': 58,
        'gender': 'M',
        'dept_id': 1,
        'join_date': '2020-01-15',
        'is_active': 1,
        'is_deleted': False,
        'deleted_at': None
    })
    
    txm.insert(txn_id, db_name, "Member_Role_Assignments", {
        'assignment_id': 1,
        'member_id': 1,
        'role_id': 1,
        'assigned_date': '2020-01-15'
    })
    
    txm.commit(txn_id, db_name)
    
    print("[DATA] Sample data population complete")


# SQL INSERT statements converted to Python records for reference
DEPARTMENTS_DATA = [
    {'dept_id': 1, 'dept_code': 'CSE', 'dept_name': 'Computer Science & Engg', 'building_location': 'Ada Lovelace Block', 'is_academic': True},
    {'dept_id': 2, 'dept_code': 'EE', 'dept_name': 'Electrical Engineering', 'building_location': 'Tesla Hall', 'is_academic': True},
    {'dept_id': 3, 'dept_code': 'ME', 'dept_name': 'Mechanical Engineering', 'building_location': 'Visvesvaraya Workshop', 'is_academic': True},
    {'dept_id': 4, 'dept_code': 'CE', 'dept_name': 'Civil Engineering', 'building_location': 'Ramanujan Building', 'is_academic': True},
]

DATA_CATEGORIES_DATA = [
    {'category_id': 1, 'category_name': 'Public'},
    {'category_id': 2, 'category_name': 'Residential'},
    {'category_id': 3, 'category_name': 'Academic'},
    {'category_id': 4, 'category_name': 'Confidential'},
    {'category_id': 5, 'category_name': 'Emergency'},
]

ROLES_DATA = [
    {'role_id': 1, 'role_title': 'Director', 'can_edit_others': True, 'can_view_logs': True},
    {'role_id': 2, 'role_title': 'Dean Academics', 'can_edit_others': True, 'can_view_logs': True},
    {'role_id': 3, 'role_title': 'Dean Student Welfare', 'can_edit_others': True, 'can_view_logs': True},
    {'role_id': 4, 'role_title': 'Registrar', 'can_edit_others': True, 'can_view_logs': True},
]
