# Saturday HQ — exact step-by-step guide

Run commands from the repository root unless a step explicitly says to enter a subdirectory.

Decisions are locked in `DECISIONS.md`.
This guide tells you **exactly what to do**, in order, and which file to run.

## Conventions used everywhere

- Catalogs: `cfb_saturday_hq_dev` and `cfb_saturday_hq_prod` for the medallion, plus
`cfb_saturday_hq_raw` for the shared landing volume
- Schemas (in each environment catalog): `cfb_bronze`, `cfb_silver`, `cfb_gold`, `cfb_ml`, `cfb_app`
- Landing volume: `/Volumes/cfb_saturday_hq_raw/landing/cfbd_landing` — **one copy, shared**
- Secret scope / key: `cfb_saturday_hq` / `cfbd_api_key`
- **The environment is picked for you.** `SATURDAY_HQ_ENV` on a job cluster selects
`cfb_saturday_hq_<env>` for the Python steps, and the dbt tasks get a matching `--target`;
both come from the bundle target (`-t dev` / `-t prod`). An interactive notebook run with no
variable set writes to dev. Every notebook prints its env and catalog in the first cell.
- **No notebook widgets.** Each notebook has a block of constants at the top
(`REPO_PATH`, `CURRENT_SEASON`, etc.). Edit those in place.
- **Season is derived from today's date; you never edit it between runs.** CFBD labels a
season by its starting year, so the rollover is in August: runs before August target the
last completed season, runs from August onward target the new one. `CURRENT_SEASON = None`
in every notebook means "derive it" (`current_cfb_season()` in `src/saturday_hq/config.py`).
Set it to an int only to pin a specific season for a one-off run.
- **Every run after the first backfill is incremental for that derived season.** The refresh
notebook pulls the season into a new `incremental/dt=YYYY-MM-DD/` drop, and dbt reads the
backfill plus every drop, keeping the newest copy of each row.
- Defaults for all of the above live in `src/saturday_hq/config.py`.



## Where data lives

Raw CFBD files are **not** part of either environment. They land once in
`cfb_saturday_hq_raw.landing.cfbd_landing`, and dev and prod each build their own
bronze → silver → gold from that same copy:

```
                          ┌─ cfb_saturday_hq_dev  (bronze → silver → gold)
cfb_saturday_hq_raw  ─────┤
  landing.cfbd_landing    └─ cfb_saturday_hq_prod (bronze → silver → gold)
```

So the CFBD API is only ever called once, the medallion stays strict inside each catalog, and
dev is guaranteed to be reading exactly what prod reads. Bronze is *not* shared, because it is
code output like everything else — you want to be able to change a bronze projection in dev
without touching prod.

## Who transforms what

**Every transformation is dbt.** Python only handles the two ends of the pipeline.


| Stage                   | Tool                   | Where                          |
| ----------------------- | ---------------------- | ------------------------------ |
| CFBD API → Volume JSONL | Python                 | `notebooks/01`, `notebooks/04` |
| Volume → bronze         | **dbt** (`read_files`) | `dbt/models/bronze/`           |
| bronze → silver         | **dbt**                | `dbt/models/silver/`           |
| silver → gold           | **dbt**                | `dbt/models/gold/`             |
| Train + score           | Python                 | `notebooks/02`                 |
| Playoff sims + briefs   | Python                 | `notebooks/03`                 |


dbt model names are prefixed by layer, and each one is aliased to a clean table name:
`bronze_games` → `cfb_bronze.games`, `silver_games` → `cfb_silver.games`,
`gold_team_week` → `cfb_gold.team_week`.

**One handoff in each direction, and no dbt work after the return to Python:**

```
Python ingest  →  dbt build  →  Python score + serve
```

`cfb_gold.matchup_card` is the one gold relation that needs the model's output, and it is a
dbt **view** for exactly that reason: dbt defines it during the transformation step, and it
reflects each new scoring run with no second dbt call. `cfb_gold.game_predictions` is a dbt
**source** (Python writes it); notebook 00 creates it empty so the view can exist from day one.

---



# Part 1 — One-time prep



## Prep 1 — Get a CFBD API key

1. Open [https://collegefootballdata.com/key](https://collegefootballdata.com/key)
2. Request a free API key and copy it.
3. Keep it somewhere temporary; you will store it in Databricks Secrets next (do not commit it to git).

**Done when:** you have an API key string.

---



## Prep 2 — Put the project in Databricks

Pick one approach.

### Option A (recommended): Databricks Git folder

1. Create a GitHub/GitLab repo from your local repository folder (or sync manually).
2. In Databricks: **Repos** → **Add** → **Git folder** → clone the repo.
3. Note the workspace path, e.g. `/Workspace/Users/you@company.com/cfb-saturday-hq`.



### Option B: Upload / Bundle sync

```bash
cd /path/to/cfb-saturday-hq
# set host in databricks.yml or via DATABRICKS_HOST / profile
databricks bundle deploy -t dev
```

**Done when:** you can see `notebooks/`, `dbt/`, `src/`, `app/` in the workspace.

---



## Prep 3 — Create the Databricks secret

In a terminal with Databricks CLI authenticated:

```bash
databricks secrets create-scope cfb_saturday_hq
databricks secrets put-secret cfb_saturday_hq cfbd_api_key
# paste API key when prompted
```

**Done when:** `databricks secrets list-secrets cfb_saturday_hq` shows `cfbd_api_key`.

---



## Prep 4 — Point dbt at your workspace

`dbt/profiles.yml` is committed, so there is no file to create — only a warehouse to name
and a token to supply locally.

1. Fill in `http_path` in `dbt/profiles.yml` (and `host`, if it is not this workspace).
  It comes from **SQL Warehouses** → your warehouse → *Connection details*.
2. Set up the local environment:
  ```bash
   cd /path/to/cfb-saturday-hq
   python3.13 -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt        # includes dbt-databricks
   cp .env.template .env                  # fill in DBT_ACCESS_TOKEN
  ```
3. Load it and verify, every session:
  ```bash
   source .venv/bin/activate
   set -a && source .env && set +a
   cd dbt && dbt debug
  ```

No `--profiles-dir` and no `DBT_PROFILES_DIR`: dbt looks next to `dbt_project.yml`, which is
where the profile lives. The `set -a` wrapper matters, because `.env` is plain `KEY=value`
lines with no `export`; without it dbt fails with
`Parsing Error: Env var required but not provided: 'DBT_ACCESS_TOKEN'`.

The profile has two targets that differ only by catalog — `dev` →`cfb_saturday_hq_dev`,
`prod` → `cfb_saturday_hq_prod` — so fill in `http_path` for both. `dbt build` uses dev; the
jobs run `dbt build --target prod`. The per-layer schemas come from `dbt/dbt_project.yml`, so
models land in `cfb_bronze` / `cfb_silver` / `cfb_gold` inside whichever catalog is targeted,
with no name mangling (`dbt/macros/generate_schema_name.sql` enforces that).

On Databricks, both jobs run dbt as a **dbt task** against this same committed profile, and
Databricks injects `DBT_ACCESS_TOKEN` for the job's *Run As* principal. Nothing extra to
configure, and no notebook ever installs or invokes dbt.

**Done when:** `dbt debug` reports all checks passed.

---



# Part 2 — Pipeline, in run order

Each notebook starts with a constants block. `REPO_PATH` should point at the folder that
contains `src/` (blank tries to auto-detect from the working directory).

## Step 1 — Notebook `00_setup.py` (UC + Volume)

Constants: `REPO_PATH`, `HISTORY_START_YEAR`, `CURRENT_SEASON`, `SETUP_ENVIRONMENTS`,
`SECRET_SCOPE`, `SECRET_KEY`

One run sets up **both** environments. What it does:

- creates catalog `cfb_saturday_hq_raw` with schema `landing` and volume `cfbd_landing`
- creates volume folders `historical/`, `incremental/`, `manual/`
- for each env in `SETUP_ENVIRONMENTS`, creates catalog `cfb_saturday_hq_<env>` and schemas
`cfb_bronze/cfb_silver/cfb_gold/cfb_ml/cfb_app`
- verifies secret access
- creates `cfb_gold.game_predictions` empty **in each environment**, so the `matchup_card`
view can be created before a model has ever been trained
- seeds `cfb_app.demo_profiles` in each environment

The schemas must exist before dbt runs; dbt writes tables into them but does not create them.

**Done when:** both catalogs and the shared volume path print, and demo profiles display.

---



## Step 2 — Notebook `01_download_historical_to_volume.py` (API → Volume)

Constants: `REPO_PATH`, `HISTORY_START_YEAR`, `CURRENT_SEASON`, `END_YEAR`, `DOMAINS`, secrets

1. Run the **smoke test** cell first (start year, teams/games/sp_plus only).
2. Confirm files exist under
  `/Volumes/cfb_saturday_hq_raw/landing/cfbd_landing/historical/`
3. Run the **full backfill** cell.

Code that runs: `src/saturday_hq/ingest/download_historical.py`

Files land as `historical/<domain>/year=YYYY/<domain>.jsonl`, which is exactly the glob the
dbt bronze models read.

The backfill ends at the derived season, so a run before August stops at the last completed
season. Set `END_YEAR` to the upcoming year if you also want its schedule loaded early for
preseason projections. This is a one-time step — after it, Step 6 keeps things current
incrementally, so you do not re-run the backfill each season.

Domains written:
`teams_fbs`, `conferences`, `games`, `team_season_stats`, `sp_plus`, `ppa_teams`, `ppa_games`, `talent`, `recruiting_teams`, `rankings`, `lines`

**Done when:** manifest shows rows for core domains across seasons and `error` count is acceptable (some early-year gaps are normal).

---



## Step 3 — dbt: bronze → silver → gold

First build only — no incremental drop exists yet:

```bash
cd /path/to/cfb-saturday-hq/dbt
dbt build --vars '{include_incremental: false}'
```

Every build after that:

```bash
# Before notebook 04 has written the first valid incremental drop:
dbt build --vars '{include_incremental: false}'                  # dev
dbt build --target prod --vars '{include_incremental: false}'    # prod

# After notebook 04 has written the first valid incremental drop:
dbt build                  # dev
dbt build --target prod    # prod / what the scheduled job runs
```

Both targets read the same shared volume and differ only in which catalog they write to, so
you can build dev, eyeball it, and then run the identical command against prod.

`include_incremental` describes the shared raw Volume, not whether the target catalog already
exists. Keep it `false` until `incremental/` contains real JSONL for every bronze domain. A
`read_files()` glob with no matching records has no inferred columns, so every projection fails
with misleading errors such as `season cannot be resolved`.

`dbt build` runs models **and** their tests, which is where the data-quality checks live:
unique/not-null keys, one row per team-season in SP+/PPA, one row per game+provider in
`lines_all`, complete non-null contracts for current lines, moneylines, and opening lines,
one row per team-week in `team_week`, and completed games always having both scores.

What gets created:


| Layer        | Tables                                                                                                                                           |
| ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| `cfb_bronze` | `games`, `teams_fbs`, `conferences`, `sp_plus`, `ppa_teams`, `ppa_games`, `talent`, `recruiting_teams`, `rankings`, `lines`, `team_season_stats` |
| `cfb_silver` | `games`, `teams`, `team_seasons`, `conferences`, `sp_plus`, `ppa_teams`, `ppa_games`, `lines`, `lines_all`, `moneylines`, `opening_lines`, `rankings`, `talent`, `recruiting_teams` |
| `cfb_gold`   | `team_week`, `game_features`, `matchup_card` (view)                                                                                              |


How the layers differ:

- **bronze** — `read_files()` over the Volume, camelCase JSON fields renamed and cast,
nested structs flattened (`offense.rating` → `sp_offense`). `lines` and `polls` stay as
arrays here. Each row keeps `_source_path`, `_ingest_mode`, `_ingested_at`.
- **silver** — canonical conference names, dedupe on natural keys, FBS filtering, derived
outcome columns, and the array explodes (`lines_all`, `rankings`). Market quotes then split by
contract: complete current spread/total (`lines`), same-provider two-way prices (`moneylines`),
and complete opening spread/total (`opening_lines`).
- **gold** — `team_week` (as-of form + season SP+/PPA/talent/recruiting), `game_features`
(one row per FBS-vs-FBS game, both sides joined as-of so a game is never described with
form recorded after it was played), and the `matchup_card` view.

Market lines are stored on `game_features` for the model-vs-market UI. They are **not**
model inputs; `FEATURE_COLS` in `src/saturday_hq/ml/train.py` excludes them.

**How re-running stays correct.** Because bronze reads the backfill *and* every incremental
drop, the same game shows up several times — scheduled in one drop, final in a later one.
Each silver dedupe keeps the newest copy: incremental beats historical, and a later
`dt=YYYY-MM-DD` beats an earlier one (`latest_ingest_first()` in
`dbt/macros/cfbd_landing.sql`). That is why you never have to clear anything out between
runs, and why the `_source_path` / `_ingest_mode` lineage columns are carried into silver.

Two dbt vars matter (`dbt/dbt_project.yml`):

- `landing_root` — Volume path the bronze models glob. Not per-environment: both targets read
`cfb_saturday_hq_raw`, which is what guarantees dev and prod see identical inputs.
- `include_incremental` — `true` by default, which is the steady state. Set it to `false`
only for the very first build, before any `incremental/dt=.../` drop exists, because
`read_files` errors on a glob that matches no files. It tracks the shared volume, not the
environment, so once a weekly refresh has run neither target needs it again.

**Done when:** `dbt build` reports PASS for all models and tests, and
`cfb_gold.game_features` has rows with `sp_overall_diff`, `ppa_offense_diff`, `market_spread`.

Useful variants:

```bash
dbt build --select silver_games+          # a model and everything downstream
dbt build --select tag:bronze             # one layer
dbt test --select silver_games            # tests only
dbt docs generate && dbt docs serve       # lineage graph
```

---



## Step 4 — Notebook `02_train_and_score.py` (no lines as features)

Constants: `REPO_PATH`, `ENV`, `CURRENT_SEASON`, `MODEL_NAME`

1. Run training cell → MLflow run + registered model `<catalog>.cfb_ml.matchup`
2. Run scoring cell → `cfb_gold.game_predictions`

Code: `src/saturday_hq/ml/train.py`

Feature list is SP+/PPA/talent/form/neutral only (`FEATURE_COLS`).

The model is registered in **Unity Catalog**, so it follows the environment like the tables do:
dev training writes `cfb_saturday_hq_dev.cfb_ml.matchup` and never touches prod's model. In the
model UI you can assign the alias `production` to the best version; scoring uses
`models:/<name>@production` and falls back to the newest version when no alias is set, so a
fresh environment works before anyone promotes anything.

The last cell displays `cfb_gold.matchup_card`. **No dbt run is needed here** — the card is a
view, so the probabilities you just wrote are already visible through it.

**Done when:** `matchup_card` shows `model_home_win_prob` beside
`market_home_win_prob_implied` and `model_minus_market_home`.

---



## Step 5 — Notebook `03_projections_and_briefs.py`

Constants: `REPO_PATH`, `ENV`, `CURRENT_SEASON`, `N_SIMS`, `RANDOM_SEED`, `SEASON_TYPES`, `WEEK`

Creates:

- `cfb_gold.preseason_team_ratings`
- `cfb_gold.season_projections`
- `cfb_gold.playoff_projections`
- `cfb_gold.weekly_brief`

`WEEK = None` generates every week in `SEASON_TYPES`; the default tuple refreshes both regular and
postseason without mixing their overlapping week numbers. Set an integer only for a targeted
repair. Brief grain is `game_id + team`, so each matchup yields home- and away-perspective rows.
Each write replaces only the requested season/type (or week), preserving every other historical
brief. The first run after the schema upgrade reconstructs all available history from
`matchup_card`.

The simulator prints input counts, 10% progress updates, and read/simulate/write timings. It
vectorizes remaining-game draws and reuses completed results. If no rated games remain, it
automatically reduces `N_SIMS` to one deterministic pass. Keep `N_SIMS = 2000` for in-season
uncertainty; `RANDOM_SEED = 42` makes identical inputs produce identical projections.

CFP logic code: `src/saturday_hq/cfp_rules.py`
Simulator: `src/saturday_hq/projections/simulator.py`
Briefs: `src/saturday_hq/briefs/generate.py`

Briefs read `cfb_gold.matchup_card`, so Step 4 has to succeed first.

Sources encoded for the 2026 structure:

- [https://collegefootballplayoff.com/sports/2024/5/29/12-team-format.aspx](https://collegefootballplayoff.com/sports/2024/5/29/12-team-format.aspx)
- NCAA AQ explainers for 2026 Power4 + G6 + Notre Dame rules

**Done when:** playoff odds board displays with disclaimer.

---



## Step 6 — The repeating loop (notebook 04 → dbt task → notebook 05)

The weekly refresh is three job tasks, one handoff each way — the same shape as the backfill
job:


| Task              | Tool                                              | What it does                                                             |
| ----------------- | ------------------------------------------------- | ------------------------------------------------------------------------ |
| `ingest`          | Python — `notebooks/04_weekly_ingest.py`          | API pull for the derived season into Volume `incremental/dt=YYYY-MM-DD/` |
| `dbt_transform`   | **dbt task** — `dbt build`                        | bronze → silver → gold                                                   |
| `score_and_serve` | Python — `notebooks/05_weekly_score_and_serve.py` | score the slate, then ratings / playoff sims / briefs                    |


Constants in 04: `REPO_PATH`, `MODE`, `CURRENT_SEASON`, `WEEK`, `FORCE_OUT_OF_SEASON`,
secrets. There is no `ENV` here — the ingest writes to the shared raw volume, so it is the
same work no matter which environment consumes it.
Constants in 05: `REPO_PATH`, `ENV`, `CURRENT_SEASON`, `MODEL_NAME`, `SEASON_TYPES`, `WEEK`,
`N_SIMS`, `RANDOM_SEED`. `WEEK = None` refreshes all regular and postseason weeks while preserving
prior seasons.

**Nothing in here needs editing between runs.** The season comes from today's date, the pull
always targets that season, and dbt reads the newest drop automatically. Re-running the same
day is safe: the drop overwrites and the silver dedupes keep the latest copy.

### How many CFBD calls a run spends

Notebook 04 does not pull all 11 domains every time — calls are the scarce resource. It prints
the exact domain list and call count it decided on before pulling anything:

| Tier                                                | Fetched                                | Calls |
| --------------------------------------------------- | -------------------------------------- | ----- |
| weekly: games, sp_plus, ppa_teams, ppa_games, rankings, team_season_stats, lines | every Monday run | 7–9 |
| season-static: teams_fbs, talent, recruiting_teams   | first in-season run of a season         | +3    |
| static: conferences                                  | once ever, if absent from `incremental/` | +1    |
| market: lines                                        | the Friday job (`MODE = "market"`)      | 1–2   |

Three further guards: the notebook exits early from February through July, `games` and `lines`
skip their postseason call until December (nothing is scheduled before then), and `WEEK` stays
`None` because narrowing to one week costs the same single call while losing late score
corrections.

Season-static domains are tracked by a marker file at
`incremental/_state/season_static_<season>.json`. Delete it to force a re-pull; it is only
written when all three succeeded, so a partial failure retries next week.

dbt runs as its own Job task, not from a notebook, so neither notebook installs dbt. To do a
manual end-to-end pass, run notebook 04, then `dbt build` from your laptop (or *Run now* on
the job), then notebook 05.

Do that once after Step 5 succeeds, then schedule the job (below).

**Done when:** notebook 05 prints `daily refresh complete for season <year>` and matchup
cards update.

---



# Part 3 — Surfaces and scheduling



## Dashboard + Genie (manual UI steps)



### Dashboard

1. Databricks → **Dashboards** → create new AI/BI dashboard.
2. Datasets should query **gold only**, for example:
  - SP+/PPA leaders from `cfb_gold.team_week`
  - Schedule strength from `cfb_gold.game_features`
  - Model vs market from `cfb_gold.matchup_card`
3. Add the market + CFP disclaimers from `DECISIONS.md` as text widgets.



### Genie (Season Preview)

1. Use the Season Preview Genie space/agent (configured via `GENIE_SPACE_ID` in `app/app.yaml`).
2. Build skeleton rows: `dbt run --select app_genie_team_briefs --target prod`
3. Fill briefs: `cd app && node scripts/warm_genie_briefs.js` (needs Genie API access + MODIFY on `cfb_app.genie_team_briefs`)
4. Team page shows stored briefs under the hero; **Ask Genie** chats live against the same space.

**Done when:** a team page shows a Genie bottom-line brief and Ask Genie answers a portal/continuity question.

---



## Schedule the refresh

Job definitions: `resources/jobs.yml`

- `saturday-hq-weekly-refresh-<env>` → `04` → dbt (`dbt build --target <env>`) → `05`, on one
shared job cluster. **Mondays 10:00 America/New_York, PAUSED.** Monday is the point where the
weekend is fully settled: all games final, SP+ and PPA re-published.
- `saturday-hq-market-refresh-<env>` → `04` (with `SATURDAY_HQ_INGEST_MODE=market`) → dbt.
**Fridays 10:00 America/New_York, PAUSED.** Lines only, 1–2 calls, so the slate shows the
current market before kickoff. There is no `05` task because the model excludes lines from its
features — predictions, ratings and sims cannot move, only the market columns on
`gold_game_features` and the `matchup_card` view. Weekly briefs therefore keep Monday's
market snapshot; add `05` to this job if you would rather they follow Friday's line.
- `saturday-hq-historical-backfill-<env>` → the one-time chain:
`01` → dbt (`--vars '{include_incremental: false}'`) → `02` → `03`.

There is deliberately no daily job. Games are weekly, so a daily pull spent ~13 calls a day
re-downloading data that had not changed.

Both dbt tasks use the committed `dbt/profiles.yml` and carry **no** `warehouse_id`,
`catalog`, or `schema` — see Prep 4. The warehouse comes from `http_path` in the profile,
so that is the one value to fill in before deploying.

The bundle target sets both halves of the environment: `SATURDAY_HQ_ENV` on the job cluster
for the Python tasks and `--target` for the dbt task. Job names carry the suffix so a dev and
a prod deployment can coexist in one workspace.

1. Deploy the jobs: `databricks bundle deploy -t dev`, and `-t prod` when you are ready.
2. Keep both schedules **PAUSED** until Steps 4–5 succeed once.
3. Then unpause. From then on the season rolls over on its own in August, so the job keeps
  working across seasons without edits.

**Done when:** the job exists and a manual test run works after model training.

---



## Deploy the App

App code: `app/` (React client under `app/client/`, Express API under `app/server/`)
App config: `app/app.yaml` (Node: `npm run start`)

1. Databricks → **Compute** → **Apps** → Create app (Node / custom)
2. Add a **SQL warehouse** resource with key `sql-warehouse` and **Can use** permission.
   `app.yaml` maps that resource to `DATABRICKS_WAREHOUSE_ID`.
3. Point the deployment at the `app/` folder. It contains its own `app.yaml` and
   `package.json`; the repository-root Python `requirements.txt` is intentionally not
   what the App installs.
4. Grant the app identity `USE CATALOG`, `USE SCHEMA`, and `SELECT` on:
  - `cfb_saturday_hq_prod.cfb_gold.*`
  - `cfb_saturday_hq_prod.cfb_app.demo_profiles`
5. `app.yaml` sets `SATURDAY_HQ_CATALOG=cfb_saturday_hq_prod`,
  `SATURDAY_HQ_GOLD_SCHEMA=cfb_gold`, and `SATURDAY_HQ_APP_SCHEMA=cfb_app`. The App serves
   prod; point the catalog at `cfb_saturday_hq_dev` in a second app if you want a dev preview.
6. Deploy and start the app. Locally: `cd app && npm install && npm run dev` with
   `DATABRICKS_HOST`, `DATABRICKS_HTTP_PATH`, and `DATABRICKS_TOKEN` (or `DBT_ACCESS_TOKEN`)
   in the repo `.env`.

See also `docs/APP_DEPLOYMENT.md`.

## Season Preview ingest

For the **Season Preview** tab (roster continuity / portal / QB rooms):

1. Run `notebooks/06_preview_ingest.py` on Databricks (or locally
   `PYTHONPATH=src python scripts/sync_preview_domains.py`).
2. It pulls the upcoming season (July → calendar year, e.g. 2026) plus the prior season’s
   production domains into `incremental/dt=YYYY-MM-DD/`.
3. Build player models:

```bash
cd dbt
dbt build --target prod --select bronze_rosters+ bronze_player_portal+ bronze_player_returning+ bronze_player_usage+ bronze_player_season_stats+ bronze_ppa_players_season+ bronze_recruiting_players+ bronze_draft_picks+ bronze_nfl_udfa+
```

CFBD often has no published roster for the upcoming season until near camp. Season Preview then
**constructs** the roster from the prior season plus portal arrivals/departures, and
**subtracts NFL exits**: drafted players from CFBD `/draft/picks` plus undrafted free agents
from nflverse (landed under `manual/nfl_udfa/`, matched to CFBD `athlete_id` via prior roster
name + college). Year N exits college season N. Residual gap: UDFAs that do not uniquely
match a prior FBS roster row.

Job: `saturday-hq-preview-refresh-${env}` in `resources/jobs.yml`.

Screens: Home, Slate (model vs market), Matchup, Projections, Brief, **Season Preview**.
Season Preview defaults to the upcoming year before August (July 2026 → 2026).

**Done when:** you can click profile → slate → matchup → brief without errors.

---



## Demo hardening checklist

1. Run the weekly job once manually end-to-end (`04` → dbt → `05`).
2. Unpause the weekly and market jobs.
3. Walk the 10-minute script:
  - Dashboard history (SP+/PPA)
  - Season projections
  - Slate model vs market
  - Genie question
  - App brief for a demo profile
4. Confirm both disclaimers are visible in App and Dashboard.
5. Confirm Genie refuses betting-advice prompts.

**Done when:** you can repeat the demo twice without fixing data live.

---



## File map (quick)


| Stage                             | Run this                                        | Code                                                             |
| --------------------------------- | ----------------------------------------------- | ---------------------------------------------------------------- |
| Setup                             | `notebooks/00_setup.py`                         | `config.py`                                                      |
| Historical Volume load            | `notebooks/01_download_historical_to_volume.py` | `ingest/download_historical.py`, `cfbd_client.py`                |
| Bronze                            | `dbt build`                                     | `dbt/models/bronze/`, `dbt/macros/cfbd_landing.sql`              |
| Silver                            | `dbt build`                                     | `dbt/models/silver/`, `dbt/macros/cfb_metrics.sql`               |
| Gold                              | `dbt build`                                     | `dbt/models/gold/`                                               |
| Model + predictions               | `notebooks/02_train_and_score.py`               | `ml/train.py`                                                    |
| Matchup card (view, no extra run) | —                                               | `dbt/models/gold/gold_matchup_card.sql`                          |
| Projections/briefs                | `notebooks/03_projections_and_briefs.py`        | `projections/simulator.py`, `cfp_rules.py`, `briefs/generate.py` |
| Weekly ingest                     | `notebooks/04_weekly_ingest.py`                 | `ingest/download_historical.py` (`plan_domains`)                 |
| Weekly score + serve              | `notebooks/05_weekly_score_and_serve.py`        | `ml/train.py`, `projections/simulator.py`, `briefs/generate.py`  |
| dbt connection                    | `dbt/profiles.yml` (committed)                  | `.env.template` → `.env` for `DBT_ACCESS_TOKEN`                  |
| App                               | `cd app && npm run start`                       | `app/server/`, `app/client/`                                     |
| Genie (Season Preview)            | `app/scripts/warm_genie_briefs.js`              | `dbt/models/app/app_genie_team_briefs.sql`, `GENIE_SPACE_ID`     |


---



## If something fails

- **Secret not found:** rerun Prep 3; `SECRET_SCOPE` / `SECRET_KEY` in the notebook must match the scope you created.
- **Import errors for** `saturday_hq`**:** set `REPO_PATH` to the folder that contains `src/`.
- **dbt** `Runtime Error ... profiles.yml`**:** run dbt from the `dbt/` folder — that is where the
committed profile lives.
- `Env var required but not provided: 'DBT_ACCESS_TOKEN'`**:** load your `.env` with
`set -a && source .env && set +a` (Prep 4). On a job, this means the task has a
`warehouse_id` set, which makes Databricks generate its own profile instead of injecting
the token for ours — remove it.
- **dbt writes to** `cfb_silver_cfb_bronze` **style schemas:** `dbt/macros/generate_schema_name.sql`
is missing or was renamed; it is what suppresses dbt's default schema concatenation.
- `PATH_NOT_FOUND` **/ no files matched in a bronze model:** the Volume glob found nothing.
On a first build pass `--vars '{include_incremental: false}'`; otherwise confirm Step 2
wrote `historical/<domain>/year=YYYY/<domain>.jsonl`.
- `gold_matchup_card` **fails on a missing relation:** `cfb_gold.game_predictions` does not
exist. Re-run the last cells of Notebook 00.
- **Wrong season targeted:** the season rolls over in August. Pin `CURRENT_SEASON` to an int
in the notebook to override for a one-off run.
- **Wrote to the wrong environment:** every notebook prints `env:` and `catalog:` in its first
cell. An interactive run defaults to dev; a job takes `SATURDAY_HQ_ENV` from its cluster. Set
the `ENV` constant to `"dev"` or `"prod"` to force one. For dbt it is `--target`.
- **Table or model missing in one environment only:** each environment is built independently.
Run `dbt build --target <env>` and, for predictions, notebook 02 with that `ENV`.
- **Empty SP+/PPA:** check bronze row counts for that year; CFBD may lack some seasons/domains, and a season that has not started yet has no ratings.
- **A bronze column does not exist:** CFBD renamed a field. Fix the projection in the one
`dbt/models/bronze/bronze_<domain>.sql` file, then `dbt build --select bronze_<domain>+`.
- **Model registration permissions:** need permission to create registered models in the workspace.
- **App cannot read tables:** grant SELECT on catalog/schema to the app service principal.

