# Databricks notebook source
# MAGIC %md
# MAGIC # Step 6: Bronze from Volume
# MAGIC Reads historical (+ optional incremental) JSONL into `bronze.*` Delta tables.

# COMMAND ----------

import sys
from pathlib import Path

dbutils.widgets.text("repo_path", "")
dbutils.widgets.text("catalog", "saturday_hq")
dbutils.widgets.text("mode", "both")  # historical | incremental | both

repo_path = dbutils.widgets.get("repo_path").strip()
sys.path.insert(0, f"{repo_path}/src" if repo_path else str(Path.cwd().parent / "src"))

from saturday_hq.config import config_from_widgets
from saturday_hq.ingest.bronze_from_volume import load_all_bronze

config = config_from_widgets(catalog=dbutils.widgets.get("catalog"))
mode = dbutils.widgets.get("mode")

results = load_all_bronze(config, mode=mode)
display(spark.createDataFrame(results))
