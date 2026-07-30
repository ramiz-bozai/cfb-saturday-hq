# Databricks notebook source
# MAGIC %md
# MAGIC # 03 — Preseason ratings, CFP projections, weekly briefs
# MAGIC Reads dbt-built silver/gold relations. Briefs read the `cfb_gold.matchup_card` view,
# MAGIC so run the scoring notebook first; no dbt run is needed in between.

# COMMAND ----------

import sys
from pathlib import Path

# Edit these constants if needed (no notebook widgets).
REPO_PATH = ""
ENV = ""  # blank => SATURDAY_HQ_ENV from the job cluster, else "dev"
CURRENT_SEASON = None  # None => derived from today's date (August rollover)
N_SIMS = 2000
RANDOM_SEED = 42  # fixed so identical inputs produce identical projections
SEASON_TYPES = ("regular", "postseason")  # kept separate because their week numbers overlap
WEEK = None  # None => every week in SEASON_TYPES; int => targeted repair/display

if REPO_PATH.strip():
    sys.path.insert(0, f"{REPO_PATH.strip()}/src")
else:
    sys.path.insert(0, str(Path.cwd().parent / "src"))
    sys.path.insert(0, str(Path.cwd() / "src"))

from pyspark.sql import functions as F

from saturday_hq.config import SaturdayHQConfig, current_cfb_season
from saturday_hq.projections.simulator import build_preseason_ratings, simulate_season
from saturday_hq.briefs.generate import generate_weekly_briefs
from saturday_hq.cfp_rules import CFP_RULES_TEXT

config = SaturdayHQConfig(env=ENV, current_season=CURRENT_SEASON or current_cfb_season())
print("env:", config.env, "| catalog:", config.catalog)
print("season:", config.current_season)
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
    random_seed=RANDOM_SEED,
)
print(proj)
display(
    spark.table(config.gold("playoff_projections"))
    .orderBy(F.desc("playoff_odds"))
    .limit(20)
)

# COMMAND ----------

for season_type in SEASON_TYPES:
    brief_table = generate_weekly_briefs(
        config,
        season=config.current_season,
        week=WEEK,
        season_type=season_type,
    )
brief_columns = (
    set(spark.table(brief_table).columns) if spark.catalog.tableExists(brief_table) else set()
)
if {"game_id", "season_type"}.issubset(brief_columns):
    briefs = (
        spark.table(brief_table)
        .filter(F.col("season") == config.current_season)
        .filter(F.lower(F.col("season_type")).isin(*[value.lower() for value in SEASON_TYPES]))
    )
    if WEEK is not None:
        briefs = briefs.filter(F.col("week") == WEEK)
    display(briefs.orderBy("season_type", "week", "game_id", "team").limit(50))
else:
    print(
        "No current weekly_brief table yet: matchup_card has no games in the requested scopes, "
        "or the legacy schema is waiting for a non-empty scope to trigger migration."
    )
