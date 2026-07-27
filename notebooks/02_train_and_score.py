# Databricks notebook source
# MAGIC %md
# MAGIC # 02 — Train matchup model and score games
# MAGIC Reads `cfb_gold.game_features` (built by dbt) and writes `cfb_gold.game_predictions`.
# MAGIC Lines are shown for model-vs-market comparison and are **not** training features.
# MAGIC
# MAGIC Run `dbt build` before this notebook. Afterwards run
# MAGIC `dbt build --select gold_matchup_card` to fold these predictions into the card.

# COMMAND ----------

import sys
from pathlib import Path

# Edit these constants if needed (no notebook widgets).
REPO_PATH = ""
CURRENT_SEASON = 2026
MODEL_NAME = "saturday_hq_matchup"

if REPO_PATH.strip():
    sys.path.insert(0, f"{REPO_PATH.strip()}/src")
else:
    sys.path.insert(0, str(Path.cwd().parent / "src"))
    sys.path.insert(0, str(Path.cwd() / "src"))

from saturday_hq.config import SaturdayHQConfig
from saturday_hq.ml.train import train_and_register, score_games

config = SaturdayHQConfig(current_season=CURRENT_SEASON)

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

# MAGIC %md
# MAGIC ## Next step
# MAGIC `cfb_gold.matchup_card` is a dbt model over these predictions:
# MAGIC ```bash
# MAGIC dbt build --select gold_matchup_card
# MAGIC ```
