# Databricks notebook source
# MAGIC %md
# MAGIC # Step 8: Gold team_week + game_features

# COMMAND ----------

import sys
from pathlib import Path

dbutils.widgets.text("repo_path", "")
dbutils.widgets.text("catalog", "saturday_hq")

repo_path = dbutils.widgets.get("repo_path").strip()
sys.path.insert(0, f"{repo_path}/src" if repo_path else str(Path.cwd().parent / "src"))

from saturday_hq.config import config_from_widgets
from saturday_hq.transform.gold import build_gold_core

config = config_from_widgets(catalog=dbutils.widgets.get("catalog"))
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
