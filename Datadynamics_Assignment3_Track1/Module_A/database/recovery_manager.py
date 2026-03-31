"""
Recovery Manager Module
Implements crash recovery and transaction undo/redo functionality.
"""

from typing import Dict, List, Set, Tuple, Any, Optional
from logger import WriteAheadLogger, LogType, LogEntry


class RecoveryManager:
    """
    Recovery Manager for crash recovery and consistency.
    
    Implements:
    - Redo: Re-apply committed operations after crash
    - Undo: Rollback incomplete transactions
    - Recovery protocols following standard DBMS recovery algorithms
    """
    
    def __init__(self, logger: WriteAheadLogger, database_manager):
        self.logger = logger
        self.db_manager = database_manager
    
    def recover_database(self, database_name: str) -> Dict[str, Any]:
        """
        Perform full database recovery after a crash.
        
        Returns:
            Dict with recovery statistics
        """
        stats = {
            'redone_txns': 0,
            'undone_txns': 0,
            'redone_operations': 0,
            'undone_operations': 0,
            'recovered_txns': []
        }
        
        # Phase 1: Redo all committed transactions
        committed_txns = self._get_committed_transactions()
        for txn_id in committed_txns:
            stats['redone_operations'] += self._redo_transaction(txn_id, database_name)
            stats['redone_txns'] += 1
            stats['recovered_txns'].append((txn_id, 'REDONE'))
        
        # Phase 2: Undo all uncommitted transactions
        uncommitted_txns = self.logger.get_uncommitted_transactions()
        for txn_id in uncommitted_txns.keys():
            stats['undone_operations'] += self._undo_transaction(txn_id, database_name)
            stats['undone_txns'] += 1
            stats['recovered_txns'].append((txn_id, 'UNDONE'))
        
        print(f"\n[RECOVERY] Database recovery completed for '{database_name}'")
        print(f"  - Transactions redone: {stats['redone_txns']}")
        print(f"  - Transactions undone: {stats['undone_txns']}")
        print(f"  - Operations redone: {stats['redone_operations']}")
        print(f"  - Operations undone: {stats['undone_operations']}")
        
        return stats
    
    def _get_committed_transactions(self) -> Set[int]:
        """Get all committed transactions from logs"""
        committed = set()
        for entry in self.logger.log_entries:
            if entry.log_type == LogType.COMMIT:
                committed.add(entry.transaction_id)
        return committed
    
    def _redo_transaction(self, transaction_id: int, database_name: str) -> int:
        """
        Redo all operations of a committed transaction.
        Returns the number of operations redone.
        """
        operations = 0
        logs = self.logger.get_transaction_logs(transaction_id)
        
        for entry in logs:
            if entry.log_type == LogType.BEGIN:
                continue
            elif entry.log_type == LogType.COMMIT:
                break
            elif entry.log_type == LogType.INSERT:
                self._redo_insert(database_name, entry)
                operations += 1
            elif entry.log_type == LogType.UPDATE:
                self._redo_update(database_name, entry)
                operations += 1
            elif entry.log_type == LogType.DELETE:
                self._redo_delete(database_name, entry)
                operations += 1
        
        return operations
    
    def _undo_transaction(self, transaction_id: int, database_name: str) -> int:
        """
        Undo all operations of an uncommitted transaction (in reverse order).
        Returns the number of operations undone.
        """
        operations = 0
        logs = self.logger.get_transaction_logs(transaction_id)
        
        # Process logs in reverse order for undo
        for entry in reversed(logs):
            if entry.log_type == LogType.BEGIN:
                continue
            elif entry.log_type == LogType.INSERT:
                # Undo INSERT by deleting
                self._undo_insert(database_name, entry)
                operations += 1
            elif entry.log_type == LogType.UPDATE:
                # Undo UPDATE by restoring old value
                self._undo_update(database_name, entry)
                operations += 1
            elif entry.log_type == LogType.DELETE:
                # Undo DELETE by re-inserting
                self._undo_delete(database_name, entry)
                operations += 1
        
        return operations
    
    def _redo_insert(self, database_name: str, entry: LogEntry):
        """Redo an INSERT operation"""
        try:
            table = self.db_manager.get_table(database_name, entry.table_name)
            if table and entry.new_value:
                # Parse key from entry
                key = self._parse_key(entry.key)
                
                # Check if record already exists (may be partially inserted)
                if table.data.search(key) is None:
                    table.data.insert(key, entry.new_value)
        except Exception as e:
            print(f"[RECOVERY ERROR] Failed to redo INSERT on {entry.table_name}: {e}")
    
    def _redo_update(self, database_name: str, entry: LogEntry):
        """Redo an UPDATE operation"""
        try:
            table = self.db_manager.get_table(database_name, entry.table_name)
            if table and entry.new_value:
                key = self._parse_key(entry.key)
                table.data.update(key, entry.new_value)
        except Exception as e:
            print(f"[RECOVERY ERROR] Failed to redo UPDATE on {entry.table_name}: {e}")
    
    def _redo_delete(self, database_name: str, entry: LogEntry):
        """Redo a DELETE operation"""
        try:
            table = self.db_manager.get_table(database_name, entry.table_name)
            if table:
                key = self._parse_key(entry.key)
                table.data.delete(key)
        except Exception as e:
            print(f"[RECOVERY ERROR] Failed to redo DELETE on {entry.table_name}: {e}")
    
    def _undo_insert(self, database_name: str, entry: LogEntry):
        """Undo an INSERT by deleting the record"""
        try:
            table = self.db_manager.get_table(database_name, entry.table_name)
            if table:
                key = self._parse_key(entry.key)
                if table.data.search(key) is not None:
                    table.data.delete(key)
        except Exception as e:
            print(f"[RECOVERY ERROR] Failed to undo INSERT on {entry.table_name}: {e}")
    
    def _undo_update(self, database_name: str, entry: LogEntry):
        """Undo an UPDATE by restoring the old value"""
        try:
            table = self.db_manager.get_table(database_name, entry.table_name)
            if table and entry.old_value:
                key = self._parse_key(entry.key)
                table.data.update(key, entry.old_value)
        except Exception as e:
            print(f"[RECOVERY ERROR] Failed to undo UPDATE on {entry.table_name}: {e}")
    
    def _undo_delete(self, database_name: str, entry: LogEntry):
        """Undo a DELETE by re-inserting the record"""
        try:
            table = self.db_manager.get_table(database_name, entry.table_name)
            if table and entry.old_value:
                key = self._parse_key(entry.key)
                # Only reinsert if it doesn't exist
                if table.data.search(key) is None:
                    table.data.insert(key, entry.old_value)
        except Exception as e:
            print(f"[RECOVERY ERROR] Failed to undo DELETE on {entry.table_name}: {e}")
    
    def _parse_key(self, key_str: str) -> Any:
        """
        Parse key string back to appropriate type.
        Try to convert to int if possible, otherwise keep as string.
        """
        try:
            return int(key_str)
        except (ValueError, TypeError):
            return key_str
    
    def get_recovery_status(self) -> Dict[str, Any]:
        """Get current recovery status"""
        uncommitted = self.logger.get_uncommitted_transactions()
        committed_count = len(self._get_committed_transactions())
        
        return {
            'uncommitted_transactions': len(uncommitted),
            'committed_transactions': committed_count,
            'total_log_entries': len(self.logger.log_entries),
            'uncommitted_txns': list(uncommitted.keys())
        }
