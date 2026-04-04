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
        self.wait_for_graph: Dict[int, Set[int]] = defaultdict(set)  # txn_id -> set of txns waiting for it
        self.waiting_for: Dict[int, Set[Tuple[str, any]]] = defaultdict(set)  # txn_id -> resources it's waiting for
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
                    # Remove from wait-for graph if it was waiting
                    self._remove_from_wait_graph(transaction_id, resource)
                    return True
                
                # Can't acquire, add to wait-for graph
                if transaction_id not in lock_info['waiters']:
                    lock_info['waiters'].append(transaction_id)
                    self.waiting_for[transaction_id].add(resource)
                    
                    # Build wait-for relationships: this txn waits for all current owners
                    for owner_id in lock_info['owners']:
                        if owner_id != transaction_id:
                            self.wait_for_graph[owner_id].add(transaction_id)
                    
                    # Check for deadlock
                    if self._detect_deadlock(transaction_id):
                        # Deadlock detected, abort this transaction
                        lock_info['waiters'].remove(transaction_id)
                        self.waiting_for[transaction_id].discard(resource)
                        self._remove_from_wait_graph(transaction_id, resource)
                        return False
            
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
                    # Remove from wait-for graph if it was waiting
                    self._remove_from_wait_graph(transaction_id, resource)
                    return True
                
                # Can't acquire, add to wait-for graph
                if transaction_id not in lock_info['waiters']:
                    lock_info['waiters'].append(transaction_id)
                    self.waiting_for[transaction_id].add(resource)
                    
                    # Build wait-for relationships: this txn waits for all current owners
                    for owner_id in lock_info['owners']:
                        if owner_id != transaction_id:
                            self.wait_for_graph[owner_id].add(transaction_id)
                    
                    # Check for deadlock
                    if self._detect_deadlock(transaction_id):
                        # Deadlock detected, abort this transaction
                        lock_info['waiters'].remove(transaction_id)
                        self.waiting_for[transaction_id].discard(resource)
                        self._remove_from_wait_graph(transaction_id, resource)
                        return False
            
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
        Check for deadlock using wait-for graph cycle detection.
        Returns True if deadlock detected, False otherwise.
        """
        return self._detect_deadlock(transaction_id)
    
    def _detect_deadlock(self, transaction_id: int) -> bool:
        """
        Detect deadlock using DFS cycle detection in wait-for graph.
        Returns True if deadlock found, False otherwise.
        """
        visited = set()
        rec_stack = set()
        
        def dfs(current_txn: int) -> bool:
            visited.add(current_txn)
            rec_stack.add(current_txn)
            
            # Check all transactions waiting for current_txn
            for waiting_txn in self.wait_for_graph.get(current_txn, set()):
                if waiting_txn not in visited:
                    if dfs(waiting_txn):
                        return True
                elif waiting_txn in rec_stack:
                    return True
            
            rec_stack.remove(current_txn)
            return False
        
        return dfs(transaction_id)
    
    def _remove_from_wait_graph(self, transaction_id: int, resource: Tuple[str, any]):
        """
        Remove transaction from wait-for graph when it acquires a lock.
        """
        # Remove this transaction from all wait-for relationships
        for txn_id in list(self.wait_for_graph.keys()):
            self.wait_for_graph[txn_id].discard(transaction_id)
            if not self.wait_for_graph[txn_id]:
                del self.wait_for_graph[txn_id]
        
        # Remove resources this transaction was waiting for
        self.waiting_for[transaction_id].discard(resource)
        if not self.waiting_for[transaction_id]:
            del self.waiting_for[transaction_id]
    
    def clear_all_locks(self):
        """Clear all locks (use with caution)"""
        with self.lock:
            self.locks.clear()
            self.transaction_locks.clear()
            self.wait_for_graph.clear()
            self.waiting_for.clear()
