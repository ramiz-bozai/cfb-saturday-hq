# Databricks notebook source
# MAGIC %md
# MAGIC # 01 — Download historical CFBD data into Volume
# MAGIC Writes JSONL under
# MAGIC `/Volumes/cfb_saturday_hq_raw/landing/cfbd_landing/historical/...`
# MAGIC Uses the API once for backfill; the weekly refresh uses the incremental path.
# MAGIC
# MAGIC **Call cost:** 12 CFBD calls per season (both season types for `games` and `lines`),
# MAGIC plus 1 for conferences, so a 2015→2026 backfill is roughly 145 calls. The smoke test
# MAGIC adds 4. This is the most expensive thing in the project and it only runs once.
# MAGIC
# MAGIC The landing volume is **shared by every environment**, so there is no environment to
# MAGIC pick here and this only needs to run once. dev and prod each build their own
# MAGIC bronze → silver → gold from this one copy of the files.

# COMMAND ----------

import sys
from pathlib import Path

# Edit these constants if needed (no notebook widgets).
REPO_PATH = "/Workspace/Users/ramiz.bozai@databricks.com/cfb-saturday-hq"
HISTORY_START_YEAR = 2015
CURRENT_SEASON = None  # None => derived from today's date (August rollover)
END_YEAR = None  # None => CURRENT_SEASON
DOMAINS = None  # None => all HISTORICAL_DOMAINS; or e.g. ["teams_fbs", "games", "sp_plus"]
RUN_SMOKE_TEST = True  # False => skip the 4-call one-year probe on a re-run
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
print("shared landing volume:", config.volume_path)

api_key = dbutils.secrets.get(config.secret_scope, config.secret_key)
client = CFBDClient(api_key, config)

# COMMAND ----------

# Optional: smoke-test one year before committing to the full backfill (4 calls).
if RUN_SMOKE_TEST:
    smoke = download_historical_to_volume(
        client,
        config,
        years=[config.history_start_year],
        domains=["teams_fbs", "games", "sp_plus"],
    )
    display(spark.createDataFrame(smoke))
else:
    print("smoke test skipped")

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
