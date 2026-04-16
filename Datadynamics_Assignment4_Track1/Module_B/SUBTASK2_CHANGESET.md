# Assignment 4 - Subtask 2 Changeset (IITGN Shard Infra)

This document captures the new Subtask 2 implementation using the instructor-provided shards.

## Deployment constraints
- Host: `10.0.116.184`
- MySQL shard ports: `3307`, `3308`, `3309`
- Team DB user: `Data_Dynamics`
- Team DB password: `password@123`
- Team DB name: `Data_Dynamics`

## Chosen sharding model
- Strategy: Hash-based sharding
- Shard key: `member_id`
- Formula: `shard_id = MOD(member_id, 3)`
- Naming convention: `shard_0_<table>`, `shard_1_<table>`, `shard_2_<table>`

## Files changed
- `callhub_backend/config.py`
  - Added shard host, ports, and team-DB credential defaults

- `callhub_backend/shard_migration_docker.py`
  - Reworked for IITGN-provided shards (no local Docker compose dependency)
  - Uses team credentials on each shard
  - Creates `shard_<id>_<table>` tables per shard
  - Migrates reference tables fully to each shard
  - Migrates partitioned tables by hash rule
  - Verifies count integrity and duplicate key absence
  - Writes report to `benchmarks/iitgn_shard_migration_report.json`

- `callhub_backend/load_source_to_shard0.py`
  - Loads baseline schema and seed data from `sql/tables_CallHub.sql`
  - Targets team DB on shard 0 (`10.0.116.184:3307`)
  - Skips `CREATE DATABASE` and `USE` SQL statements safely

- `docker-shards/README.md`
  - Replaced with instructions for external shard usage

## Runbook
From `Module_B/callhub_backend`:

```bash
python load_source_to_shard0.py --drop-existing

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

## Verification evidence
- Migration script prints `Verification status: OK` on success
- JSON artifact: `benchmarks/iitgn_shard_migration_report.json`

## Subtask 2 checklist mapping
- At least 3 shard nodes: Yes (ports `3307`, `3308`, `3309`)
- Data partitioning implemented: Yes (`MOD(member_id, 3)`)
- Correct subset per shard: Yes (exclusive predicate per shard)
- No loss or duplication validation: Yes (count + duplicate checks)
