# Saturday HQ

FBS college football intelligence on Databricks using [CollegeFootballData](https://collegefootballdata.com/).

## What it is
- Historical CFBD data downloaded into a Unity Catalog **Volume**, plus a daily **API** refresh into `incremental/`
- **dbt** owns every transformation: bronze (`read_files` over the Volume) → silver → gold
- Silver/gold marts with **SP+** and **PPA** as first-class metrics
- Matchup model that does **not** train on betting lines
- UI compares **model vs market**
- Preseason + Monte Carlo playoff projections using published **2026 CFP** structure
- Dashboards, Genie, and a Streamlit Databricks App

## Who does what
| Stage | Tool |
|---|---|
| CFBD API → Volume | Python (`notebooks/01`, `notebooks/04`) |
| Volume → bronze → silver → gold | **dbt** (`dbt/models/`) |
| Model training + scoring | Python (`notebooks/02`) |
| Playoff sims + weekly briefs | Python (`notebooks/03`) |

## Start here
1. Read `DECISIONS.md`
2. Follow `docs/STEP_BY_STEP.md` in order
3. Paste `docs/GENIE_INSTRUCTIONS.md` into your Genie space

## Layout
```
cfb-saturday-hq/
  app/                 # Databricks App (Streamlit)
  dbt/                 # dbt project: bronze/silver/gold models
  docs/                # Step-by-step + Genie instructions
  notebooks/           # Run these in order (00 → 04)
  resources/           # Databricks Asset Bundle jobs
  sql/                 # UC bootstrap + metric notes
  src/saturday_hq/     # Python package used by notebooks
```

## Quick command reminders
```bash
cd /Users/ramiz.bozai/cfb-saturday-hq
databricks secrets create-scope cfb_saturday_hq
databricks secrets put-secret cfb_saturday_hq cfbd_api_key
databricks bundle deploy -t dev   # after setting workspace host

# transformations (see dbt/profiles.yml.example first)
cd dbt
dbt build --exclude gold_matchup_card   # before scoring
dbt build --select gold_matchup_card    # after scoring
```
