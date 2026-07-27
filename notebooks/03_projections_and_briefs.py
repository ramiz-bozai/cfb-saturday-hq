# Databricks notebook source
# MAGIC %md
# MAGIC # 03 — Preseason ratings, CFP projections, weekly briefs
# MAGIC Reads dbt-built silver/gold tables; briefs need `cfb_gold.matchup_card`, so run
# MAGIC `dbt build --select gold_matchup_card` after scoring and before this notebook.

# COMMAND ----------

import sys
from pathlib import Path

# Edit these constants if needed (no notebook widgets).
REPO_PATH = ""
CURRENT_SEASON = 2026
N_SIMS = 2000
WEEK = None  # None => latest available week in data

if REPO_PATH.strip():
    sys.path.insert(0, f"{REPO_PATH.strip()}/src")
else:
    sys.path.insert(0, str(Path.cwd().parent / "src"))
    sys.path.insert(0, str(Path.cwd() / "src"))

from pyspark.sql import functions as F

from saturday_hq.config import SaturdayHQConfig
from saturday_hq.projections.simulator import build_preseason_ratings, simulate_season
from saturday_hq.briefs.generate import generate_weekly_briefs
from saturday_hq.cfp_rules import CFP_RULES_TEXT

config = SaturdayHQConfig(current_season=CURRENT_SEASON)
print(CFP_RULES_TEXT[:500], "...")

# COMMAND ----------

pre_table = build_preseason_ratings(config)
display(spark.table(pre_table).orderBy("preseason_rank").limit(25))

# COMMAND ----------

proj = simulate_season(
    config,
    season=config.current_season,
    n_sims=N_SIMS,
    use_model_probs=True,
)
print(proj)
display(
    spark.table(config.gold("playoff_projections"))
    .orderBy(F.desc("playoff_odds"))
    .limit(20)
)

# COMMAND ----------

brief_table = generate_weekly_briefs(config, season=config.current_season, week=WEEK)
display(spark.table(brief_table).limit(50))
