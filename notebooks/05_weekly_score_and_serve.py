# Databricks notebook source
# MAGIC %md
# MAGIC # 05 — Weekly score and serve
# MAGIC
# MAGIC Last leg of the weekly loop, after `04_weekly_ingest.py` and the job's dbt task have
# MAGIC refreshed gold. Scores the slate with the registered model, then rebuilds the serving
# MAGIC marts: preseason ratings, playoff sims, and weekly briefs.
# MAGIC
# MAGIC Makes no API calls, so it is free to re-run.
# MAGIC
# MAGIC No dbt call afterwards — `cfb_gold.matchup_card` is a dbt **view**, so the probabilities
# MAGIC written here are visible through it immediately.
# MAGIC
# MAGIC Nothing here needs editing between runs: the season is derived from today's date.

# COMMAND ----------

import sys
from pathlib import Path

# Edit these constants if needed (no notebook widgets).
REPO_PATH = ""
ENV = ""  # blank => SATURDAY_HQ_ENV from the job cluster, else "dev"
CURRENT_SEASON = None  # None => derived from today's date (August rollover)
MODEL_NAME = ""  # blank => <catalog>.cfb_ml.matchup for this environment
SEASON_TYPES = ("regular", "postseason")  # kept separate because their week numbers overlap
WEEK = None  # None => refresh every week in SEASON_TYPES; int => targeted repair
N_SIMS = 2000
RANDOM_SEED = 42  # fixed so identical inputs produce identical projections

repo_root = Path(REPO_PATH.strip()) if REPO_PATH.strip() else Path.cwd().parent
sys.path.insert(0, str(repo_root / "src"))

from saturday_hq.config import SaturdayHQConfig, current_cfb_season
from saturday_hq.ml.train import score_games
from saturday_hq.projections.simulator import build_preseason_ratings, simulate_season
from saturday_hq.briefs.generate import generate_weekly_briefs

config = SaturdayHQConfig(env=ENV, current_season=CURRENT_SEASON or current_cfb_season())
model_name = MODEL_NAME or config.model_name
print("env:", config.env, "| catalog:", config.catalog)
print("season:", config.current_season, "| model:", model_name)

# COMMAND ----------

score_games(
    config,
    model_name=model_name,
    seasons=[config.current_season],
)
build_preseason_ratings(config, season=config.current_season)
simulate_season(
    config,
    season=config.current_season,
    n_sims=N_SIMS,
    use_model_probs=True,
    random_seed=RANDOM_SEED,
)
for season_type in SEASON_TYPES:
    generate_weekly_briefs(
        config,
        season=config.current_season,
        week=WEEK,
        season_type=season_type,
    )

print("weekly refresh complete for season", config.current_season)

# COMMAND ----------

display(spark.table(config.gold("matchup_card")))
