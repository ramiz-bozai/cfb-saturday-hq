# Databricks notebook source
# MAGIC %md
# MAGIC # 04 — Gold team_week + game_features

# COMMAND ----------

import sys
from pathlib import Path

# Edit these constants if needed (no notebook widgets).
REPO_PATH = ""

if REPO_PATH.strip():
    sys.path.insert(0, f"{REPO_PATH.strip()}/src")
else:
    sys.path.insert(0, str(Path.cwd().parent / "src"))
    sys.path.insert(0, str(Path.cwd() / "src"))

from saturday_hq.config import SaturdayHQConfig
from saturday_hq.transform.gold import build_gold_core

config = SaturdayHQConfig()
results = build_gold_core(config)
display(spark.createDataFrame(results))

# COMMAND ----------

display(
    spark.table(config.gold("team_week"))
    .filter("season = 2025")
    .orderBy("week", "sp_overall")
    .limit(50)
)

display(
    spark.table(config.gold("game_features"))
    .filter("season = 2025 AND completed")
    .select(
        "game_id",
        "week",
        "home_team",
        "away_team",
        "sp_overall_diff",
        "ppa_offense_diff",
        "market_spread",
        "home_won",
    )
    .limit(50)
)
