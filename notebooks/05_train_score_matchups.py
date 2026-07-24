# Databricks notebook source
# MAGIC %md
# MAGIC # 05 — Train matchup model, score slate, build matchup cards
# MAGIC Lines are shown for model-vs-market comparison and are **not** training features.

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
from saturday_hq.transform.gold import build_gold_matchup_card

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

# COMMAND ----------

card_table = build_gold_matchup_card(config)
print("wrote", card_table)
display(
    spark.table(card_table)
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
