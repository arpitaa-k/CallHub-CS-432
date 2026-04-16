import pymysql
from config import SHARD_HOST, SHARD_PORTS, TEAM_DB_USER, TEAM_DB_PASSWORD, TEAM_DB_NAME, NUM_SHARDS, SHARD_KEY, SHARD_STRATEGY

class ShardManager:
    def __init__(self):
        self.connections = {}
        for i in range(NUM_SHARDS):
            self.connections[i] = pymysql.connect(
                host=SHARD_HOST,
                port=SHARD_PORTS[i],
                user=TEAM_DB_USER,
                password=TEAM_DB_PASSWORD,
                database=TEAM_DB_NAME,
                autocommit=False  # We'll manage transactions
            )

    def get_shard_id(self, member_id):
        if SHARD_STRATEGY == "hash_mod":
            return member_id % NUM_SHARDS
        # Add other strategies if needed
        return 0

    def get_connection(self, shard_id):
        return self.connections[shard_id]

    def execute_on_shard(self, shard_id, query, params=None, fetch=False):
        conn = self.get_connection(shard_id)
        cursor = conn.cursor()
        try:
            cursor.execute(query, params)
            if fetch:
                return cursor.fetchall()
            else:
                conn.commit()
            return None
        finally:
            cursor.close()

    def execute_on_all_shards(self, query, params=None, fetch=False):
        results = []
        for shard_id in range(NUM_SHARDS):
            result = self.execute_on_shard(shard_id, query, params, fetch)
            if fetch:
                results.extend(result)
        return results

    def get_next_member_id(self):
        # Compute global max across all shards to avoid cross-shard PK collisions.
        max_id = 0
        for shard_id in range(NUM_SHARDS):
            result = self.execute_on_shard(
                shard_id,
                "SELECT MAX(member_id) FROM shard_{}_members".format(shard_id),
                fetch=True,
            )
            shard_max = result[0][0] if result and result[0][0] else 0
            if shard_max > max_id:
                max_id = shard_max
        return max_id + 1

    def close_all(self):
        for conn in self.connections.values():
            conn.close()

# Global instance
shard_manager = ShardManager()