# Databricks notebook source
# MAGIC %md
# MAGIC # 04 — Daily ingest
# MAGIC
# MAGIC First leg of the daily loop: pull today's CFBD snapshot for the current season into
# MAGIC Volume `incremental/dt=YYYY-MM-DD/`.
# MAGIC
# MAGIC The landing volume is **shared by every environment** (`cfb_saturday_hq_raw.landing`),
# MAGIC so this notebook has no environment to pick: it calls the API once and both dev and
# MAGIC prod build their own bronze → silver → gold from the same files.
# MAGIC
# MAGIC The `saturday-hq-daily-refresh` job runs three tasks in a row, which is the same
# MAGIC Python → dbt → Python handoff the backfill job uses:
# MAGIC
# MAGIC 1. this notebook
# MAGIC 2. a **dbt task** — bronze → silver → gold
# MAGIC 3. `05_daily_score_and_serve.py`
# MAGIC
# MAGIC dbt runs as its own Job task against the committed `dbt/profiles.yml`, so no notebook
# MAGIC installs or shells out to dbt.
# MAGIC
# MAGIC Nothing here needs editing between runs: the season is derived from today's date.

# COMMAND ----------

import sys
from pathlib import Path

# Edit these constants if needed (no notebook widgets).
REPO_PATH = ""
CURRENT_SEASON = None  # None => derived from today's date (August rollover)
WEEK = None  # None => full current season pull
SECRET_SCOPE = "cfb_saturday_hq"
SECRET_KEY = "cfbd_api_key"

repo_root = Path(REPO_PATH.strip()) if REPO_PATH.strip() else Path.cwd().parent
sys.path.insert(0, str(repo_root / "src"))

from saturday_hq.config import SaturdayHQConfig, current_cfb_season
from saturday_hq.cfbd_client import CFBDClient
from saturday_hq.ingest.download_historical import download_incremental_to_volume

config = SaturdayHQConfig(
    current_season=CURRENT_SEASON or current_cfb_season(),
    secret_scope=SECRET_SCOPE,
    secret_key=SECRET_KEY,
)
print("season:", config.current_season)
print("shared landing volume:", config.volume_path)

api_key = dbutils.secrets.get(config.secret_scope, config.secret_key)
client = CFBDClient(api_key, config)

# COMMAND ----------

inc = download_incremental_to_volume(
    client, config, year=config.current_season, week=WEEK
)
display(spark.createDataFrame(inc))

print("ingest complete for season", config.current_season, "— dbt task runs next")
