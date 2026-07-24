# Databricks notebook source
# MAGIC %md
# MAGIC # Step 7: Silver transforms

# COMMAND ----------

import sys
from pathlib import Path

dbutils.widgets.text("repo_path", "")
dbutils.widgets.text("catalog", "saturday_hq")

repo_path = dbutils.widgets.get("repo_path").strip()
sys.path.insert(0, f"{repo_path}/src" if repo_path else str(Path.cwd().parent / "src"))

from saturday_hq.config import config_from_widgets
from saturday_hq.transform.silver import build_all_silver

config = config_from_widgets(catalog=dbutils.widgets.get("catalog"))
results = build_all_silver(config)
display(spark.createDataFrame(results))

# COMMAND ----------

# Quick DQ checks
checks = [
    ("games unique", f"SELECT count(*) = count(DISTINCT game_id) AS ok FROM {config.silver('games')}"),
    ("completed have scores", f"""
        SELECT count(*) = 0 AS ok
        FROM {config.silver('games')}
        WHERE completed AND (home_points IS NULL OR away_points IS NULL)
    """),
    ("sp_plus seasons", f"SELECT min(season), max(season), count(*) FROM {config.silver('sp_plus')}"),
    ("ppa seasons", f"SELECT min(season), max(season), count(*) FROM {config.silver('ppa_teams')}"),
]
for name, sql in checks:
    print(name)
    display(spark.sql(sql))
