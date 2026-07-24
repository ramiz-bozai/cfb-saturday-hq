# Databricks notebook source
# MAGIC %md
# MAGIC # Step 0–2: Saturday HQ setup
# MAGIC Creates UC schemas, volume, and verifies CFBD secret access.

# COMMAND ----------

# MAGIC %pip install requests tenacity pandas scikit-learn mlflow --quiet
# MAGIC dbutils.library.restartPython()

# COMMAND ----------

import sys
from pathlib import Path

# Repo root on path whether run from bundle sync or Git folder
for candidate in [
    Path.cwd(),
    Path.cwd().parent,
    Path("/Workspace/Users/") ,
]:
    pass

# Prefer explicit repo path widget
dbutils.widgets.text("repo_path", "")
dbutils.widgets.text("catalog", "saturday_hq")
dbutils.widgets.text("secret_scope", "saturday_hq")
dbutils.widgets.text("secret_key", "cfbd_api_key")
dbutils.widgets.text("history_start_year", "2015")
dbutils.widgets.text("current_season", "2026")

repo_path = dbutils.widgets.get("repo_path").strip()
if repo_path:
    sys.path.insert(0, f"{repo_path}/src")
else:
    # Common bundle layout: notebooks/ next to src/
    sys.path.insert(0, str(Path.cwd().parent / "src"))
    sys.path.insert(0, str(Path.cwd() / "src"))

from saturday_hq.config import SaturdayHQConfig, config_from_widgets

config = config_from_widgets(
    catalog=dbutils.widgets.get("catalog"),
    history_start_year=int(dbutils.widgets.get("history_start_year")),
    current_season=int(dbutils.widgets.get("current_season")),
    secret_scope=dbutils.widgets.get("secret_scope"),
    secret_key=dbutils.widgets.get("secret_key"),
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
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {schema}")

spark.sql(
    f"CREATE VOLUME IF NOT EXISTS {config.catalog}.{config.schema_bronze}.{config.volume_name}"
)
print("Volume path:", config.volume_path)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Secret check
# MAGIC Create the secret once in a terminal / Cloud Shell:
# MAGIC ```bash
# MAGIC databricks secrets create-scope saturday_hq
# MAGIC databricks secrets put-secret saturday_hq cfbd_api_key
# MAGIC ```

# COMMAND ----------

api_key = dbutils.secrets.get(config.secret_scope, config.secret_key)
assert api_key, "API key secret is empty"
print("CFBD secret found (value not printed).")

# COMMAND ----------

from pathlib import Path

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
  ('sec_fan', 'SEC Fan', array('Alabama','Georgia','Texas','LSU')),
  ('big_ten_fan', 'Big Ten Fan', array('Ohio State','Oregon','Michigan','Penn State')),
  ('underdog', 'G6 Watcher', array('Tulane','Boise State','James Madison','UNLV'))
AS t(profile_id, display_name, teams)
"""
)

display(spark.table(config.app("demo_profiles")))
