# Databricks notebook source
# MAGIC %md
# MAGIC # Step 9 / Daily job: API incremental → bronze → silver → gold → score → briefs
# MAGIC Schedule this notebook daily.

# COMMAND ----------

import sys
from pathlib import Path

dbutils.widgets.text("repo_path", "")
dbutils.widgets.text("catalog", "saturday_hq")
dbutils.widgets.text("secret_scope", "saturday_hq")
dbutils.widgets.text("secret_key", "cfbd_api_key")
dbutils.widgets.text("current_season", "2026")
dbutils.widgets.text("model_name", "saturday_hq_matchup")
dbutils.widgets.text("week", "")

repo_path = dbutils.widgets.get("repo_path").strip()
sys.path.insert(0, f"{repo_path}/src" if repo_path else str(Path.cwd().parent / "src"))

from saturday_hq.config import config_from_widgets
from saturday_hq.cfbd_client import CFBDClient
from saturday_hq.ingest.download_historical import download_incremental_to_volume
from saturday_hq.ingest.bronze_from_volume import load_all_bronze
from saturday_hq.transform.silver import build_all_silver
from saturday_hq.transform.gold import build_gold_core, build_gold_matchup_card
from saturday_hq.ml.train import score_games
from saturday_hq.projections.simulator import build_preseason_ratings, simulate_season
from saturday_hq.briefs.generate import generate_weekly_briefs

config = config_from_widgets(
    catalog=dbutils.widgets.get("catalog"),
    current_season=int(dbutils.widgets.get("current_season")),
    secret_scope=dbutils.widgets.get("secret_scope"),
    secret_key=dbutils.widgets.get("secret_key"),
)
model_name = dbutils.widgets.get("model_name")
week_raw = dbutils.widgets.get("week").strip()
week = int(week_raw) if week_raw else None

api_key = dbutils.secrets.get(config.secret_scope, config.secret_key)
client = CFBDClient(api_key, config)

# COMMAND ----------

inc = download_incremental_to_volume(
    client, config, year=config.current_season, week=week
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
    model_name=model_name,
    seasons=[config.current_season],
)
build_gold_matchup_card(config)
build_preseason_ratings(config, season=config.current_season)
simulate_season(config, season=config.current_season, n_sims=2000, use_model_probs=True)
generate_weekly_briefs(config, season=config.current_season, week=week)

print("daily refresh complete")
