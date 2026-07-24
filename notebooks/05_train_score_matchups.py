# Databricks notebook source
# MAGIC %md
# MAGIC # Step 11–12: Train matchup model, score slate, build matchup cards
# MAGIC Lines are shown for model-vs-market comparison and are **not** training features.

# COMMAND ----------

import sys
from pathlib import Path

dbutils.widgets.text("repo_path", "")
dbutils.widgets.text("catalog", "saturday_hq")
dbutils.widgets.text("current_season", "2026")
dbutils.widgets.text("model_name", "saturday_hq_matchup")

repo_path = dbutils.widgets.get("repo_path").strip()
sys.path.insert(0, f"{repo_path}/src" if repo_path else str(Path.cwd().parent / "src"))

from saturday_hq.config import config_from_widgets
from saturday_hq.ml.train import train_and_register, score_games
from saturday_hq.transform.gold import build_gold_matchup_card

config = config_from_widgets(
    catalog=dbutils.widgets.get("catalog"),
    current_season=int(dbutils.widgets.get("current_season")),
)
model_name = dbutils.widgets.get("model_name")

# COMMAND ----------

summary = train_and_register(config, model_name=model_name)
print(summary)

# COMMAND ----------

# Score historical + current season for dashboards / calibration / slate
pred_table = score_games(
    config,
    model_name=model_name,
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
