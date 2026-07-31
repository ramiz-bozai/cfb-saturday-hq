# Databricks notebook source
# MAGIC %md
# MAGIC # 06 — Season Preview ingest
# MAGIC
# MAGIC Pulls player-level CFBD domains for the **upcoming season** (Season Preview target)
# MAGIC and the prior completed season's production/usage into `incremental/dt=YYYY-MM-DD/`
# MAGIC so continuity models can weight returning players.
# MAGIC
# MAGIC Allowed outside the Aug–Jan window (unlike notebook 04's weekly/market modes).
# MAGIC
# MAGIC Domains: teams_fbs, rosters (~130 calls/year), player_portal, player_returning,
# MAGIC player_usage, player_season_stats, ppa_players_season, recruiting_players.
# MAGIC
# MAGIC After this notebook: `dbt build --select bronze_rosters+` (or a full build).

# COMMAND ----------

import sys
from pathlib import Path

REPO_PATH = ""
UPCOMING_SEASON = None  # None => preview_season() (July 2026 -> 2026)
SECRET_SCOPE = "cfb_saturday_hq"
SECRET_KEY = "cfbd_api_key"

repo_root = Path(REPO_PATH.strip()) if REPO_PATH.strip() else Path.cwd().parent
sys.path.insert(0, str(repo_root / "src"))

from saturday_hq.config import SaturdayHQConfig, preview_season
from saturday_hq.cfbd_client import CFBDClient
from saturday_hq.ingest.download_historical import download_preview_to_volume, plan_domains

config = SaturdayHQConfig(secret_scope=SECRET_SCOPE, secret_key=SECRET_KEY)
upcoming = UPCOMING_SEASON or preview_season()
domains = plan_domains(config, season=upcoming, mode="preview")

print("preview season:", upcoming, "| prior:", upcoming - 1)
print("shared landing volume:", config.volume_path)
print(f"domains ({len(domains)}):", domains)

# COMMAND ----------

api_key = dbutils.secrets.get(config.secret_scope, config.secret_key)
client = CFBDClient(api_key, config)

manifest = download_preview_to_volume(
    client=client,
    config=config,
    upcoming_season=upcoming,
    domains=domains,
)
manifest_df = spark.createDataFrame(manifest)
display(manifest_df.orderBy("domain", "year"))
if "error" in manifest_df.columns:
    print("errors:", manifest_df.filter("error is not null").count())
print("dbt task should build player bronze → gold next")
