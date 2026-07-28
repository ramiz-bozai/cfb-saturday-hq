# Databricks notebook source
# MAGIC %md
# MAGIC # 02 — Train matchup model and score games
# MAGIC Reads `cfb_gold.game_features` (built by dbt) and writes `cfb_gold.game_predictions`.
# MAGIC Lines are shown for model-vs-market comparison and are **not** training features.
# MAGIC
# MAGIC Run `dbt build` before this notebook. Nothing to run in dbt afterwards:
# MAGIC `cfb_gold.matchup_card` is a view, so it picks these predictions up immediately.

# COMMAND ----------

import sys
from pathlib import Path

# Edit these constants if needed (no notebook widgets).
REPO_PATH = ""
CURRENT_SEASON = None  # None => derived from today's date (August rollover)
MODEL_NAME = "saturday_hq_matchup"

if REPO_PATH.strip():
    sys.path.insert(0, f"{REPO_PATH.strip()}/src")
else:
    sys.path.insert(0, str(Path.cwd().parent / "src"))
    sys.path.insert(0, str(Path.cwd() / "src"))

from saturday_hq.config import SaturdayHQConfig, current_cfb_season
from saturday_hq.ml.train import train_and_register, score_games

config = SaturdayHQConfig(current_season=CURRENT_SEASON or current_cfb_season())
print("season:", config.current_season)

# COMMAND ----------

summary = train_and_register(config, model_name=MODEL_NAME)
print(summary)

# COMMAND ----------

# Score historical + current season for dashboards / calibration / slate
pred_table = score_games(
    config,
    model_name=MODEL_NAME,
    seasons=list(range(config.history_start_year, config.current_season + 1)),
)
print("wrote", pred_table)
display(spark.table(pred_table).orderBy("season", "week").limit(50))

# COMMAND ----------

# The dbt view already reflects the scores just written.
display(
    spark.table(config.gold("matchup_card"))
    .filter(f"season = {config.current_season}")
    .select(
        "week",
        "home_team",
        "away_team",
        "model_home_win_prob",
        "market_home_win_prob_implied",
        "model_minus_market_home",
        "market_spread",
        "home_sp_overall",
        "away_sp_overall",
    )
    .orderBy("week")
    .limit(100)
)
