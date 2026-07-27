# Databricks notebook source
# MAGIC %md
# MAGIC # 04 — Daily refresh
# MAGIC
# MAGIC Order of operations, and why dbt appears twice:
# MAGIC 1. **Python** — API pull for the current season into Volume `incremental/dt=YYYY-MM-DD/`
# MAGIC 2. **dbt** — bronze → silver → gold, excluding the matchup card
# MAGIC 3. **Python** — score the slate into `cfb_gold.game_predictions`
# MAGIC 4. **dbt** — build `gold_matchup_card` now that predictions exist
# MAGIC 5. **Python** — preseason ratings, playoff simulation, weekly briefs
# MAGIC
# MAGIC `RUN_DBT = False` prints the dbt commands instead of running them, which is what you
# MAGIC want if you orchestrate dbt as its own Job task around this notebook.

# COMMAND ----------

# MAGIC %pip install dbt-databricks --quiet

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

import os
import subprocess
import sys
from pathlib import Path

# Edit these constants if needed (no notebook widgets).
REPO_PATH = ""
CURRENT_SEASON = 2026
MODEL_NAME = "saturday_hq_matchup"
WEEK = None  # None => full current season pull / latest week for briefs
SECRET_SCOPE = "cfb_saturday_hq"
SECRET_KEY = "cfbd_api_key"
RUN_DBT = True  # False => print the dbt commands and keep going
DBT_TARGET = "dev"

repo_root = Path(REPO_PATH.strip()) if REPO_PATH.strip() else Path.cwd().parent
sys.path.insert(0, str(repo_root / "src"))
DBT_PROJECT_DIR = repo_root / "dbt"

from saturday_hq.config import SaturdayHQConfig
from saturday_hq.cfbd_client import CFBDClient
from saturday_hq.ingest.download_historical import download_incremental_to_volume
from saturday_hq.ml.train import score_games
from saturday_hq.projections.simulator import build_preseason_ratings, simulate_season
from saturday_hq.briefs.generate import generate_weekly_briefs

config = SaturdayHQConfig(
    current_season=CURRENT_SEASON,
    secret_scope=SECRET_SCOPE,
    secret_key=SECRET_KEY,
)

api_key = dbutils.secrets.get(config.secret_scope, config.secret_key)
client = CFBDClient(api_key, config)


def dbt_build(*args: str) -> None:
    """Run `dbt build` in the repo's dbt project, or print the command if RUN_DBT is off."""
    # Invoked through the interpreter so it works without dbt on PATH.
    cmd = [
        sys.executable,
        "-m",
        "dbt.cli.main",
        "build",
        "--project-dir",
        str(DBT_PROJECT_DIR),
        "--profiles-dir",
        str(DBT_PROJECT_DIR),
        "--target",
        DBT_TARGET,
        # Incremental drops exist by the time the daily job runs.
        "--vars",
        "{include_incremental: true}",
        *args,
    ]
    if not RUN_DBT:
        print("dbt step (not run):", " ".join(cmd))
        return
    # Keep dbt's artifacts off the (possibly read-only) workspace project folder.
    env = {
        **os.environ,
        "DBT_TARGET_PATH": "/tmp/dbt_target",
        "DBT_LOG_PATH": "/tmp/dbt_logs",
    }
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
    print(result.stdout[-4000:])
    if result.returncode != 0:
        print(result.stderr[-4000:])
        raise RuntimeError(f"dbt failed: {' '.join(cmd)}")


# COMMAND ----------

# 1. Ingest today's CFBD snapshot for the current season
inc = download_incremental_to_volume(
    client, config, year=config.current_season, week=WEEK
)
display(spark.createDataFrame(inc))

# COMMAND ----------

# 2. Transform bronze -> silver -> gold. The card waits for predictions.
dbt_build("--exclude", "gold_matchup_card")

# COMMAND ----------

# 3. Score the slate with the registered model
score_games(
    config,
    model_name=MODEL_NAME,
    seasons=[config.current_season],
)

# COMMAND ----------

# 4. Now that predictions exist, build the serving card
dbt_build("--select", "gold_matchup_card")

# COMMAND ----------

# 5. Ratings, playoff odds, briefs
build_preseason_ratings(config, season=config.current_season)
simulate_season(config, season=config.current_season, n_sims=2000, use_model_probs=True)
generate_weekly_briefs(config, season=config.current_season, week=WEEK)

print("daily refresh complete")
