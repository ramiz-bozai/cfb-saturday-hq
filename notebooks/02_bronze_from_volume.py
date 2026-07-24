# Databricks notebook source
# MAGIC %md
# MAGIC # 02 — Bronze from Volume
# MAGIC Reads historical (+ optional incremental) JSONL into `cfb_bronze.*` Delta tables.

# COMMAND ----------

import sys
from pathlib import Path

# Edit these constants if needed (no notebook widgets).
REPO_PATH = ""
MODE = "both"  # historical | incremental | both

if REPO_PATH.strip():
    sys.path.insert(0, f"{REPO_PATH.strip()}/src")
else:
    sys.path.insert(0, str(Path.cwd().parent / "src"))
    sys.path.insert(0, str(Path.cwd() / "src"))

from saturday_hq.config import SaturdayHQConfig
from saturday_hq.ingest.bronze_from_volume import load_all_bronze

config = SaturdayHQConfig()
results = load_all_bronze(config, mode=MODE)
display(spark.createDataFrame(results))
