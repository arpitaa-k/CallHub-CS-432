"""
Module A: Advanced Transaction Engine & Crash Recovery
B+ Tree based database with ACID compliance
"""

from database.bplustree import BPlusTree, BPlusTreeNode
from database.table import Table
from database.db_manager import DatabaseManager
from database.transaction_manager import TransactionManager
from database.logger import WriteAheadLogger, LogEntry, LogType
from database.lock_manager import LockManager
from database.recovery_manager import RecoveryManager
from database.schema import initialize_module_a_schema, populate_sample_data

__version__ = "1.0.0"
__author__ = "Module A Implementation"

__all__ = [
    'BPlusTree',
    'BPlusTreeNode',
    'Table',
    'DatabaseManager',
    'TransactionManager',
    'WriteAheadLogger',
    'LogEntry',
    'LogType',
    'LockManager',
    'RecoveryManager',
    'initialize_module_a_schema',
    'populate_sample_data'
]
