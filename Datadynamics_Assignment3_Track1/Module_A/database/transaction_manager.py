"""
Transaction Manager Module
Implements ACID transaction support with multi-table transactions and crash recovery.
"""

from typing import Dict, List, Set, Tuple, Any, Optional
from enum import Enum
from collections import defaultdict
from logger import WriteAheadLogger, LogType
from lock_manager import LockManager
from recovery_manager import RecoveryManager


class TransactionState(Enum):
    """Transaction states"""
    ACTIVE = "ACTIVE"
    COMMITTED = "COMMITTED"
    ABORTED = "ABORTED"


class Transaction:
    """Represents a single transaction"""
    
    def __init__(self, transaction_id: int):
        self.transaction_id = transaction_id
        self.state = TransactionState.ACTIVE
        self.operations: List[Dict] = []  # List of operations in this transaction
        self.affected_resources: Dict[Tuple[str, Any], str] = {}  # {(table, key): operation_type}
        self.touched_tables: Set[str] = set()
    
    def add_operation(self, operation_type: str, table_name: str, key: Any, 
                      old_value: Optional[Dict] = None, new_value: Optional[Dict] = None):
        """Record an operation in this transaction"""
        self.operations.append({
            'type': operation_type,
            'table': table_name,
            'key': key,
            'old_value': old_value,
            'new_value': new_value
        })
        self.affected_resources[(table_name, key)] = operation_type
        self.touched_tables.add(table_name)


class TransactionManager:
    """
    Transaction Manager for ACID compliance.
    
    Features:
    - Multi-table transaction support
    - Write-Ahead Logging (WAL) for durability
    - Locking mechanism for isolation
    - Crash recovery
    - Atomicity through two-phase commit
    """
    
    def __init__(self, database_manager, log_dir: str = "logs"):
        self.db_manager = database_manager
        self.logger = WriteAheadLogger(log_dir)
        self.lock_manager = LockManager()
        self.recovery_manager = RecoveryManager(self.logger, database_manager)
        
        # Active transactions
        self.transactions: Dict[int, Transaction] = {}
        self.transaction_id_counter = 1
        
        # Saved states for rollback
        self.transaction_states: Dict[int, Dict[str, Dict]] = defaultdict(dict)
    
    def begin_transaction(self) -> int:
        """
        Begin a new transaction and return its ID.
        
        Guarantees:
        - Isolation through locking
        - Atomicity through logging
        """
        txn_id = self.transaction_id_counter
        self.transaction_id_counter += 1
        
        txn = Transaction(txn_id)
        self.transactions[txn_id] = txn
        
        # Log transaction begin
        self.logger.log_begin(txn_id)
        
        print(f"[TXN {txn_id}] Transaction started")
        return txn_id
    
    def insert(self, transaction_id: int, database_name: str, table_name: str, record: Dict) -> bool:
        """
        Insert a record within a transaction.
        
        Returns:
            True if successful, False otherwise
        """
        if transaction_id not in self.transactions:
            print(f"[TXN {transaction_id}] ERROR: Transaction not found")
            return False
        
        txn = self.transactions[transaction_id]
        if txn.state != TransactionState.ACTIVE:
            print(f"[TXN {transaction_id}] ERROR: Transaction is not active")
            return False
        
        # Get table
        table = self.db_manager.get_table(database_name, table_name)
        if not table:
            print(f"[TXN {transaction_id}] ERROR: Table not found")
            return False
        
        # Get the key
        key = record.get(table.search_key)
        
        # Acquire write lock
        if not self.lock_manager.acquire_write_lock(transaction_id, table_name, key):
            print(f"[TXN {transaction_id}] ERROR: Could not acquire write lock on {table_name}")
            return False
        
        # Validate record
        if not table.validate_record(record):
            self.lock_manager.release_lock(transaction_id, table_name, key)
            return False
        
        # Check for duplicates
        if table.data.search(key) is not None:
            print(f"[TXN {transaction_id}] ERROR: Record with {table.search_key} '{key}' already exists")
            self.lock_manager.release_lock(transaction_id, table_name, key)
            return False
        
        # Save old state (for rollback)
        self.transaction_states[transaction_id][(table_name, key)] = None
        
        # Perform insert
        table.data.insert(key, record)
        
        # Log the operation
        self.logger.log_insert(transaction_id, table_name, key, record)
        
        # Track in transaction
        txn.add_operation('INSERT', table_name, key, None, record)
        
        print(f"[TXN {transaction_id}] INSERT into {table_name} (key={key})")
        return True
    
    def update(self, transaction_id: int, database_name: str, table_name: str,
               record_id: Any, new_record: Dict) -> bool:
        """
        Update a record within a transaction.
        
        Returns:
            True if successful, False otherwise
        """
        if transaction_id not in self.transactions:
            print(f"[TXN {transaction_id}] ERROR: Transaction not found")
            return False
        
        txn = self.transactions[transaction_id]
        if txn.state != TransactionState.ACTIVE:
            print(f"[TXN {transaction_id}] ERROR: Transaction is not active")
            return False
        
        # Get table
        table = self.db_manager.get_table(database_name, table_name)
        if not table:
            print(f"[TXN {transaction_id}] ERROR: Table not found")
            return False
        
        # Acquire write lock
        if not self.lock_manager.acquire_write_lock(transaction_id, table_name, record_id):
            print(f"[TXN {transaction_id}] ERROR: Could not acquire write lock on {table_name}")
            return False
        
        # Validate
        if not table.validate_record(new_record):
            self.lock_manager.release_lock(transaction_id, table_name, record_id)
            return False
        
        # Get old value
        old_record = table.data.search(record_id)
        if old_record is None:
            print(f"[TXN {transaction_id}] ERROR: Record with {table.search_key} '{record_id}' not found")
            self.lock_manager.release_lock(transaction_id, table_name, record_id)
            return False
        
        # Save old state
        if (table_name, record_id) not in self.transaction_states[transaction_id]:
            self.transaction_states[transaction_id][(table_name, record_id)] = old_record.copy()
        
        # Perform update
        table.data.update(record_id, new_record)
        
        # Log the operation
        self.logger.log_update(transaction_id, table_name, record_id, old_record, new_record)
        
        # Track in transaction
        txn.add_operation('UPDATE', table_name, record_id, old_record, new_record)
        
        print(f"[TXN {transaction_id}] UPDATE {table_name} (key={record_id})")
        return True
    
    def delete(self, transaction_id: int, database_name: str, table_name: str,
               record_id: Any) -> bool:
        """
        Delete a record within a transaction.
        
        Returns:
            True if successful, False otherwise
        """
        if transaction_id not in self.transactions:
            print(f"[TXN {transaction_id}] ERROR: Transaction not found")
            return False
        
        txn = self.transactions[transaction_id]
        if txn.state != TransactionState.ACTIVE:
            print(f"[TXN {transaction_id}] ERROR: Transaction is not active")
            return False
        
        # Get table
        table = self.db_manager.get_table(database_name, table_name)
        if not table:
            print(f"[TXN {transaction_id}] ERROR: Table not found")
            return False
        
        # Acquire write lock
        if not self.lock_manager.acquire_write_lock(transaction_id, table_name, record_id):
            print(f"[TXN {transaction_id}] ERROR: Could not acquire write lock on {table_name}")
            return False
        
        # Get old value
        old_record = table.data.search(record_id)
        if old_record is None:
            print(f"[TXN {transaction_id}] ERROR: Record with {table.search_key} '{record_id}' not found")
            self.lock_manager.release_lock(transaction_id, table_name, record_id)
            return False
        
        # Save old state
        if (table_name, record_id) not in self.transaction_states[transaction_id]:
            self.transaction_states[transaction_id][(table_name, record_id)] = old_record.copy()
        
        # Perform delete
        table.data.delete(record_id)
        
        # Log the operation
        self.logger.log_delete(transaction_id, table_name, record_id, old_record)
        
        # Track in transaction
        txn.add_operation('DELETE', table_name, record_id, old_record, None)
        
        print(f"[TXN {transaction_id}] DELETE from {table_name} (key={record_id})")
        return True
    
    def commit(self, transaction_id: int, database_name: str) -> bool:
        """
        Commit a transaction.
        
        Ensures:
        - Atomicity: All or nothing
        - Durability: Changes persist after commit
        
        Returns:
            True if commit successful, False otherwise
        """
        if transaction_id not in self.transactions:
            print(f"[TXN {transaction_id}] ERROR: Transaction not found")
            return False
        
        txn = self.transactions[transaction_id]
        if txn.state != TransactionState.ACTIVE:
            print(f"[TXN {transaction_id}] ERROR: Transaction is not active")
            return False
        
        try:
            # Phase 2: Write COMMIT log (atomicity point)
            self.logger.log_commit(transaction_id)
            
            # Mark as committed
            txn.state = TransactionState.COMMITTED
            
            # Release all locks
            self.lock_manager.release_all_locks(transaction_id)
            
            # Clean up transaction state
            if transaction_id in self.transaction_states:
                del self.transaction_states[transaction_id]
            
            print(f"[TXN {transaction_id}] COMMIT successful ({len(txn.operations)} operations)")
            print(f"  Affected tables: {', '.join(sorted(txn.touched_tables))}")
            
            return True
        
        except Exception as e:
            print(f"[TXN {transaction_id}] ERROR during commit: {e}")
            self.rollback(transaction_id, database_name)
            return False
    
    def rollback(self, transaction_id: int, database_name: str) -> bool:
        """
        Rollback a transaction.
        
        Ensures:
        - Atomicity: No partial updates visible
        - Consistency: Database remains in valid state
        
        Returns:
            True if rollback successful, False otherwise
        """
        if transaction_id not in self.transactions:
            print(f"[TXN {transaction_id}] ERROR: Transaction not found")
            return False
        
        txn = self.transactions[transaction_id]
        
        try:
            # Undo all operations in reverse order
            undone_count = 0
            for resource, old_value in reversed(list(self.transaction_states[transaction_id].items())):
                table_name, key = resource
                table = self.db_manager.get_table(database_name, table_name)
                
                if table:
                    if old_value is None:
                        # This was an INSERT, so delete it
                        if table.data.search(key) is not None:
                            table.data.delete(key)
                    else:
                        # This was UPDATE or DELETE, restore old value
                        if table.data.search(key) is not None:
                            table.data.update(key, old_value)
                        else:
                            table.data.insert(key, old_value)
                    
                    undone_count += 1
            
            # Log abort
            self.logger.log_abort(transaction_id)
            
            # Mark as aborted
            txn.state = TransactionState.ABORTED
            
            # Release all locks
            self.lock_manager.release_all_locks(transaction_id)
            
            # Clean up
            if transaction_id in self.transaction_states:
                del self.transaction_states[transaction_id]
            
            print(f"[TXN {transaction_id}] ROLLBACK successful ({undone_count} operations undone)")
            
            return True
        
        except Exception as e:
            print(f"[TXN {transaction_id}] ERROR during rollback: {e}")
            return False
    
    def get_transaction_status(self, transaction_id: int) -> Optional[Dict]:
        """Get status of a transaction"""
        if transaction_id not in self.transactions:
            return None
        
        txn = self.transactions[transaction_id]
        return {
            'transaction_id': transaction_id,
            'state': txn.state.value,
            'operations_count': len(txn.operations),
            'affected_tables': list(txn.touched_tables),
            'held_locks': list(self.lock_manager.get_transaction_locks(transaction_id))
        }
    
    def get_all_transactions(self) -> Dict[int, Dict]:
        """Get status of all transactions"""
        return {txn_id: self.get_transaction_status(txn_id) 
                for txn_id in self.transactions.keys()}
    
    def recover_from_crash(self, database_name: str) -> Dict:
        """Recover database from crash"""
        print(f"\n[RECOVERY] Starting crash recovery for '{database_name}'")
        return self.recovery_manager.recover_database(database_name)
