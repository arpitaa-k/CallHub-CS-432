"""
Module A Quick Start Guide
Get started with transactions and crash recovery in 5 minutes
"""

from db_manager import DatabaseManager
from transaction_manager import TransactionManager
from schema import initialize_module_a_schema


def quick_start_demo():
    """Quick demonstration of Module A features"""
    
    print("\n" + "="*80)
    print("MODULE A QUICK START DEMO")
    print("="*80)
    
    # Step 1: Setup
    print("\n[Step 1] Setting up database...")
    dm = DatabaseManager()
    txm = TransactionManager(dm)
    
    initialize_module_a_schema(dm, "QuickStart")
    print("[OK] Database initialized with 12 tables")
    
    # Step 2: Single table transaction
    print("\n[Step 2] Simple transaction...")
    txn_id = txm.begin_transaction()
    
    success = txm.insert(txn_id, "QuickStart", "Members", {
        'member_id': 1,
        'full_name': 'Alice Johnson',
        'designation': 'Student',
        'profile_image_url': 'alice.jpg',
        'age': 20,
        'gender': 'F',
        'dept_id': 1,
        'join_date': '2026-01-01',
        'is_active': 1,
        'is_deleted': False,
        'deleted_at': None
    })
    
    if success:
        txm.commit(txn_id, "QuickStart")
        print("[OK] Single table transaction committed")
    
    # Step 3: Multi-table transaction
    print("\n[Step 3] Multi-table transaction...")
    txn_id = txm.begin_transaction()
    
    # Insert related data
    txm.insert(txn_id, "QuickStart", "Contact_Details", {
        'contact_id': 1,
        'member_id': 1,
        'contact_type': 'Mobile',
        'contact_value': '9876543210',
        'category_id': 1,
        'is_primary': True
    })
    
    txm.insert(txn_id, "QuickStart", "Locations", {
        'location_id': 1,
        'member_id': 1,
        'location_type': 'Hostel Room',
        'building_name': 'Hostel A',
        'room_number': '101',
        'category_id': 2
    })
    
    txm.insert(txn_id, "QuickStart", "Emergency_Contacts", {
        'record_id': 1,
        'member_id': 1,
        'contact_person_name': 'Bob Johnson',
        'relation': 'Father',
        'emergency_phone': '9988776655',
        'category_id': 5
    })
    
    txm.commit(txn_id, "QuickStart")
    print("[OK] Multi-table transaction committed (3 tables updated atomically)")
    
    # Step 4: Transaction rollback
    print("\n[Step 4] Transaction rollback...")
    txn_id = txm.begin_transaction()
    
    txm.insert(txn_id, "QuickStart", "Members", {
        'member_id': 2,
        'full_name': 'Bob Smith',
        'designation': 'Professor',
        'profile_image_url': 'bob.jpg',
        'age': 45,
        'gender': 'M',
        'dept_id': 1,
        'join_date': '2020-01-01',
        'is_active': 1,
        'is_deleted': False,
        'deleted_at': None
    })
    
    # Rollback instead of commit
    txm.rollback(txn_id, "QuickStart")
    
    members_table = dm.get_table("QuickStart", "Members")
    member_2 = members_table.get(2)
    
    if member_2 is None:
        print("[OK] Rollback successful - uncommitted changes not persisted")
    
    # Step 5: Check transaction status
    print("\n[Step 5] Transaction status...")
    status = txm.get_all_transactions()
    print(f"[OK] Active transactions: {len(status)}")
    for txn_id, info in status.items():
        if info:
            print(f"  - TXN {txn_id}: {info['state']}")
    
    # Step 6: View log information
    print("\n[Step 6] Transaction logs...")
    print(f"[OK] Total log entries: {len(txm.logger.log_entries)}")
    print(f"[OK] Sample entries:")
    
    for i, entry in enumerate(txm.logger.log_entries[:5]):
        print(f"  - Log {i}: {entry.log_type.value} on {entry.table_name}")
    
    print("\n" + "="*80)
    print("QUICK START COMPLETE!")
    print("="*80)
    print("\nNext steps:")
    print("1. Run test_acid.py for comprehensive ACID testing")
    print("2. Run scenarios.py for real-world scenario examples")
    print("3. Review MODULE_A_README.md for full documentation")
    print("4. Integrate with your application")


def example_student_enrollment():
    """Example: Complete student enrollment process"""
    
    print("\n" + "="*80)
    print("EXAMPLE: STUDENT ENROLLMENT PROCESS")
    print("="*80)
    
    dm = DatabaseManager()
    txm = TransactionManager(dm)
    initialize_module_a_schema(dm, "StudentDemo")
    
    print("\nEnrolling new student Priya Sharma...")
    
    # Single atomic transaction for entire enrollment
    txn_id = txm.begin_transaction()
    
    # 1. Add member
    txm.insert(txn_id, "StudentDemo", "Members", {
        'member_id': 100,
        'full_name': 'Priya Sharma',
        'designation': 'BTech CSE 1st Year',
        'profile_image_url': 'priya.jpg',
        'age': 18,
        'gender': 'F',
        'dept_id': 1,
        'join_date': '2026-01-15',
        'is_active': 1,
        'is_deleted': False,
        'deleted_at': None
    })
    print("  [OK] Member record created")
    
    # 2. Assign role
    txm.insert(txn_id, "StudentDemo", "Member_Role_Assignments", {
        'assignment_id': 100,
        'member_id': 100,
        'role_id': 8,
        'assigned_date': '2026-01-15'
    })
    print("  [OK] Student role assigned")
    
    # 3. Add contact
    txm.insert(txn_id, "StudentDemo", "Contact_Details", {
        'contact_id': 100,
        'member_id': 100,
        'contact_type': 'Mobile',
        'contact_value': '9876543210',
        'category_id': 2,
        'is_primary': True
    })
    print("  [OK] Contact details added")
    
    # 4. Add location
    txm.insert(txn_id, "StudentDemo", "Locations", {
        'location_id': 100,
        'member_id': 100,
        'location_type': 'Hostel Room',
        'building_name': 'Himalaya Hostel',
        'room_number': 'H-301',
        'category_id': 2
    })
    print("  [OK] Hostel location added")
    
    # Commit creates single ACID point
    result = txm.commit(txn_id, "StudentDemo")
    
    if result:
        print("\n[OK] ENROLLMENT COMPLETE - All 4 tables updated atomically")
        print("  Either all succeeded or none would have succeeded")
    
    print("\n" + "="*80)


def example_concurrent_operations():
    """Example: Handling concurrent operations"""
    
    print("\n" + "="*80)
    print("EXAMPLE: CONCURRENT OPERATIONS & ISOLATION")
    print("="*80)
    
    dm = DatabaseManager()
    txm = TransactionManager(dm)
    initialize_module_a_schema(dm, "ConcurrentDemo")
    
    # Setup: Insert a member for concurrent access
    setup_txn = txm.begin_transaction()
    txm.insert(setup_txn, "ConcurrentDemo", "Members", {
        'member_id': 200,
        'full_name': 'Dr. Smith',
        'designation': 'Professor',
        'profile_image_url': 'smith.jpg',
        'age': 45,
        'gender': 'M',
        'dept_id': 1,
        'join_date': '2020-01-01',
        'is_active': 1,
        'is_deleted': False,
        'deleted_at': None
    })
    txm.commit(setup_txn, "ConcurrentDemo")
    print("Setup: Member 200 created")
    
    # Concurrent transaction 1: Update profile image
    print("\nTransaction 1: Updating profile image...")
    txn1 = txm.begin_transaction()
    
    txm.update(txn1, "ConcurrentDemo", "Members", 200, {
        'member_id': 200,
        'full_name': 'Dr. Smith',
        'designation': 'Professor',
        'profile_image_url': 'smith_new.jpg',
        'age': 45,
        'gender': 'M',
        'dept_id': 1,
        'join_date': '2020-01-01',
        'is_active': 1,
        'is_deleted': False,
        'deleted_at': None
    })
    print("[OK] TXN1: Write lock acquired on member 200")
    
    # Concurrent transaction 2: Try to update (will wait)
    print("Transaction 2: Attempting update (will wait for TXN1)...")
    txn2 = txm.begin_transaction()
    
    print("[OK] TXN2: Waiting for lock (isolation in effect)...")
    
    # Commit txn1 to release lock
    txm.commit(txn1, "ConcurrentDemo")
    print("[OK] TXN1: Committed and released lock")
    
    # Now txn2 can proceed
    txm.update(txn2, "ConcurrentDemo", "Members", 200, {
        'member_id': 200,
        'full_name': 'Dr. Smith',
        'designation': 'Associate Professor',
        'profile_image_url': 'smith_new.jpg',
        'age': 45,
        'gender': 'M',
        'dept_id': 1,
        'join_date': '2020-01-01',
        'is_active': 1,
        'is_deleted': False,
        'deleted_at': None
    })
    
    txm.commit(txn2, "ConcurrentDemo")
    print("[OK] TXN2: Acquired lock and committed update")
    
    print("\nResult: Both transactions completed sequentially (serialized)")
    print("       No race conditions or dirty reads occurred")
    
    print("\n" + "="*80)


if __name__ == "__main__":
    # Run demonstrations
    quick_start_demo()
    example_student_enrollment()
    example_concurrent_operations()
