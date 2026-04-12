"""
Write-Ahead Logging (WAL) Module
Implements persistent logging for transaction management and crash recovery.
"""

import json
import os
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class LogType(Enum):
    """Types of log entries"""
    BEGIN = "BEGIN"
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    COMMIT = "COMMIT"
    ABORT = "ABORT"


class LogEntry:
    """Represents a single log entry"""
    
    def __init__(self, log_id: int, transaction_id: int, log_type: LogType,
                 table_name: str, key: Any, old_value: Optional[Dict] = None,
                 new_value: Optional[Dict] = None, timestamp: Optional[str] = None):
        self.log_id = log_id
        self.transaction_id = transaction_id
        self.log_type = log_type
        self.table_name = table_name
        self.key = key
        self.old_value = old_value  # For UNDO
        self.new_value = new_value  # For REDO
        self.timestamp = timestamp or datetime.now().isoformat()
    
    def to_dict(self) -> Dict:
        """Convert log entry to dictionary for serialization"""
        return {
            'log_id': self.log_id,
            'transaction_id': self.transaction_id,
            'log_type': self.log_type.value,
            'table_name': self.table_name,
            'key': str(self.key),  # Convert key to string for JSON serialization
            'old_value': self.old_value,
            'new_value': self.new_value,
            'timestamp': self.timestamp
        }
    
    @staticmethod
    def from_dict(data: Dict) -> 'LogEntry':
        """Reconstruct log entry from dictionary"""
        return LogEntry(
            log_id=data['log_id'],
            transaction_id=data['transaction_id'],
            log_type=LogType(data['log_type']),
            table_name=data['table_name'],
            key=data['key'],
            old_value=data.get('old_value'),
            new_value=data.get('new_value'),
            timestamp=data.get('timestamp')
        )


class WriteAheadLogger:
    """
    Write-Ahead Logging implementation for ACID compliance.
    
    Ensures:
    - Durability: All changes are logged before being applied
    - Atomicity: Full transactions are logged before commit
    - Recovery: Can redo committed transactions or undo aborted ones
    """
    
    def __init__(self, log_dir: str = "logs"):
        self.log_dir = log_dir
        self.log_file = os.path.join(log_dir, "transaction.log")
        self.checkpoint_file = os.path.join(log_dir, "checkpoint.log")
        self.log_entries: List[LogEntry] = []
        self.log_id_counter = 0
        
        # Ensure logs directory exists
        os.makedirs(self.log_dir, exist_ok=True)
        
        # Load existing logs
        self._load_logs()
    
    def _load_logs(self):
        """Load existing logs from disk"""
        if os.path.exists(self.log_file):
            try:
                with open(self.log_file, 'r') as f:
                    for line in f:
                        if line.strip():
                            data = json.loads(line)
                            entry = LogEntry.from_dict(data)
                            self.log_entries.append(entry)
                            self.log_id_counter = max(self.log_id_counter, entry.log_id + 1)
            except Exception as e:
                print(f"Warning: Could not load logs: {e}")
    
    def log_begin(self, transaction_id: int) -> LogEntry:
        """Log the beginning of a transaction"""
        entry = LogEntry(
            log_id=self.log_id_counter,
            transaction_id=transaction_id,
            log_type=LogType.BEGIN,
            table_name="",
            key=None
        )
        self.log_id_counter += 1
        self._persist_entry(entry)
        self.log_entries.append(entry)
        return entry
    
    def log_insert(self, transaction_id: int, table_name: str, key: Any, new_value: Dict) -> LogEntry:
        """Log an insert operation"""
        entry = LogEntry(
            log_id=self.log_id_counter,
            transaction_id=transaction_id,
            log_type=LogType.INSERT,
            table_name=table_name,
            key=key,
            old_value=None,
            new_value=new_value
        )
        self.log_id_counter += 1
        self._persist_entry(entry)
        self.log_entries.append(entry)
        return entry
    
    def log_update(self, transaction_id: int, table_name: str, key: Any,
                   old_value: Dict, new_value: Dict) -> LogEntry:
        """Log an update operation"""
        entry = LogEntry(
            log_id=self.log_id_counter,
            transaction_id=transaction_id,
            log_type=LogType.UPDATE,
            table_name=table_name,
            key=key,
            old_value=old_value,
            new_value=new_value
        )
        self.log_id_counter += 1
        self._persist_entry(entry)
        self.log_entries.append(entry)
        return entry
    
    def log_delete(self, transaction_id: int, table_name: str, key: Any, old_value: Dict) -> LogEntry:
        """Log a delete operation"""
        entry = LogEntry(
            log_id=self.log_id_counter,
            transaction_id=transaction_id,
            log_type=LogType.DELETE,
            table_name=table_name,
            key=key,
            old_value=old_value,
            new_value=None
        )
        self.log_id_counter += 1
        self._persist_entry(entry)
        self.log_entries.append(entry)
        return entry
    
    def log_commit(self, transaction_id: int) -> LogEntry:
        """Log a commit operation"""
        entry = LogEntry(
            log_id=self.log_id_counter,
            transaction_id=transaction_id,
            log_type=LogType.COMMIT,
            table_name="",
            key=None
        )
        self.log_id_counter += 1
        self._persist_entry(entry)
        self.log_entries.append(entry)
        return entry
    
    def log_abort(self, transaction_id: int) -> LogEntry:
        """Log an abort/rollback operation"""
        entry = LogEntry(
            log_id=self.log_id_counter,
            transaction_id=transaction_id,
            log_type=LogType.ABORT,
            table_name="",
            key=None
        )
        self.log_id_counter += 1
        self._persist_entry(entry)
        self.log_entries.append(entry)
        return entry
    
    def _persist_entry(self, entry: LogEntry):
        """Write log entry to disk immediately (WAL guarantee)"""
        try:
            os.makedirs(self.log_dir, exist_ok=True)
            with open(self.log_file, 'a') as f:
                f.write(json.dumps(entry.to_dict()) + '\n')
                f.flush()
                os.fsync(f.fileno())  # Force write to disk
        except Exception as e:
            print(f"Error persisting log entry: {e}")
    
    def get_transaction_logs(self, transaction_id: int) -> List[LogEntry]:
        """Get all log entries for a specific transaction"""
        return [entry for entry in self.log_entries if entry.transaction_id == transaction_id]
    
    def get_logs_since(self, log_id: int) -> List[LogEntry]:
        """Get all log entries since a specific log ID (for recovery)"""
        return [entry for entry in self.log_entries if entry.log_id > log_id]
    
    def get_uncommitted_transactions(self) -> Dict[int, List[LogEntry]]:
        """Get all transactions that don't have COMMIT or ABORT logs"""
        committed_txns = set()
        aborted_txns = set()
        txn_logs = {}
        
        for entry in self.log_entries:
            if entry.transaction_id not in txn_logs:
                txn_logs[entry.transaction_id] = []
            txn_logs[entry.transaction_id].append(entry)
            
            if entry.log_type == LogType.COMMIT:
                committed_txns.add(entry.transaction_id)
            elif entry.log_type == LogType.ABORT:
                aborted_txns.add(entry.transaction_id)
        
        # Find uncommitted transactions
        uncommitted = {}
        for txn_id, logs in txn_logs.items():
            if txn_id not in committed_txns and txn_id not in aborted_txns:
                uncommitted[txn_id] = logs
        
        return uncommitted
    
    def write_checkpoint(self, last_log_id: int):
        """Write a checkpoint to facilitate faster recovery"""
        try:
            with open(self.checkpoint_file, 'w') as f:
                json.dump({'last_log_id': last_log_id}, f)
        except Exception as e:
            print(f"Error writing checkpoint: {e}")
    
    def read_checkpoint(self) -> int:
        """Read the last checkpoint"""
        if os.path.exists(self.checkpoint_file):
            try:
                with open(self.checkpoint_file, 'r') as f:
                    data = json.load(f)
                    return data.get('last_log_id', -1)
            except Exception as e:
                print(f"Error reading checkpoint: {e}")
        return -1
    
    def clear_logs(self):
        """Clear all log files (use with caution)"""
        if os.path.exists(self.log_file):
            os.remove(self.log_file)
        if os.path.exists(self.checkpoint_file):
            os.remove(self.checkpoint_file)
        self.log_entries.clear()
        self.log_id_counter = 0
