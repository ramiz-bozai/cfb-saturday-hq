# Databricks notebook source
# MAGIC %md
# MAGIC # 01 — Download historical CFBD data into Volume
# MAGIC Writes JSONL under `/Volumes/cfb_saturday_hq/cfb_bronze/cfbd_landing/historical/...`
# MAGIC Uses the API once for backfill; the weekly refresh uses the incremental path.

# COMMAND ----------

import sys
from pathlib import Path

# Edit these constants if needed (no notebook widgets).
REPO_PATH = "/Workspace/Users/ramiz.bozai@databricks.com/cfb-saturday-hq"
HISTORY_START_YEAR = 2015
CURRENT_SEASON = None  # None => derived from today's date; set an int to pin a season
END_YEAR = None  # None => CURRENT_SEASON; bump to the upcoming year to grab its schedule early
DOMAINS = None  # None => all HISTORICAL_DOMAINS; or e.g. ["teams_fbs", "games", "sp_plus"]
SECRET_SCOPE = "cfb_saturday_hq"
SECRET_KEY = "cfbd_api_key"

if REPO_PATH.strip():
    sys.path.insert(0, f"{REPO_PATH.strip()}/src")
else:
    sys.path.insert(0, str(Path.cwd().parent / "src"))
    sys.path.insert(0, str(Path.cwd() / "src"))

from saturday_hq.config import HISTORICAL_DOMAINS, SaturdayHQConfig, current_cfb_season
from saturday_hq.cfbd_client import CFBDClient
from saturday_hq.ingest.download_historical import download_historical_to_volume

config = SaturdayHQConfig(
    history_start_year=HISTORY_START_YEAR,
    current_season=CURRENT_SEASON or current_cfb_season(),
    secret_scope=SECRET_SCOPE,
    secret_key=SECRET_KEY,
)
end_year = END_YEAR if END_YEAR is not None else config.current_season
domains = list(DOMAINS) if DOMAINS else list(HISTORICAL_DOMAINS)
print(f"backfilling {config.history_start_year} -> {end_year}")

api_key = dbutils.secrets.get(config.secret_scope, config.secret_key)
client = CFBDClient(api_key, config)

# COMMAND ----------

# Optional: smoke-test one year before full backfill
smoke = download_historical_to_volume(
    client,
    config,
    years=[config.history_start_year],
    domains=["teams_fbs", "games", "sp_plus"],
)
display(spark.createDataFrame(smoke))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Full historical backfill
# MAGIC This can take a while (many seasons × domains). Re-run safe: files overwrite per domain/year.

# COMMAND ----------

manifest = download_historical_to_volume(
    client,
    config,
    start_year=config.history_start_year,
    end_year=end_year,
    domains=domains,
)
manifest_df = spark.createDataFrame(manifest)
display(manifest_df.orderBy("domain", "year"))
if "error" in manifest_df.columns:
    print("errors:", manifest_df.filter("error is not null").count())
print("historical root:", config.historical_path)
