# Databricks notebook source
# MAGIC %md
# MAGIC # Step 5: Download historical CFBD data into Volume
# MAGIC Writes JSONL under `/Volumes/<catalog>/bronze/cfbd_landing/historical/...`
# MAGIC Uses the API once for backfill; daily refresh uses the incremental path.

# COMMAND ----------

import sys
from pathlib import Path

dbutils.widgets.text("repo_path", "")
dbutils.widgets.text("catalog", "saturday_hq")
dbutils.widgets.text("secret_scope", "saturday_hq")
dbutils.widgets.text("secret_key", "cfbd_api_key")
dbutils.widgets.text("history_start_year", "2015")
dbutils.widgets.text("current_season", "2026")
dbutils.widgets.text("end_year", "")  # blank => current_season
dbutils.widgets.text("domains", "")  # blank => all HISTORICAL_DOMAINS

repo_path = dbutils.widgets.get("repo_path").strip()
sys.path.insert(0, f"{repo_path}/src" if repo_path else str(Path.cwd().parent / "src"))

from saturday_hq.config import HISTORICAL_DOMAINS, config_from_widgets
from saturday_hq.cfbd_client import CFBDClient
from saturday_hq.ingest.download_historical import download_historical_to_volume

config = config_from_widgets(
    catalog=dbutils.widgets.get("catalog"),
    history_start_year=int(dbutils.widgets.get("history_start_year")),
    current_season=int(dbutils.widgets.get("current_season")),
    secret_scope=dbutils.widgets.get("secret_scope"),
    secret_key=dbutils.widgets.get("secret_key"),
)

end_year_raw = dbutils.widgets.get("end_year").strip()
end_year = int(end_year_raw) if end_year_raw else config.current_season
domains_raw = dbutils.widgets.get("domains").strip()
domains = [d.strip() for d in domains_raw.split(",") if d.strip()] or list(HISTORICAL_DOMAINS)

api_key = dbutils.secrets.get(config.secret_scope, config.secret_key)
client = CFBDClient(api_key, config)

# COMMAND ----------

# Optional: smoke-test one year before full backfill
smoke = download_historical_to_volume(
    client,
    config,
    years=[config.history_start_year],
    domains=["teams_fbs", "games", "sp_plus"],
)
display(spark.createDataFrame(smoke))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Full historical backfill
# MAGIC This can take a while (many seasons × domains). Re-run safe: files overwrite per domain/year.

# COMMAND ----------

manifest = download_historical_to_volume(
    client,
    config,
    start_year=config.history_start_year,
    end_year=end_year,
    domains=domains,
)
manifest_df = spark.createDataFrame(manifest)
display(manifest_df.orderBy("domain", "year"))
print("errors:", manifest_df.filter("error is not null").count())
print("historical root:", config.historical_path)
