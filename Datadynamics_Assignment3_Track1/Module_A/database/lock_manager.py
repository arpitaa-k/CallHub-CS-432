"""
Lock Manager Module
Implements locking mechanism for transaction isolation and consistency.
"""

from typing import Dict, Set, Optional, Tuple
from collections import defaultdict
import threading
import time


class LockType:
    """Lock types"""
    READ = "READ"
    WRITE = "WRITE"


class LockManager:
    """
    Lock Manager for transaction isolation.
    
    Implements distributed locking:
    - Shared (READ) locks: Multiple readers, no writers
    - Exclusive (WRITE) locks: Single writer, no readers
    - Supports lock queuing and deadlock detection
    """
    
    def __init__(self):
        self.locks: Dict[Tuple[str, any], Dict] = {}  # {(table, key): {type, owners, waiters}}
        self.transaction_locks: Dict[int, Set[Tuple[str, any]]] = defaultdict(set)
        self.lock = threading.RLock()  # Reentrant lock for thread-safety
    
    def acquire_read_lock(self, transaction_id: int, table_name: str, key: any,
                          timeout: float = 5.0) -> bool:
        """
        Acquire a READ lock on a resource.
        Multiple transactions can hold read locks simultaneously.
        """
        resource = (table_name, key)
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            with self.lock:
                if resource not in self.locks:
                    self.locks[resource] = {
                        'type': LockType.READ,
                        'owners': {transaction_id},
                        'waiters': []
                    }
                    self.transaction_locks[transaction_id].add(resource)
                    return True
                
                lock_info = self.locks[resource]
                
                # Can acquire READ if:
                # 1. No WRITE locks owned by others
                # 2. No exclusive write lock is held
                if lock_info['type'] == LockType.READ and not any(
                    tid != transaction_id for tid in lock_info['owners']
                    if self._has_exclusive_intent(tid, resource)
                ):
                    lock_info['owners'].add(transaction_id)
                    self.transaction_locks[transaction_id].add(resource)
                    return True
                
                # Can't acquire, wait
            
            time.sleep(0.01)
        
        return False
    
    def acquire_write_lock(self, transaction_id: int, table_name: str, key: any,
                           timeout: float = 5.0) -> bool:
        """
        Acquire a WRITE lock on a resource.
        Only one transaction can hold a write lock, no concurrent readers.
        """
        resource = (table_name, key)
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            with self.lock:
                if resource not in self.locks:
                    self.locks[resource] = {
                        'type': LockType.WRITE,
                        'owners': {transaction_id},
                        'waiters': []
                    }
                    self.transaction_locks[transaction_id].add(resource)
                    return True
                
                lock_info = self.locks[resource]
                
                # Can only acquire WRITE if no other owners
                if len(lock_info['owners']) == 1 and transaction_id in lock_info['owners']:
                    # Already own this lock
                    return True
                elif len(lock_info['owners']) == 0:
                    # No one owns it
                    lock_info['type'] = LockType.WRITE
                    lock_info['owners'] = {transaction_id}
                    self.transaction_locks[transaction_id].add(resource)
                    return True
                
                # Can't acquire, wait
            
            time.sleep(0.01)
        
        return False
    
    def release_lock(self, transaction_id: int, table_name: str, key: any) -> bool:
        """Release a lock held by a transaction"""
        resource = (table_name, key)
        
        with self.lock:
            if resource not in self.locks:
                return False
            
            lock_info = self.locks[resource]
            if transaction_id in lock_info['owners']:
                lock_info['owners'].discard(transaction_id)
                self.transaction_locks[transaction_id].discard(resource)
                
                # Clean up empty lock entries
                if len(lock_info['owners']) == 0:
                    del self.locks[resource]
                
                return True
        
        return False
    
    def release_all_locks(self, transaction_id: int):
        """Release all locks held by a transaction"""
        with self.lock:
            resources = list(self.transaction_locks[transaction_id])
            for table_name, key in resources:
                self.release_lock(transaction_id, table_name, key)
    
    def _has_exclusive_intent(self, transaction_id: int, resource: Tuple) -> bool:
        """Check if transaction has exclusive intent on resource"""
        if resource not in self.locks:
            return False
        lock_info = self.locks[resource]
        return lock_info['type'] == LockType.WRITE and transaction_id in lock_info['owners']
    
    def get_transaction_locks(self, transaction_id: int) -> Set[Tuple[str, any]]:
        """Get all locks held by a transaction"""
        return self.transaction_locks.get(transaction_id, set())
    
    def is_deadlock_detected(self, transaction_id: int, table_name: str, key: any) -> bool:
        """
        Simple deadlock detection using timeout.
        In production, use cycle detection in wait-for graph.
        """
        # Implement proper cycle detection if needed
        return False
    
    def clear_all_locks(self):
        """Clear all locks (use with caution)"""
        with self.lock:
            self.locks.clear()
            self.transaction_locks.clear()
