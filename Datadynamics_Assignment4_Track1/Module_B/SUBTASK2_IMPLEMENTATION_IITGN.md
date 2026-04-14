# Assignment 4 - Subtask 2 (Data Partitioning on IITGN Shards)

## Environment used
- Host: `10.0.116.184`
- Shard ports:
  - Shard 0 -> `3307`
  - Shard 1 -> `3308`
  - Shard 2 -> `3309`
- Team user/db: `Data_Dynamics`

## Partitioning rule
- `shard_id = MOD(member_id, 3)`

## Table layout
- Reference tables replicated on every shard:
  - `Departments`, `Data_Categories`, `Roles`, `Role_Permissions`
- Partitioned tables written with shard-prefix naming:
  - `shard_0_members`, `shard_1_members`, `shard_2_members`
  - similarly for related tables:
    - `member_role_assignments`, `contact_details`, `locations`,
      `emergency_contacts`, `user_credentials`, `search_logs`, `audit_trail`

## Implementation files
- `callhub_backend/config.py`
- `callhub_backend/load_source_to_shard0.py`
- `callhub_backend/shard_migration_docker.py`

## Execution commands
Run from `Module_B/callhub_backend`:

1) Load source schema/data into shard 0 (seed source dataset):

```bash
python load_source_to_shard0.py --drop-existing
```

2) Partition into all 3 shards:

```bash
python shard_migration_docker.py \
  --source-host 10.0.116.184 \
  --source-port 3307 \
  --source-user Data_Dynamics \
  --source-password password@123 \
  --source-db Data_Dynamics \
  --shard-host 10.0.116.184 \
  --shard-ports 3307,3308,3309 \
  --team-user Data_Dynamics \
  --team-password password@123 \
  --team-db Data_Dynamics \
  --num-shards 3 \
  --reset-tables
```

## Verification guarantees
The migration script validates both:
- **No record loss:** source count equals sum of records across all shard tables.
- **No duplication:** primary keys do not appear on multiple shards.

Generated report path:
- `benchmarks/iitgn_shard_migration_report.json`
