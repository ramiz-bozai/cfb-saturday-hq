# Databricks notebook source
# MAGIC %md
# MAGIC # 07 — Weekly in-season refresh
# MAGIC API incremental → bronze → silver → gold → score → briefs.
# MAGIC
# MAGIC The season is derived from today's date: CFBD labels a season by its starting year, so
# MAGIC runs before August pull the last completed season and runs from August onward pull the
# MAGIC new one. Nothing to change when the season flips over.
# MAGIC
# MAGIC Scheduled weekly (Sunday morning ET) so each run picks up the Saturday slate.

# COMMAND ----------

import sys
from pathlib import Path

# Edit these constants if needed (no notebook widgets).
REPO_PATH = ""
CURRENT_SEASON = None  # None => derived from today's date; set an int to pin a season
MODEL_NAME = "saturday_hq_matchup"
WEEK = None  # None => full-season pull / latest week for briefs
SECRET_SCOPE = "cfb_saturday_hq"
SECRET_KEY = "cfbd_api_key"

if REPO_PATH.strip():
    sys.path.insert(0, f"{REPO_PATH.strip()}/src")
else:
    sys.path.insert(0, str(Path.cwd().parent / "src"))
    sys.path.insert(0, str(Path.cwd() / "src"))

from saturday_hq.config import SaturdayHQConfig, current_cfb_season
from saturday_hq.cfbd_client import CFBDClient
from saturday_hq.ingest.download_historical import download_incremental_to_volume
from saturday_hq.ingest.bronze_from_volume import load_all_bronze
from saturday_hq.transform.silver import build_all_silver
from saturday_hq.transform.gold import build_gold_core, build_gold_matchup_card
from saturday_hq.ml.train import score_games
from saturday_hq.projections.simulator import build_preseason_ratings, simulate_season
from saturday_hq.briefs.generate import generate_weekly_briefs

config = SaturdayHQConfig(
    current_season=CURRENT_SEASON or current_cfb_season(),
    secret_scope=SECRET_SCOPE,
    secret_key=SECRET_KEY,
)
print("refreshing season:", config.current_season)

api_key = dbutils.secrets.get(config.secret_scope, config.secret_key)
client = CFBDClient(api_key, config)

# COMMAND ----------

inc = download_incremental_to_volume(
    client, config, year=config.current_season, week=WEEK
)
display(spark.createDataFrame(inc))

# COMMAND ----------

# Rebuild bronze from historical + latest incremental drops
load_all_bronze(config, mode="both")
build_all_silver(config)
build_gold_core(config)

# COMMAND ----------

score_games(
    config,
    model_name=MODEL_NAME,
    seasons=[config.current_season],
)
build_gold_matchup_card(config)
build_preseason_ratings(config, season=config.current_season)
simulate_season(config, season=config.current_season, n_sims=2000, use_model_probs=True)
generate_weekly_briefs(config, season=config.current_season, week=WEEK)

print("weekly refresh complete")
