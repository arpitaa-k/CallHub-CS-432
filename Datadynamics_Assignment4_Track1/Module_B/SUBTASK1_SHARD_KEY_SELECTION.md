# Assignment 4 - Subtask 1 (Shard Key Selection and Justification)

## 1) Selected shard key
- **Shard key:** `member_id`

## 2) Why this key fits the required criteria
- **High cardinality:** `member_id` is unique and auto-incrementing in `Members`, so values distribute well.
- **Query aligned:** Existing APIs frequently query with `member_id` in CRUD and portfolio flows.
- **Stable:** `member_id` never changes after insertion.

## 3) Partitioning strategy chosen
- **Strategy:** Hash-based sharding
- **Rule:** `shard_id = MOD(member_id, 3)`

### Why hash-based suits this project
- Gives near-even distribution for growing member data.
- Avoids manual range maintenance.
- Matches point-lookup access patterns (`/members/<id>`, member portfolio, role assignment joins by member).

## 4) Expected distribution and skew risk
- Expected shard load for large N: roughly `N/3` per shard.
- Small temporary skew is possible for very small datasets.
- Long-term skew risk is low unless member_id assignment becomes non-uniform.

## 5) Trade-offs to mention in report
- **Pros:** Balanced writes, good point-lookup scaling, simple routing logic.
- **Cons:** Name-prefix search and broad filters require scatter-gather across shards.
- **Operational note:** Reference tables are replicated; member-centric tables are partitioned.

## 6) Deployment context used
- Host: `10.0.116.184`
- MySQL shard ports: `3307`, `3308`, `3309`
- Team DB/User: `Data_Dynamics`
