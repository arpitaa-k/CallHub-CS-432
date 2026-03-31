"""
ACID Test Suite for Module A
Comprehensive tests for Atomicity, Consistency, Isolation, and Durability
"""

import os
import sys
import time
import shutil
import threading
from db_manager import DatabaseManager
from transaction_manager import TransactionManager
from schema import initialize_module_a_schema, populate_sample_data


class AcidTestSuite:
    """Complete test suite for ACID properties"""
    
    def __init__(self, db_name: str = "Module_A1_Final"):
        self.db_name = db_name
        self.dm = DatabaseManager()
        self.txm = TransactionManager(self.dm)
        self.test_results = []
    
    def setup(self):
        """Setup test database"""
        print("\n" + "="*70)
        print("SETTING UP TEST ENVIRONMENT")
        print("="*70)
        
        # Clean previous logs (gracefully handle locked directories)
        if os.path.exists("logs"):
            try:
                shutil.rmtree("logs")
            except PermissionError:
                # Directory is locked, try removing files individually
                try:
                    for file in os.listdir("logs"):
                        file_path = os.path.join("logs", file)
                        if os.path.isfile(file_path):
                            os.remove(file_path)
                except:
                    pass  # Ignore errors if we can't clean up
        
        initialize_module_a_schema(self.dm, self.db_name)
        populate_sample_data(self.txm, self.db_name)
        
        print("\nSetup complete!")
    
    # ========== ATOMICITY TESTS ==========
    def test_atomicity_multi_table_commit(self):
        """Test Atomicity: All-or-nothing for multi-table transactions on COMMIT"""
        print("\n" + "-"*70)
        print("TEST: ATOMICITY - Multi-Table COMMIT")
        print("-"*70)
        
        # Start transaction
        txn_id = self.txm.begin_transaction()
        
        # Insert into 3 different tables
        success = True
        success &= self.txm.insert(txn_id, self.db_name, "Members", {
            'member_id': 100,
            'full_name': 'Test Member A',
            'designation': 'Test',
            'profile_image_url': 'default.png',
            'age': 25,
            'gender': 'M',
            'dept_id': 1,
            'join_date': '2026-03-31',
            'is_active': 1,
            'is_deleted': False,
            'deleted_at': None
        })
        
        success &= self.txm.insert(txn_id, self.db_name, "Contact_Details", {
            'contact_id': 200,
            'member_id': 100,
            'contact_type': 'Mobile',
            'contact_value': '9999999999',
            'category_id': 1,
            'is_primary': True
        })
        
        success &= self.txm.insert(txn_id, self.db_name, "Locations", {
            'location_id': 300,
            'member_id': 100,
            'location_type': 'Hostel Room',
            'building_name': 'Test Hostel',
            'room_number': '101',
            'category_id': 2
        })
        
        if success:
            # Commit all changes atomically
            result = self.txm.commit(txn_id, self.db_name)
            
            # Verify all records are inserted
            members_table = self.dm.get_table(self.db_name, "Members")
            contacts_table = self.dm.get_table(self.db_name, "Contact_Details")
            locations_table = self.dm.get_table(self.db_name, "Locations")
            
            member_exists = members_table.get(100) is not None
            contact_exists = contacts_table.get(200) is not None
            location_exists = locations_table.get(300) is not None
            
            test_passed = result and member_exists and contact_exists and location_exists
            
            self.record_result("Atomicity - Multi-Table COMMIT", test_passed,
                             f"All 3 tables committed: {test_passed}")
            return test_passed
        else:
            self.record_result("Atomicity - Multi-Table COMMIT", False, "Insert operations failed")
            return False
    
    def test_atomicity_multi_table_rollback(self):
        """Test Atomicity: All-or-nothing for multi-table transactions on ROLLBACK"""
        print("\n" + "-"*70)
        print("TEST: ATOMICITY - Multi-Table ROLLBACK")
        print("-"*70)
        
        # Start transaction
        txn_id = self.txm.begin_transaction()
        
        # Insert into 3 tables
        self.txm.insert(txn_id, self.db_name, "Members", {
            'member_id': 101,
            'full_name': 'Test Member B',
            'designation': 'Test',
            'profile_image_url': 'default.png',
            'age': 26,
            'gender': 'F',
            'dept_id': 1,
            'join_date': '2026-03-31',
            'is_active': 1,
            'is_deleted': False,
            'deleted_at': None
        })
        
        self.txm.insert(txn_id, self.db_name, "Contact_Details", {
            'contact_id': 201,
            'member_id': 101,
            'contact_type': 'Mobile',
            'contact_value': '9999999998',
            'category_id': 1,
            'is_primary': True
        })
        
        self.txm.insert(txn_id, self.db_name, "Locations", {
            'location_id': 301,
            'member_id': 101,
            'location_type': 'Hostel Room',
            'building_name': 'Test Hostel',
            'room_number': '102',
            'category_id': 2
        })
        
        # Rollback the transaction
        result = self.txm.rollback(txn_id, self.db_name)
        
        # Verify all records are rolled back
        members_table = self.dm.get_table(self.db_name, "Members")
        contacts_table = self.dm.get_table(self.db_name, "Contact_Details")
        locations_table = self.dm.get_table(self.db_name, "Locations")
        
        member_exists = members_table.get(101) is not None
        contact_exists = contacts_table.get(201) is not None
        location_exists = locations_table.get(301) is not None
        
        test_passed = result and not member_exists and not contact_exists and not location_exists
        
        self.record_result("Atomicity - Multi-Table ROLLBACK", test_passed,
                         f"All 3 tables rolled back: {test_passed}")
        return test_passed
    
    # ========== CONSISTENCY TESTS ==========
    def test_consistency_referential_integrity(self):
        """Test Consistency: Referential integrity is maintained"""
        print("\n" + "-"*70)
        print("TEST: CONSISTENCY - Referential Integrity")
        print("-"*70)
        
        # Transaction: Insert member and then role assignment
        txn_id = self.txm.begin_transaction()
        
        success = True
        success &= self.txm.insert(txn_id, self.db_name, "Members", {
            'member_id': 102,
            'full_name': 'Test Member C',
            'designation': 'Test',
            'profile_image_url': 'default.png',
            'age': 27,
            'gender': 'M',
            'dept_id': 1,
            'join_date': '2026-03-31',
            'is_active': 1,
            'is_deleted': False,
            'deleted_at': None
        })
        
        # Try to assign a role to newly inserted member
        success &= self.txm.insert(txn_id, self.db_name, "Member_Role_Assignments", {
            'assignment_id': 100,
            'member_id': 102,
            'role_id': 1,
            'assigned_date': '2026-03-31'
        })
        
        if success:
            result = self.txm.commit(txn_id, self.db_name)
            
            members_table = self.dm.get_table(self.db_name, "Members")
            assignments_table = self.dm.get_table(self.db_name, "Member_Role_Assignments")
            
            member = members_table.get(102)
            assignment = assignments_table.get(100)
            
            test_passed = result and member is not None and assignment is not None
            
            self.record_result("Consistency - Referential Integrity", test_passed,
                             f"Member and assignment both committed and consistent: {test_passed}")
            return test_passed
        else:
            self.record_result("Consistency - Referential Integrity", False, "Insert failed")
            return False
    
    def test_consistency_data_types(self):
        """Test Consistency: Data type constraints are enforced"""
        print("\n" + "-"*70)
        print("TEST: CONSISTENCY - Data Type Validation")
        print("-"*70)
        
        txn_id = self.txm.begin_transaction()
        
        # Try to insert with wrong data type
        result = self.txm.insert(txn_id, self.db_name, "Members", {
            'member_id': "not_an_int",  # Should be int
            'full_name': 'Test Member',
            'designation': 'Test',
            'profile_image_url': 'default.png',
            'age': 25,
            'gender': 'M',
            'dept_id': 1,
            'join_date': '2026-03-31',
            'is_active': 1,
            'is_deleted': False,
            'deleted_at': None
        })
        
        # Should fail validation
        test_passed = not result
        
        self.record_result("Consistency - Data Type Validation", test_passed,
                         f"Invalid data type rejected: {test_passed}")
        return test_passed
    
    # ========== ISOLATION TESTS ==========
    def test_isolation_concurrent_reads(self):
        """Test Isolation: Multiple concurrent readers don't block each other"""
        print("\n" + "-"*70)
        print("TEST: ISOLATION - Concurrent Reads")
        print("-"*70)
        
        results = []
        
        def read_operation(txn_id, thread_num):
            txm = TransactionManager(self.dm)
            table = self.dm.get_table(self.db_name, "Members")
            
            if table:
                # Try to acquire read lock and read
                if txm.lock_manager.acquire_read_lock(txn_id, "Members", 1):
                    record = table.get(1)
                    results.append(record is not None)
                    txm.lock_manager.release_lock(txn_id, "Members", 1)
        
        # Create multiple concurrent read transactions
        threads = []
        txn_ids = [self.txm.begin_transaction() for _ in range(3)]
        
        for i, txn_id in enumerate(txn_ids):
            t = threading.Thread(target=read_operation, args=(txn_id, i))
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        test_passed = all(results)
        self.record_result("Isolation - Concurrent Reads", test_passed,
                         f"All {len(results)} concurrent reads successful: {test_passed}")
        return test_passed
    
    def test_isolation_read_uncommitted_prevention(self):
        """Test Isolation: Cannot read uncommitted data (Dirty Read Prevention)"""
        print("\n" + "-"*70)
        print("TEST: ISOLATION - Dirty Read Prevention")
        print("-"*70)
        
        # Transaction 1: Update without commit
        txn1 = self.txm.begin_transaction()
        self.txm.insert(txn1, self.db_name, "Members", {
            'member_id': 103,
            'full_name': 'Test Member D',
            'designation': 'Test',
            'profile_image_url': 'default.png',
            'age': 28,
            'gender': 'F',
            'dept_id': 1,
            'join_date': '2026-03-31',
            'is_active': 1,
            'is_deleted': False,
            'deleted_at': None
        })
        
        # Transaction 2: Try to read the uncommitted data
        txn2 = self.txm.begin_transaction()  # returns int
        members_table = self.dm.get_table(self.db_name, "Members")
        
        # Try to read - should fail because txn1 has write lock
        read_locked = self.txm.lock_manager.acquire_read_lock(txn2, "Members", 103, timeout=1.0)
        test_passed = not read_locked  # Should not be able to read
        
        self.txm.rollback(txn1, self.db_name)
        self.txm.rollback(txn2, self.db_name)
        
        self.record_result("Isolation - Dirty Read Prevention", test_passed,
                         f"Uncommitted data not readable: {test_passed}")
        return test_passed
    
    # ========== DURABILITY TESTS ==========
    def test_durability_persistence_after_commit(self):
        """Test Durability: Data persists after commit"""
        print("\n" + "-"*70)
        print("TEST: DURABILITY - Persistence After Commit")
        print("-"*70)
        
        txn_id = self.txm.begin_transaction()
        
        self.txm.insert(txn_id, self.db_name, "Members", {
            'member_id': 104,
            'full_name': 'Test Member E',
            'designation': 'Test',
            'profile_image_url': 'default.png',
            'age': 29,
            'gender': 'M',
            'dept_id': 1,
            'join_date': '2026-03-31',
            'is_active': 1,
            'is_deleted': False,
            'deleted_at': None
        })
        
        result = self.txm.commit(txn_id, self.db_name)
        
        # Verify data is in log and can be recovered
        members_table = self.dm.get_table(self.db_name, "Members")
        member = members_table.get(104)
        
        test_passed = result and member is not None
        
        self.record_result("Durability - Persistence After Commit", test_passed,
                         f"Committed data persists: {test_passed}")
        return test_passed
    
    def test_durability_crash_recovery(self):
        """Test Durability: Committed data survives simulated crash"""
        print("\n" + "-"*70)
        print("TEST: DURABILITY - Crash Recovery")
        print("-"*70)
        
        # Insert data through transaction
        txn_id = self.txm.begin_transaction()
        
        self.txm.insert(txn_id, self.db_name, "Members", {
            'member_id': 105,
            'full_name': 'Test Member F',
            'designation': 'Test',
            'profile_image_url': 'default.png',
            'age': 30,
            'gender': 'F',
            'dept_id': 1,
            'join_date': '2026-03-31',
            'is_active': 1,
            'is_deleted': False,
            'deleted_at': None
        })
        
        self.txm.commit(txn_id, self.db_name)
        
        # Simulate crash: verify log contains commit entry
        committed_txns = self.txm.recovery_manager._get_committed_transactions()
        
        test_passed = txn_id in committed_txns
        
        self.record_result("Durability - Crash Recovery", test_passed,
                         f"Commit log entry persisted: {test_passed}")
        return test_passed
    
    # ========== RECOVERY SCENARIO TESTS ==========
    def test_recovery_undo_incomplete_transaction(self):
        """Test Recovery: Recover by undoing incomplete transactions"""
        print("\n" + "-"*70)
        print("TEST: RECOVERY - Undo Incomplete Transaction")
        print("-"*70)
        
        # Insert without committing (simulates crash)
        txn_id = self.txm.begin_transaction()
        
        self.txm.insert(txn_id, self.db_name, "Members", {
            'member_id': 106,
            'full_name': 'Test Member G',
            'designation': 'Test',
            'profile_image_url': 'default.png',
            'age': 31,
            'gender': 'M',
            'dept_id': 1,
            'join_date': '2026-03-31',
            'is_active': 1,
            'is_deleted': False,
            'deleted_at': None
        })
        
        # Record is in tree but not committed
        members_table = self.dm.get_table(self.db_name, "Members")
        member_in_tree = members_table.get(106) is not None
        
        # Now recover
        recovery_stats = self.txm.recover_from_crash(self.db_name)
        
        # After recovery, member should be gone
        member_after_recovery = members_table.get(106) is not None
        
        test_passed = member_in_tree and not member_after_recovery
        
        self.record_result("Recovery - Undo Incomplete Transaction", test_passed,
                         f"Incomplete transaction undone: {test_passed}")
        return test_passed
    
    def test_recovery_redo_committed_transaction(self):
        """Test Recovery: Recover by redoing committed transactions"""
        print("\n" + "-"*70)
        print("TEST: RECOVERY - Redo Committed Transaction")
        print("-"*70)
        
        txn_id = self.txm.begin_transaction()
        
        self.txm.insert(txn_id, self.db_name, "Members", {
            'member_id': 107,
            'full_name': 'Test Member H',
            'designation': 'Test',
            'profile_image_url': 'default.png',
            'age': 32,
            'gender': 'F',
            'dept_id': 1,
            'join_date': '2026-03-31',
            'is_active': 1,
            'is_deleted': False,
            'deleted_at': None
        })
        
        self.txm.commit(txn_id, self.db_name)
        
        # Get recovery status
        recovery_status = self.txm.recovery_manager.get_recovery_status()
        
        test_passed = recovery_status['committed_transactions'] > 0
        
        self.record_result("Recovery - Redo Committed Transaction", test_passed,
                         f"Committed transactions tracked: {test_passed}")
        return test_passed
    
    # ========== TEST RESULT MANAGEMENT ==========
    def record_result(self, test_name: str, passed: bool, message: str):
        """Record test result"""
        status = "[PASS]" if passed else "[FAIL]"
        print(f"\n{status}: {test_name}")
        print(f"  Message: {message}")
        self.test_results.append((test_name, passed, message))
    
    def run_all_tests(self):
        """Run complete test suite"""
        print("\n" + "="*70)
        print("RUNNING COMPLETE ACID TEST SUITE")
        print("="*70)
        
        # Atomicity tests
        self.test_atomicity_multi_table_commit()
        self.test_atomicity_multi_table_rollback()
        
        # Consistency tests
        self.test_consistency_referential_integrity()
        self.test_consistency_data_types()
        
        # Isolation tests
        self.test_isolation_concurrent_reads()
        self.test_isolation_read_uncommitted_prevention()
        
        # Durability tests
        self.test_durability_persistence_after_commit()
        self.test_durability_crash_recovery()
        
        # Recovery tests
        self.test_recovery_undo_incomplete_transaction()
        self.test_recovery_redo_committed_transaction()
        
        # Print summary
        self.print_summary()
    
    def print_summary(self):
        """Print test summary"""
        print("\n" + "="*70)
        print("TEST SUMMARY")
        print("="*70)
        
        passed = sum(1 for _, result, _ in self.test_results if result)
        total = len(self.test_results)
        
        print(f"\nTests Passed: {passed}/{total}")
        print(f"Success Rate: {100 * passed / total:.1f}%")
        
        print("\nDetailed Results:")
        for name, result, message in self.test_results:
            status = "[OK]" if result else "[FAIL]"
            print(f"  {status} {name}")
        
        print("\n" + "="*70)


if __name__ == "__main__":
    # Run test suite
    test_suite = AcidTestSuite()
    test_suite.setup()
    test_suite.run_all_tests()
