# Databricks notebook source
# MAGIC %md
# MAGIC # 00 — Saturday HQ setup
# MAGIC Creates UC catalog/schemas, volume folders, and verifies CFBD secret access.

# COMMAND ----------

# MAGIC %pip install requests tenacity pandas scikit-learn mlflow --quiet
# MAGIC dbutils.library.restartPython()

# COMMAND ----------

import sys
from pathlib import Path

# Edit these constants if needed (no notebook widgets).
REPO_PATH = ""  # e.g. "/Workspace/Users/you@company.com/saturday-hq"; blank => auto-detect
HISTORY_START_YEAR = 2015
CURRENT_SEASON = 2026
SECRET_SCOPE = "cfb_saturday_hq"
SECRET_KEY = "cfbd_api_key"

if REPO_PATH.strip():
    sys.path.insert(0, f"{REPO_PATH.strip()}/src")
else:
    sys.path.insert(0, str(Path.cwd().parent / "src"))
    sys.path.insert(0, str(Path.cwd() / "src"))

from saturday_hq.config import SaturdayHQConfig

config = SaturdayHQConfig(
    history_start_year=HISTORY_START_YEAR,
    current_season=CURRENT_SEASON,
    secret_scope=SECRET_SCOPE,
    secret_key=SECRET_KEY,
)
print(config)

# COMMAND ----------

spark.sql(f"CREATE CATALOG IF NOT EXISTS {config.catalog}")
spark.sql(f"USE CATALOG {config.catalog}")
for schema in [
    config.schema_bronze,
    config.schema_silver,
    config.schema_gold,
    config.schema_ml,
    config.schema_app,
]:
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {config.catalog}.{schema}")

spark.sql(
    f"CREATE VOLUME IF NOT EXISTS {config.catalog}.{config.schema_bronze}.{config.volume_name}"
)
print("Volume path:", config.volume_path)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Secret check
# MAGIC Create the secret once in a terminal / Cloud Shell:
# MAGIC ```bash
# MAGIC databricks secrets create-scope cfb_saturday_hq
# MAGIC databricks secrets put-secret cfb_saturday_hq cfbd_api_key
# MAGIC ```

# COMMAND ----------

api_key = dbutils.secrets.get(config.secret_scope, config.secret_key)
assert api_key, "API key secret is empty"
print("CFBD secret found (value not printed).")

# COMMAND ----------

for sub in [config.historical_path, config.incremental_path, config.manual_path]:
    Path(sub).mkdir(parents=True, exist_ok=True)
    print("ready:", sub)

# COMMAND ----------

spark.sql(
    f"""
CREATE TABLE IF NOT EXISTS {config.app('demo_profiles')} (
  profile_id STRING,
  display_name STRING,
  teams ARRAY<STRING>
) USING DELTA
"""
)

spark.sql(
    f"""
CREATE OR REPLACE TABLE {config.app('demo_profiles')} AS
SELECT * FROM VALUES
  ('sec_fan', 'SEC Fan', array('Alabama','Georgia','Oklahoma','Texas','LSU')),
  ('big_ten_fan', 'Big Ten Fan', array('Ohio State','Indiana','Oregon','Michigan','Penn State')),
  ('underdog', 'G6 Watcher', array('Tulane','Boise State','James Madison','UNLV'))
AS t(profile_id, display_name, teams)
"""
)

display(spark.table(config.app("demo_profiles")))
