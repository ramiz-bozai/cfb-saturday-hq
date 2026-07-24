# Databricks notebook source
# MAGIC %md
# MAGIC # Step 10 + 14: Preseason ratings, CFP projections, weekly briefs

# COMMAND ----------

import sys
from pathlib import Path

dbutils.widgets.text("repo_path", "")
dbutils.widgets.text("catalog", "saturday_hq")
dbutils.widgets.text("current_season", "2026")
dbutils.widgets.text("n_sims", "2000")
dbutils.widgets.text("week", "")

repo_path = dbutils.widgets.get("repo_path").strip()
sys.path.insert(0, f"{repo_path}/src" if repo_path else str(Path.cwd().parent / "src"))

from pyspark.sql import functions as F

from saturday_hq.config import config_from_widgets
from saturday_hq.projections.simulator import build_preseason_ratings, simulate_season
from saturday_hq.briefs.generate import generate_weekly_briefs
from saturday_hq.cfp_rules import CFP_RULES_TEXT

config = config_from_widgets(
    catalog=dbutils.widgets.get("catalog"),
    current_season=int(dbutils.widgets.get("current_season")),
)
print(CFP_RULES_TEXT[:500], "...")

# COMMAND ----------

pre_table = build_preseason_ratings(config)
display(spark.table(pre_table).orderBy("preseason_rank").limit(25))

# COMMAND ----------

proj = simulate_season(
    config,
    season=config.current_season,
    n_sims=int(dbutils.widgets.get("n_sims")),
    use_model_probs=True,
)
print(proj)
display(
    spark.table(config.gold("playoff_projections"))
    .orderBy(F.desc("playoff_odds"))
    .limit(20)
)

# COMMAND ----------

week_raw = dbutils.widgets.get("week").strip()
week = int(week_raw) if week_raw else None
brief_table = generate_weekly_briefs(config, season=config.current_season, week=week)
display(spark.table(brief_table).limit(50))
