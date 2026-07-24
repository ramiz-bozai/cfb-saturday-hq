# Saturday HQ

FBS college football intelligence on Databricks using [CollegeFootballData](https://collegefootballdata.com/).

## What it is
- Historical CFBD data downloaded into a Unity Catalog **Volume**, then loaded to bronze
- Daily **API** refresh into Volume `incremental/`
- Silver/gold marts with **SP+** and **PPA** as first-class metrics
- Matchup model that does **not** train on betting lines
- UI compares **model vs market**
- Preseason + Monte Carlo playoff projections using published **2026 CFP** structure
- Dashboards, Genie, and a Streamlit Databricks App

## Start here
1. Read `DECISIONS.md`
2. Follow `docs/STEP_BY_STEP.md` in order
3. Paste `docs/GENIE_INSTRUCTIONS.md` into your Genie space

## Layout
```
cfb-saturday-hq/
  app/                 # Databricks App (Streamlit)
  docs/                # Step-by-step + Genie instructions
  notebooks/           # Run these in order (00 → 07)
  resources/           # Databricks Asset Bundle jobs
  sql/                 # UC bootstrap + metric notes
  src/saturday_hq/     # Python package used by notebooks
```

## Quick command reminders
```bash
cd /Users/ramiz.bozai/cfb-saturday-hq
databricks secrets create-scope saturday_hq
databricks secrets put-secret saturday_hq cfbd_api_key
databricks bundle deploy -t dev   # after setting workspace host
```
