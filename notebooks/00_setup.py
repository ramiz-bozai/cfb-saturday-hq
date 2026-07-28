# Databricks notebook source
# MAGIC %md
# MAGIC # 00 — Saturday HQ setup
# MAGIC
# MAGIC Creates the Unity Catalog objects, in two distinct pieces:
# MAGIC
# MAGIC - **One shared raw catalog** (`cfb_saturday_hq_raw.landing`) holding the CFBD landing
# MAGIC   volume. Neither environment owns it, so the API is only ever called once and dev reads
# MAGIC   exactly what prod reads.
# MAGIC - **One catalog per environment** (`cfb_saturday_hq_dev`, `cfb_saturday_hq_prod`), each
# MAGIC   with the full `cfb_bronze` → `cfb_silver` → `cfb_gold` set plus `cfb_ml` / `cfb_app`.
# MAGIC   dbt builds the medallion into whichever one the run targets.
# MAGIC
# MAGIC Run this once and it sets up both environments. It also verifies CFBD secret access.

# COMMAND ----------

# MAGIC %pip install requests tenacity pandas scikit-learn mlflow --quiet
# MAGIC dbutils.library.restartPython()

# COMMAND ----------

import sys
from pathlib import Path

# Edit these constants if needed (no notebook widgets).
REPO_PATH = ""  # e.g. "/Workspace/Users/you@company.com/saturday-hq"; blank => auto-detect
HISTORY_START_YEAR = 2015
CURRENT_SEASON = None  # None => derived from today's date (August rollover)
SETUP_ENVIRONMENTS = ("dev", "prod")  # environments to create catalogs for
SECRET_SCOPE = "cfb_saturday_hq"
SECRET_KEY = "cfbd_api_key"

if REPO_PATH.strip():
    sys.path.insert(0, f"{REPO_PATH.strip()}/src")
else:
    sys.path.insert(0, str(Path.cwd().parent / "src"))
    sys.path.insert(0, str(Path.cwd() / "src"))

from saturday_hq.config import SaturdayHQConfig, current_cfb_season

configs = {
    env: SaturdayHQConfig(
        env=env,
        history_start_year=HISTORY_START_YEAR,
        current_season=CURRENT_SEASON or current_cfb_season(),
        secret_scope=SECRET_SCOPE,
        secret_key=SECRET_KEY,
    )
    for env in SETUP_ENVIRONMENTS
}
for env, cfg in configs.items():
    print(f"{env}: catalog {cfg.catalog}")

# Any config knows the shared raw location; they all agree on it.
raw = configs[SETUP_ENVIRONMENTS[0]]
print("season:", raw.current_season)
print("shared volume:", raw.volume_path)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Shared raw landing (created once, read by every environment)

# COMMAND ----------

spark.sql(f"CREATE CATALOG IF NOT EXISTS {raw.raw_catalog}")
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {raw.raw_catalog}.{raw.raw_schema}")
spark.sql(
    f"CREATE VOLUME IF NOT EXISTS {raw.raw_catalog}.{raw.raw_schema}.{raw.volume_name}"
)

for sub in [raw.historical_path, raw.incremental_path, raw.manual_path]:
    Path(sub).mkdir(parents=True, exist_ok=True)
    print("ready:", sub)

# COMMAND ----------

# MAGIC %md
# MAGIC ## One catalog per environment (bronze → silver → gold)

# COMMAND ----------

for env, cfg in configs.items():
    spark.sql(f"CREATE CATALOG IF NOT EXISTS {cfg.catalog}")
    for schema in [
        cfg.schema_bronze,
        cfg.schema_silver,
        cfg.schema_gold,
        cfg.schema_ml,
        cfg.schema_app,
    ]:
        spark.sql(f"CREATE SCHEMA IF NOT EXISTS {cfg.catalog}.{schema}")
    print("ready:", cfg.catalog)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Secret check
# MAGIC Create the secret once in a terminal / Cloud Shell:
# MAGIC ```bash
# MAGIC databricks secrets create-scope cfb_saturday_hq
# MAGIC databricks secrets put-secret cfb_saturday_hq cfbd_api_key
# MAGIC ```

# COMMAND ----------

api_key = dbutils.secrets.get(raw.secret_scope, raw.secret_key)
assert api_key, "API key secret is empty"
print("CFBD secret found (value not printed).")

# COMMAND ----------

# cfb_gold.matchup_card is a dbt view over this table, and Python fills it during scoring.
# Creating it empty in each environment means the first `dbt build` can create the view
# before any model has been trained.
for env, cfg in configs.items():
    spark.sql(
        f"""
CREATE TABLE IF NOT EXISTS {cfg.gold('game_predictions')} (
  game_id BIGINT,
  season INT,
  week INT,
  model_home_win_prob DOUBLE,
  model_version STRING,
  scored_at STRING
) USING DELTA
"""
    )
    print("ready:", cfg.gold("game_predictions"))

# COMMAND ----------

for env, cfg in configs.items():
    spark.sql(
        f"""
CREATE TABLE IF NOT EXISTS {cfg.app('demo_profiles')} (
  profile_id STRING,
  display_name STRING,
  teams ARRAY<STRING>
) USING DELTA
"""
    )
    spark.sql(
        f"""
CREATE OR REPLACE TABLE {cfg.app('demo_profiles')} AS
SELECT * FROM VALUES
  ('sec_fan', 'SEC Fan', array('Alabama','Georgia','Oklahoma','Texas','LSU')),
  ('big_ten_fan', 'Big Ten Fan', array('Ohio State','Indiana','Oregon','Michigan','Penn State')),
  ('underdog', 'G6 Watcher', array('Tulane','Boise State','James Madison','UNLV'))
AS t(profile_id, display_name, teams)
"""
    )

display(spark.table(configs[SETUP_ENVIRONMENTS[0]].app("demo_profiles")))
