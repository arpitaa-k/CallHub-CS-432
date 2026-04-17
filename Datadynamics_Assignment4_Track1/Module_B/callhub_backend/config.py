import os
from dotenv import load_dotenv

load_dotenv()

MYSQL_HOST = os.getenv("MYSQL_HOST")
MYSQL_USER = os.getenv("MYSQL_USER")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD")
MYSQL_DB = os.getenv("MYSQL_DB")

# Assignment 4 sharding configuration 
SHARD_KEY = os.getenv("SHARD_KEY", "member_id")
SHARD_STRATEGY = os.getenv("SHARD_STRATEGY", "hash_mod")
NUM_SHARDS = int(os.getenv("NUM_SHARDS", "3"))

SHARD_HOST = os.getenv("SHARD_HOST", "10.0.116.184")
SHARD_PORTS = [
	int(os.getenv("SHARD_0_PORT", "3307")),
	int(os.getenv("SHARD_1_PORT", "3308")),
	int(os.getenv("SHARD_2_PORT", "3309")),
]

# Team credentials provided by instructor deployment.
TEAM_DB_USER = os.getenv("TEAM_DB_USER", "Data_Dynamics")
TEAM_DB_PASSWORD = os.getenv("TEAM_DB_PASSWORD", "password@123")
TEAM_DB_NAME = os.getenv("TEAM_DB_NAME", "Data_Dynamics")

