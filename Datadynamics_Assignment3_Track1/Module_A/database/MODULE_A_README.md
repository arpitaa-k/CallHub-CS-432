# Module A: Advanced Transaction Engine & Crash Recovery

## Overview

Module A extends the B+ Tree-based mini-database system with comprehensive ACID transaction support, crash recovery, and multi-table consistency guarantees.

## Architecture

### Core Components

```
┌─────────────────────────────────────────────────────────────┐
│              Transaction Manager (Central)                  │
│  - Transaction lifecycle (BEGIN, COMMIT, ROLLBACK)         │
│  - Coordinates all ACID guarantees                          │
└─────────────────────────────────────────────────────────────┘
         │                        │                        │
         ▼                        ▼                        ▼
    ┌─────────────┐        ┌──────────────┐       ┌───────────────┐
    │   WAL       │        │    Lock      │       │   Recovery    │
    │             │        │   Manager    │       │   Manager     │
    │  Logging    │        │              │       │               │
    │  & Recovery │        │  Isolation   │       │  Undo/Redo    │
    │  Guarantees │        │              │       │  Protocols    │
    └─────────────┘        └──────────────┘       └───────────────┘
         │                        │                        │
         ▼                        ▼                        ▼
    ┌─────────────────────────────────────────────────────────┐
    │           Database Manager & B+ Tree Storage             │
    │                                                          │
    │  [Departments] [Members] [Roles] [Contact_Details]...   │
    └─────────────────────────────────────────────────────────┘
```

## Key Features

### 1. ACID Compliance

#### **Atomicity** ✓
- All-or-nothing transaction execution
- Multi-table transactions treated as single atomic unit
- Rollback capability for incomplete transactions
- Example: Student enrollment updating 5 tables atomically

#### **Consistency** ✓
- Data type validation at insert/update
- Referential integrity checks
- State machine enforcement (only valid state transitions)
- Example: Cannot assign role to non-existent member

#### **Isolation** ✓
- Lock-based concurrency control
- Two-phase locking (2PL)
- READ locks (shared) and WRITE locks (exclusive)
- Prevention of dirty reads and race conditions
- Example: Concurrent updates to same member are serialized

#### **Durability** ✓
- Write-Ahead Logging (WAL) before changes applied
- Log entries persisted to disk immediately
- Committed data survives crashes
- Example: After COMMIT, data persists even on system failure

### 2. Write-Ahead Logging (WAL)

```python
# Log Lifecycle:
BEGIN TXN
  ├─ INSERT (Member 1)        # Logged before applying
  ├─ UPDATE (Dept 1)          # Logged before applying
  ├─ DELETE (Contact 5)       # Logged before applying
  └─ COMMIT                   # Logged after all operations
     └─ Data now durable
```

**Key Log Entries:**
- `BEGIN`: Transaction start
- `INSERT`: New record with value
- `UPDATE`: Old value + new value
- `DELETE`: Record value
- `COMMIT`: Transaction committed
- `ABORT`: Transaction rolled back

### 3. Lock Management

```
SHARED (READ) LOCK
├─ Multiple transactions can hold
├─ Prevents concurrent writes
└─ Example: 3 readers can access member simultaneously

EXCLUSIVE (WRITE) LOCK
├─ Only 1 transaction can hold
├─ Blocks all other readers/writers
└─ Example: Update blocks all concurrent access
```

### 4. Crash Recovery

**Two-Phase Recovery:**

1. **Redo Phase**: Re-apply all committed transactions
   - Ensures durability of committed changes
   - Uses NEW values from logs

2. **Undo Phase**: Roll back uncommitted transactions
   - Prevents partial updates from surviving
   - Uses OLD values from logs

```
Recovery Flow:
  1. Read log entries
  2. Identify committed transactions
  3. REDO: Re-apply all operations in committed txns
  4. Identify uncommitted transactions
  5. UNDO: Remove all operations from uncommitted txns
  6. Database is now in consistent state
```

## File Structure

```
database/
├── __init__.py
├── bplustree.py            # B+ Tree implementation
├── table.py                # Table abstraction
├── db_manager.py           # Database manager
├── logger.py               # Write-Ahead Logger (NEW)
├── lock_manager.py         # Lock Management (NEW)
├── recovery_manager.py     # Crash Recovery (NEW)
├── transaction_manager.py  # Transaction Control (NEW)
├── schema.py               # Schema Definitions (NEW)
├── test_acid.py            # ACID Test Suite (NEW)
├── scenarios.py            # Real-World Scenarios (NEW)
├── test_bplustree.py       # Existing B+ Tree tests
└── performance_analyzer.py # Performance metrics
```

## Database Schema

### 12 Tables (Module A)

1. **Departments** - Organizational departments
2. **Data_Categories** - Information categories
3. **Roles** - User roles
4. **Role_Permissions** - Role-category permissions
5. **Members** - Core member data
6. **Member_Role_Assignments** - Member-role mappings
7. **Contact_Details** - Phone, email, etc.
8. **Locations** - Physical locations
9. **Emergency_Contacts** - Emergency contacts
10. **Search_Logs** - Search activity
11. **Audit_Trail** - Change audit log
12. **User_Credentials** - Login credentials

## Usage

### 1. Basic Transaction

```python
from database.transaction_manager import TransactionManager
from database.db_manager import DatabaseManager

dm = DatabaseManager()
txm = TransactionManager(dm)

# Initialize schema
from database.schema import initialize_module_a_schema
initialize_module_a_schema(dm, "Module_A")

# Use transaction
txn_id = txm.begin_transaction()

txm.insert(txn_id, "Module_A", "Members", {
    'member_id': 1,
    'full_name': 'John Doe',
    # ... other fields
})

txm.commit(txn_id, "Module_A")  # All changes durable
```

### 2. Multi-Table Transaction

```python
txn_id = txm.begin_transaction()

# All these happen atomically
txm.insert(txn_id, "Module_A", "Members", member_record)
txm.insert(txn_id, "Module_A", "Contact_Details", contact_record)
txm.insert(txn_id, "Module_A", "Locations", location_record)

result = txm.commit(txn_id, "Module_A")
# Either all 3 committed or all 3 rolled back
```

### 3. Rollback on Error

```python
txn_id = txm.begin_transaction()

success = txm.insert(txn_id, "Module_A", "Members", record1)
if not success:
    txm.rollback(txn_id, "Module_A")
    # No partial updates
```

### 4. Crash Recovery

```python
txm = TransactionManager(dm)

# Recover from crash
stats = txm.recover_from_crash("Module_A")
print(f"Redone: {stats['redone_txns']} transactions")
print(f"Undone: {stats['undone_txns']} transactions")
```

## Testing

### Run ACID Test Suite

```bash
python test_acid.py
```

Tests included:
- ✓ Atomicity: Multi-table COMMIT/ROLLBACK
- ✓ Consistency: Type validation, referential integrity
- ✓ Isolation: Concurrent reads, dirty read prevention
- ✓ Durability: Persistence, crash recovery
- ✓ Recovery: Undo incomplete, redo committed

### Run Real-World Scenarios

```bash
python scenarios.py
```

Scenarios included:
1. Student Enrollment (5-table atomic transaction)
2. Enrollment with Failure (atomicity verification)
3. Department Creation (consistency check)
4. Concurrent Updates (isolation testing)
5. Crash Simulation & Recovery (durability verification)

## Assignment 3 Validation

### Execution Steps
1. Open a terminal in `Datadynamics_Assignment3_Track1/Module_A/database`
2. Run `python test_acid.py`
3. Observe the summary output at the end to confirm all tests pass

### What is Checked
- Atomicity: multi-table transactions either fully commit or fully rollback
- Consistency: schema validation and referential integrity are enforced
- Isolation: shared read locks allow concurrent reads and prevent dirty reads
- Durability: commit logs persist and committed changes survive recovery
- Recovery: uncommitted transactions are undone, committed transactions are redone

### Expected Result
All ACID tests should pass with a success rate of `100%` after initializing the schema and sample data.

### Important Notes
- Logs are stored under `logs/transaction.log`
- Recovery uses the write-ahead log to restore committed state and undo incomplete transactions
- The B+ Tree remains consistent with table records during normal operations, rollback, and recovery

## Log File Format

1. Student Enrollment (5-table atomic transaction)
2. Enrollment with Failure (atomicity verification)
3. Department Creation (consistency check)
4. Concurrent Updates (isolation testing)
5. Crash Simulation & Recovery (durability verification)

## Performance Characteristics

| Operation | Complexity | Notes |
|-----------|-----------|-------|
| BEGIN | O(1) | Constant time |
| INSERT | O(log N) | B+ Tree insertion |
| UPDATE | O(log N) | B+ Tree search + update |
| DELETE | O(log N) | B+ Tree deletion |
| COMMIT | O(1) | Log write + metadata |
| ROLLBACK | O(M) | M = operations in txn |
| LOCK | O(1) | Hash table lookup |
| RECOVERY | O(L) | L = log entries |

## Log File Format

```json
{
  "log_id": 0,
  "transaction_id": 1,
  "log_type": "BEGIN",
  "table_name": "",
  "key": null,
  "old_value": null,
  "new_value": null,
  "timestamp": "2026-03-31T10:30:45.123456"
}

{
  "log_id": 1,
  "transaction_id": 1,
  "log_type": "INSERT",
  "table_name": "Members",
  "key": "1",
  "old_value": null,
  "new_value": {
    "member_id": 1,
    "full_name": "John Doe",
    ...
  },
  "timestamp": "2026-03-31T10:30:45.234567"
}

{
  "log_id": 2,
  "transaction_id": 1,
  "log_type": "COMMIT",
  "table_name": "",
  "key": null,
  "old_value": null,
  "new_value": null,
  "timestamp": "2026-03-31T10:30:45.345678"
}
```

## Key Implementation Details

### Write-Ahead Logging

1. **Before** applying operation: Write to log
2. Immediate fsync() to ensure durability
3. Log entry contains full undo/redo information
4. Transaction COMMIT is just a log entry

### Lock Manager

1. **Hash map** of resource -> lock info
2. **Lock info**: type (READ/WRITE), owners, waiters
3. **Timeout**: 5 seconds default per lock
4. **Release**: Automatic on COMMIT/ROLLBACK

### Recovery Manager

1. **Forward pass**: Redo all COMMIT entries
2. **Backward pass**: Undo uncommitted transactions (reverse order)

## Quick Reference

### Basic Transaction
```python
txn_id = txm.begin_transaction()
txm.insert(txn_id, "MyDB", "Members", {'member_id': 1, 'full_name': 'John'})
txm.commit(txn_id, "MyDB")
```

### Multi-Table Transaction (Atomic)
```python
txn_id = txm.begin_transaction()
txm.insert(txn_id, "MyDB", "Members", member_record)
txm.insert(txn_id, "MyDB", "Contact_Details", contact_record)
txm.insert(txn_id, "MyDB", "Locations", location_record)
txm.commit(txn_id, "MyDB")  # All 3 committed atomically
```

### Recovery from Crash
```python
recovery_stats = txm.recover_from_crash("MyDB")
print(f"Redone: {recovery_stats['redone_txns']} transactions")
print(f"Undone: {recovery_stats['undone_txns']} transactions")
```

## Deliverables Summary

### Files Created (9 new files)

1. **transaction_manager.py** - Central transaction coordinator (400+ lines)
2. **logger.py** - Write-Ahead Logging with durability (320+ lines)
3. **lock_manager.py** - Lock-based concurrency control (220+ lines)
4. **recovery_manager.py** - Crash recovery with redo/undo (240+ lines)
5. **schema.py** - 12-table database schema initialization (250+ lines)
6. **test_acid.py** - Comprehensive ACID test suite (450+ lines, 10 tests)
7. **scenarios.py** - Real-world transaction scenarios (500+ lines, 5 scenarios)
8. **quickstart.py** - Quick start tutorial and examples (300+ lines)
9. **MODULE_A_README.md** - Complete documentation (this file)

### Features Implemented

✅ **Multi-table ACID Transactions**: Atomicity across 3+ tables  
✅ **Crash Recovery**: Redo committed, undo uncommitted transactions  
✅ **Write-Ahead Logging**: Persisted transaction logs with fsync()  
✅ **Lock-based Isolation**: READ/WRITE locks with deadlock detection  
✅ **2PL Protocol**: Two-phase locking for serializability  
✅ **12 Database Tables**: Complete schema from assignment  
✅ **10 ACID Tests**: Comprehensive test coverage  
✅ **5 Real-world Scenarios**: Student enrollment, concurrent ops, recovery  
✅ **Referential Integrity**: Foreign key validation  
✅ **Data Type Validation**: Schema compliance enforcement  

## Key Implementation Details

### Write-Ahead Logging

1. **Before** applying operation: Write to log
2. Immediate fsync() to ensure durability
3. Log entry contains full undo/redo information
4. Transaction COMMIT is just a log entry

### Lock Manager

1. **Hash map** of resource -> lock info
2. **Lock info**: type (READ/WRITE), owners, waiters
3. **Timeout**: 5 seconds default per lock
4. **Release**: Automatic on COMMIT/ROLLBACK

### Recovery Manager

1. **Forward pass**: Redo all COMMIT entries
2. **Backward pass**: Undo uncommitted transactions (reverse order)
3. **Checkpoint**: Track recovery progress

### Transaction Manager

1. **Transaction object**: Tracks operations and state
2. **State machine**: ACTIVE → COMMITTED/ABORTED
3. **Atomicity**: All-or-nothing via single COMMIT log entry
4. **Isolation**: Via lock manager

## Constraints & Limitations

1. **No Partial Rollback**: Entire transaction rolls back or commits
2. **Single-Version**: No MVCC (multi-version concurrency control)
3. **In-Memory**: No persistence to disk (log only)
4. **Simple Locking**: No deadlock detection (timeouts used)
5. **No Optimization**: Every log entry written (no optimization)

## Future Enhancements

1. **MVCC**: Multiple versions for better concurrency
2. **Deadlock Detection**: Cycle detection in wait graph
3. **Savepoints**: Partial rollbacks
4. **Distributed Transactions**: Two-phase commit
5. **Query Optimization**: Smarter lock ordering
6. **Compression**: Log file compression

## Deadline

**6:00 PM, 5 April 2026**

---

**Module A Complete** ✓

- [x] Transaction BEGIN, COMMIT, ROLLBACK
- [x] Write-Ahead Logging
- [x] Crash Recovery (Redo/Undo)
- [x] Lock-Based Isolation
- [x] Multi-table ACID transactions
- [x] Comprehensive test suite
- [x] Real-world scenarios
- [x] Documentation
