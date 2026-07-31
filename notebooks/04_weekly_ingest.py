# Databricks notebook source
# MAGIC %md
# MAGIC # 04 — Weekly ingest
# MAGIC
# MAGIC First leg of the refresh loop: pull the current season's CFBD snapshot into Volume
# MAGIC `incremental/dt=YYYY-MM-DD/`.
# MAGIC
# MAGIC **CFBD calls are the scarce resource here, so this notebook pulls the smallest correct
# MAGIC set rather than every domain.** `plan_domains()` decides:
# MAGIC
# MAGIC | Tier | Domains | When |
# MAGIC |---|---|---|
# MAGIC | weekly | games, sp_plus, ppa_teams, ppa_games, rankings, team_season_stats, lines | every Monday run |
# MAGIC | season-static | teams_fbs, talent, recruiting_teams | first in-season run of a season |
# MAGIC | static | conferences | once ever, if absent from `incremental/` |
# MAGIC | market | lines | the Friday run (`MODE = "market"`) |
# MAGIC | preview | player domains (rosters, portal, usage, …) | Season Preview — use notebook 06 |
# MAGIC
# MAGIC Three further savings: nothing is called outside the August→January window, the
# MAGIC postseason endpoints are skipped until December (they have nothing to return before
# MAGIC bowls are announced), and the pull stays season-wide rather than week-scoped because
# MAGIC narrowing to a week costs the same one call while losing late score corrections.
# MAGIC
# MAGIC The landing volume is **shared by every environment** (`cfb_saturday_hq_raw.landing`),
# MAGIC so this notebook has no environment to pick: it calls the API once and both dev and
# MAGIC prod build their own bronze → silver → gold from the same files.
# MAGIC
# MAGIC The `saturday-hq-weekly-refresh` job runs three tasks in a row, the same
# MAGIC Python → dbt → Python handoff the backfill job uses:
# MAGIC
# MAGIC 1. this notebook
# MAGIC 2. a **dbt task** — bronze → silver → gold
# MAGIC 3. `05_weekly_score_and_serve.py`
# MAGIC
# MAGIC Nothing here needs editing between runs: the season is derived from today's date.

# COMMAND ----------

import sys
from pathlib import Path

# Edit these constants if needed (no notebook widgets).
REPO_PATH = ""
MODE = ""  # blank => SATURDAY_HQ_INGEST_MODE from the job cluster, else "weekly"
CURRENT_SEASON = None  # None => derived from today's date (August rollover)
WEEK = None  # None => season-wide pull (same call cost, keeps late corrections)
FORCE_OUT_OF_SEASON = False  # True => pull even in the offseason
SECRET_SCOPE = "cfb_saturday_hq"
SECRET_KEY = "cfbd_api_key"

repo_root = Path(REPO_PATH.strip()) if REPO_PATH.strip() else Path.cwd().parent
sys.path.insert(0, str(repo_root / "src"))

from saturday_hq.config import (
    SaturdayHQConfig,
    current_cfb_season,
    current_ingest_mode,
    in_season,
    season_types_for,
)
from saturday_hq.cfbd_client import CFBDClient
from saturday_hq.ingest.download_historical import (
    download_incremental_to_volume,
    mark_season_static_done,
    plan_domains,
)

config = SaturdayHQConfig(
    current_season=CURRENT_SEASON or current_cfb_season(),
    secret_scope=SECRET_SCOPE,
    secret_key=SECRET_KEY,
)
mode = current_ingest_mode(MODE)
season_types = season_types_for()
domains = plan_domains(config, season=config.current_season, mode=mode)

print("season:", config.current_season, "| mode:", mode)
print("shared landing volume:", config.volume_path)
print("season types:", season_types)
print(f"domains ({len(domains)}):", domains)

# COMMAND ----------

# Outside the season nothing has changed, so spending calls to re-download identical JSON is
# pure waste. The later tasks still run and simply rebuild from the newest existing drop.
if not in_season() and not FORCE_OUT_OF_SEASON:
    print("offseason — skipping the API pull (set FORCE_OUT_OF_SEASON = True to override)")
    dbutils.notebook.exit("skipped: offseason")

# COMMAND ----------

inc = download_incremental_to_volume(
    client=CFBDClient(dbutils.secrets.get(config.secret_scope, config.secret_key), config),
    config=config,
    year=config.current_season,
    domains=domains,
    week=WEEK,
    season_types=season_types,
)
display(spark.createDataFrame(inc))

# Stops next week's run from re-fetching teams/talent/recruiting for this season.
if mode == "weekly":
    mark_season_static_done(config, config.current_season, inc)

calls = sum(len(season_types) if d in ("games", "lines") else 1 for d in domains)
print(f"ingest complete for season {config.current_season} — {calls} CFBD calls")
print("dbt task runs next")
