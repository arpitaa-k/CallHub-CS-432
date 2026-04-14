# External Shard Infra Notes (Assignment 4)

Subtask 2 now uses instructor-provided shard instances instead of a local `docker compose` setup.

## Provided shard endpoints
- Host: `10.0.116.184`
- Shard 0 port: `3307`
- Shard 1 port: `3308`
- Shard 2 port: `3309`

## Team credentials
- Username: `Data_Dynamics`
- Password: `password@123`
- Database: `Data_Dynamics`

## Migration entrypoint
Use the script in `callhub_backend/shard_migration_docker.py`.


PowerShell example (Windows):

```powershell
python shard_migration_docker.py `
  --source-host 10.0.116.184 `
  --source-port 3307 `
  --source-user Data_Dynamics `
  --source-password password@123 `
  --source-db Data_Dynamics `
  --shard-host 10.0.116.184 `
  --shard-ports 3307,3308,3309 `
  --team-user Data_Dynamics `
  --team-password password@123 `
  --team-db Data_Dynamics `
  --num-shards 3 `
  --reset-tables
```

Why these two options matter:
- `--num-shards 3`: explicitly tells the script to route with 3 shards.
- `--reset-tables`: drops and recreates `shard_*` tables before loading, so reruns stay clean and do not duplicate data.

The script creates and loads tables with naming pattern:
- `shard_0_members`
- `shard_1_members`
- `shard_2_members`

and writes verification output to:
- `benchmarks/iitgn_shard_migration_report.json`
