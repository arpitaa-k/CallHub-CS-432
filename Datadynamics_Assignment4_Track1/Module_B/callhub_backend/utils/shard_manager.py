import pymysql
from pymysql.err import MySQLError
from config import SHARD_HOST, SHARD_PORTS, TEAM_DB_USER, TEAM_DB_PASSWORD, TEAM_DB_NAME, NUM_SHARDS, SHARD_KEY, SHARD_STRATEGY

class ShardManager:
    def __init__(self):
        self.connections = {}
        self.alive = {}
        for i in range(NUM_SHARDS):
            self._connect_shard(i)
        self._print_shard_status()

    def _connect_shard(self, shard_id):
        try:
            conn = pymysql.connect(
                host=SHARD_HOST,
                port=SHARD_PORTS[shard_id],
                user=TEAM_DB_USER,
                password=TEAM_DB_PASSWORD,
                database=TEAM_DB_NAME,
                autocommit=False  # We'll manage transactions
            )
            self.connections[shard_id] = conn
            self.alive[shard_id] = True
        except Exception as exc:
            self.connections[shard_id] = None
            self.alive[shard_id] = False
            print(f"[SHARD] failed to connect shard {shard_id}: {exc}")

    def _print_shard_status(self):
        print(
            f"[SHARD STATUS] available={self.get_available_shards()}, unavailable={self.get_unavailable_shards()}"
        )

    def _mark_shard_down(self, shard_id, exc=None):
        self.alive[shard_id] = False
        if exc is not None:
            print(f"[SHARD] shard {shard_id} marked down: {exc}")
        else:
            print(f"[SHARD] shard {shard_id} marked down")
        self._print_shard_status()

    def get_shard_id(self, member_id):
        if SHARD_STRATEGY == "hash_mod":
            return member_id % NUM_SHARDS
        return 0

    def get_available_shards(self):
        return [shard_id for shard_id in range(NUM_SHARDS) if self.alive.get(shard_id, False)]

    def get_unavailable_shards(self):
        return [shard_id for shard_id in range(NUM_SHARDS) if not self.alive.get(shard_id, False)]

    def _ensure_connection(self, shard_id):
        if not self.alive.get(shard_id, False):
            self._connect_shard(shard_id)
            if self.alive.get(shard_id, False):
                print(f"[SHARD] shard {shard_id} restored")
                self._print_shard_status()
        conn = self.connections.get(shard_id)
        if conn is None:
            raise ConnectionError(f"Shard {shard_id} is unavailable")
        try:
            conn.ping(reconnect=True)
            self.alive[shard_id] = True
        except Exception as exc:
            self._mark_shard_down(shard_id, exc)
            raise ConnectionError(f"Shard {shard_id} is unavailable") from exc
        return conn

    def get_connection(self, shard_id):
        return self._ensure_connection(shard_id)

    def execute_on_shard(self, shard_id, query, params=None, fetch=False):
        conn = self._ensure_connection(shard_id)
        cursor = conn.cursor()
        try:
            cursor.execute(query, params)
            if fetch:
                return cursor.fetchall()
            conn.commit()
            return None
        except (MySQLError, ConnectionError) as exc:
            self._mark_shard_down(shard_id, exc)
            raise
        finally:
            cursor.close()

    def execute_on_all_shards(self, query, params=None, fetch=False):
        results = []
        for shard_id in self.get_available_shards():
            try:
                result = self.execute_on_shard(shard_id, query, params, fetch)
            except Exception as exc:
                print(f"[SHARD] skipping shard {shard_id} during all-shard execution: {exc}")
                continue
            if fetch:
                results.extend(result)
        return results

    def execute_on_available_shards(self, query, params=None, fetch=False):
        return self.execute_on_all_shards(query, params=params, fetch=fetch)

    def get_next_member_id(self):
        # Compute global max across all shards to avoid cross-shard PK collisions.
        max_id = 0
        for shard_id in self.get_available_shards():
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
            if conn is not None:
                conn.close()

# Global instance
shard_manager = ShardManager()