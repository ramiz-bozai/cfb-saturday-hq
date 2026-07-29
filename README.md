# Saturday HQ

FBS college football intelligence on Databricks using [CollegeFootballData](https://collegefootballdata.com/).

## What it is
- Historical CFBD data downloaded into a Unity Catalog **Volume**, plus a **weekly API** refresh into `incremental/`
- **dbt** owns every transformation: bronze (`read_files` over the Volume) → silver → gold
- **dev and prod catalogs** for the medallion, over **one shared raw volume** — the API is called once
- Season is derived from the date (August rollover), so every run after the backfill is incremental for the current season with no edits
- Silver/gold marts with **SP+** and **PPA** as first-class metrics
- Matchup model that does **not** train on betting lines
- UI compares **model vs market**
- Preseason + Monte Carlo playoff projections using published **2026 CFP** structure
- Dashboards, Genie, and a Streamlit Databricks App

## Who does what
One handoff in each direction: `Python ingest → dbt build → Python score + serve`.

| Stage | Tool |
|---|---|
| CFBD API → Volume | Python (`notebooks/01`, `notebooks/04`) |
| Volume → bronze → silver → gold | **dbt** (`dbt/models/`, run as a Job dbt task) |
| Model training + scoring | Python (`notebooks/02`, `notebooks/05`) |
| Playoff sims + weekly briefs | Python (`notebooks/03`, `notebooks/05`) |

dbt never runs from inside a notebook. Both jobs are the same three-step shape — a Python
notebook, then a dbt task, then a Python notebook — so the handoffs are visible in the job
graph rather than buried in a subprocess call.

`cfb_gold.matchup_card` is a dbt **view** over the model's predictions, so no dbt run is
needed after scoring.

## Catalogs
| Catalog | Holds | Written by |
|---|---|---|
| `cfb_saturday_hq_raw` | `landing.cfbd_landing` volume: the CFBD JSONL files | the ingest notebooks, once |
| `cfb_saturday_hq_dev` | `cfb_bronze` → `cfb_silver` → `cfb_gold`, plus `cfb_ml` / `cfb_app` | local `dbt build`, interactive notebook runs |
| `cfb_saturday_hq_prod` | the same set | the scheduled jobs (`-t prod`) |

Raw files sit outside both environments on purpose: dev and prod each build their own bronze
from the identical inputs, so the medallion stays strict inside each catalog and CFBD is never
hit twice. Everything follows one variable — `SATURDAY_HQ_ENV` on the cluster for Python,
`--target` for dbt — both set from the bundle target.

## Refresh cadence and the CFBD call budget

CFBD calls are the scarce resource, so the schedule is built around them.

| Job | When | Pulls | Calls |
|---|---|---|---|
| `saturday-hq-weekly-refresh` | Monday 10:00 ET | games, sp_plus, ppa_teams, ppa_games, rankings, team_season_stats, lines | 7–9 |
| `saturday-hq-market-refresh` | Friday 10:00 ET | lines only | 1–2 |
| `saturday-hq-historical-backfill` | once, by hand | every domain, every season | ~145 |

Four things keep the weekly number down:

**Weekly, not daily.** Games are played weekly and every model input — scores, SP+, PPA — only
moves after they are played. Monday morning captures the entire weekend, late West Coast
finishes included. A daily schedule spent ~13 calls a day re-downloading identical JSON.

**Domains are tiered by how often they actually change.** `conferences` is fetched once, ever —
the check looks for a copy in the incremental tree only, because bronze unions a per-domain glob
over `incremental/` and `read_files()` fails on a glob matching zero files. That is a deliberate
invariant: the first in-season run of a season covers **all eleven domains** across the three
tiers, so every bronze model has something to read. `teams_fbs`, `talent` and
`recruiting_teams` are settled before kickoff, so they
are fetched on the first in-season run of a season — which lands after National Signing Day —
and a marker file at `incremental/_state/season_static_<season>.json` stops later runs from
repeating them. Only genuinely weekly domains run weekly. Tiers live in `config.py`;
`plan_domains()` applies them.

**No offseason calls.** `notebooks/04_weekly_ingest.py` exits early from February through July,
when nothing in college football changes.

**No pointless postseason calls.** `games` and `lines` cost one call *per season type*. Bowls
are not scheduled until December, so before then the refresh asks for `regular` only and skips
the second call.

One thing that looks like a saving but is not: scoping a pull to `week=N` instead of the whole
season. It is the same single request either way, and the season-wide pull is what lets a
corrected score or a rescheduled game land later. `WEEK` stays `None` on purpose.

## Start here
1. Read `DECISIONS.md`
2. Follow `docs/STEP_BY_STEP.md` in order
3. Paste `docs/GENIE_INSTRUCTIONS.md` into your Genie space

## Layout
```
cfb-saturday-hq/
  app/                 # Databricks App (Streamlit)
  dbt/                 # dbt project: models, macros, and the committed profiles.yml
  docs/                # Step-by-step + Genie instructions
  notebooks/           # Python steps, 00 → 05; dbt runs between 01/02 and between 04/05
  resources/           # Databricks Asset Bundle jobs
  sql/                 # UC bootstrap + metric notes
  src/saturday_hq/     # Python package used by notebooks
  .env.template        # local-only secrets checklist (copy to .env)
```

---

## How dbt works here

If you have not used dbt before: you write `SELECT` statements, and dbt wraps each one in the
`CREATE TABLE`/`CREATE VIEW` around it, works out what has to run before what, and runs the data
tests. There is no orchestration code in this repo because dbt derives it.

### The mental model

**One file is one relation.** `dbt/models/silver/silver_games.sql` is a single `SELECT`, and
building it creates `cfb_silver.games`. Model files are prefixed by layer so the folder and the
name agree; the relation they produce drops the prefix:

| Model file | Creates |
|---|---|
| `models/bronze/bronze_games.sql` | `cfb_bronze.games` |
| `models/silver/silver_games.sql` | `cfb_silver.games` |
| `models/gold/gold_team_week.sql` | `cfb_gold.team_week` |

The schema comes from the folder config in `dbt_project.yml` (`bronze: +schema: cfb_bronze`, and
so on). dbt normally *concatenates* that onto the profile's schema and would give you
`cfb_silver_cfb_bronze`; `macros/generate_schema_name.sql` overrides that so the folder's name is
used verbatim.

**Dependencies come from `ref()`, not from you.** When `silver_games` says
`{{ ref('bronze_games') }}`, that does two things at once: it prints the real table name into the
compiled SQL, and it tells dbt that bronze has to be built first. That is the whole dependency
graph — 25 models across three layers — so `dbt build` runs everything in the right order and you
never maintain a run list. It also means renaming a model updates every reference automatically.

**`build` = `run` + `test`.** Key columns declare `unique` / `not_null` tests in the `_bronze.yml`
/ `_silver.yml` / `_gold.yml` file sitting next to the models, and `dbt/tests/` holds five
hand-written ones for things a generic test cannot express, like "a completed game always has both
scores." `dbt build` runs a model and then its tests before anything downstream of it, so a bad
upstream table stops the run instead of quietly poisoning gold.

### Everything is a table except one view

`dbt_project.yml` sets `+materialized: table`, so each model is rebuilt from scratch as a Delta
table on every run. The exception is `gold_matchup_card`, which is a **view**.

That is deliberate, and it is what keeps the tool handoffs one-way. The matchup card joins
`cfb_gold.game_features` (dbt's) to `cfb_gold.game_predictions` (written by Python in
`notebooks/02`). As a view it re-reads predictions every time someone queries it, so a new scoring
run shows up immediately and there is no second `dbt build` after the model runs. Notebook 00
creates `game_predictions` empty for exactly this reason — the view has to be able to compile
before a model has ever been trained.

### Where bronze comes from

There are no `source()` definitions for CFBD data, because the raw data is not in tables — it is
JSONL files that the Python ingest dropped in a Unity Catalog volume. Bronze models glob those
files directly with `read_files()`, wrapped in the `cfbd_union` macro:

```sql
{{ cfbd_union('games', projection) }}
```

The macro reads two places and unions them: the one-time `historical/` backfill and every
`incremental/dt=YYYY-MM-DD/` drop the weekly refresh has written. Both roots hang off one var, so
repointing at a different volume is a one-line change:

```yaml
vars:
  landing_root: /Volumes/cfb_saturday_hq_raw/landing/cfbd_landing
  include_incremental: true
```

Note that `landing_root` is **not** parameterized by environment. It points into
`cfb_saturday_hq_raw` for both targets, which is what makes dev and prod read byte-identical
inputs.

`include_incremental` is the only var you ever pass on the command line, and only once. Set it to
`false` for the very first build, because at that point no `incremental/` folder exists yet and
`read_files()` errors on a glob matching zero files. After the first weekly refresh, leave it alone.

The single dbt **source** in the project is `cfb_gold.game_predictions` — a table dbt reads but
does not own.

### Why re-running is safe

Since bronze re-reads the backfill *plus* every drop, the same game legitimately appears many
times: scheduled in one Monday's pull, final score in the next. Every silver model dedupes on its
natural key and keeps the newest copy, ordering by `latest_ingest_first()` — incremental beats
historical, and a later `dt=` beats an earlier one.

The practical upshot: **runs are idempotent and you never clean anything out between them.** Run
the refresh twice in one day, or re-run a week later, and you get the same answer. That is also
why the Friday market job is safe: it drops a lines-only file and dbt sorts out precedence.

### Two targets, one project

`dev` and `prod` are dbt targets that differ **only** by catalog — same models, same macros,
same vars. `dbt build` locally goes to `cfb_saturday_hq_dev`; the jobs run
`dbt build --target prod`. Nothing in `models/` mentions a catalog, because `ref()` resolves
within whichever target is active, so promoting a change is just running the same command with
a different `--target`.

The Python side matches: `SATURDAY_HQ_ENV` on the job cluster picks
`cfb_saturday_hq_<env>` in `src/saturday_hq/config.py`, and an interactive notebook with no
such variable defaults to dev. Both come from the bundle target, so `-t prod` moves them
together.

### Configuration: why profiles.yml is committed

`dbt/profiles.yml` is deliberately **not** gitignored, and it holds no secrets. Host, `http_path`,
catalog, and schema are plain non-sensitive values; the only credential is a
`{{ env_var('DBT_ACCESS_TOKEN') }}` reference resolved at runtime:

| | Local laptop | Databricks job dbt task |
|---|---|---|
| **Where the profile comes from** | `dbt/profiles.yml`, found next to `dbt_project.yml` | the same committed file, synced with the repo |
| **How `DBT_ACCESS_TOKEN` is set** | you `source .env` | Databricks **injects it automatically** for the job's *Run As* principal |
| **Profiles Directory setting** | n/a (found via the project dir) | leave **unset** — it defaults to the dbt project root |

Committing the file is what makes the Databricks side trivial: the dbt task syncs the repo, finds
`profiles.yml` where it already lives, and gets a short-lived token injected into the task runtime.
Nothing to copy into the workspace, and no secret ever lands in git.

`.env` is gitignored and is the **local-only** counterpart — it exists so your laptop can supply
the same `DBT_ACCESS_TOKEN` that Databricks supplies for itself. Use `.env.template` (tracked) as
the checklist of what to fill in.

Two things the job tasks must get right, both visible in `resources/jobs.yml`:

- **No `warehouse_id` on the dbt task.** If you set one (or pick a warehouse in the UI),
  Databricks generates its own profile and ignores ours. The warehouse comes from `http_path`
  instead.
- **No `catalog` or `schema` on the task either.** Those can only be set alongside a
  `warehouse_id`, so leaving them in fails validation with
  `Catalog can only be defined if the warehouseId is defined.` Ours come from the profile and
  from the per-folder configs in `dbt_project.yml`.

### Running it locally

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt          # includes dbt-databricks
cp .env.template .env                    # fill in DBT_ACCESS_TOKEN
```

Then every session:

```bash
source .venv/bin/activate
set -a && source .env && set +a          # plain KEY=value lines need the -a wrapper
cd dbt && dbt debug                      # all checks passed?
```

Run dbt from the `dbt/` folder and you never need `--profiles-dir`: dbt looks next to
`dbt_project.yml` before falling back to `~/.dbt/`, and that is exactly where the profile lives.

Fill in `http_path` in `dbt/profiles.yml` the first time (both targets) — **SQL Warehouses** →
your warehouse → *Connection details*.

### Commands worth knowing

```bash
dbt build --vars '{include_incremental: false}'   # first build in an environment
dbt build                                          # every run after that (dev)
dbt build --target prod                            # what the jobs run
dbt build --select silver_games+                   # a model and everything downstream of it
dbt build --select tag:bronze                      # one layer
dbt test  --select silver_games                    # tests only, no rebuild
dbt docs generate && dbt docs serve                # click through the lineage graph
```

### Checking the model before you train it

```bash
python scripts/feature_audit.py     # refits FEATURE_COLS locally, prints the market baseline
```

Worth running before any training job, since it needs only the SQL warehouse and finishes in
seconds. It refits the exact training pipeline over `gold.game_features` and prints holdout
metrics beside the sportsbook's own accuracy on the same games.

The market column is the reason it exists. A logistic regression on season aggregates has no
business beating a sportsbook by much, so an AUC well above the market's means a feature is
carrying the answer — not that the model is good. That is precisely how the as-of join bug
below was caught: 0.95 AUC against the market's 0.79. The script warns when the gap exceeds
five points.

Two leaks worth knowing about, because both are easy to reintroduce:

- **Form** must come from a week *strictly before* the game. A `team_week` row is cumulative
  through its own week, so joining on `week <= game_week` hands the model the result it is
  predicting. Guarded by the `gold_game_features_form_precedes_game` test.
- **SP+ and PPA** are season aggregates. For a finished season they are computed from the game
  in question, so features use the `_prior` columns (last season's ratings). The unsuffixed
  ones are for reporting only.

Each environment needs the `include_incremental: false` treatment for *its* first build only —
that flag is about whether any `incremental/` folder exists yet, which is a property of the
shared volume, so once the first weekly refresh has run neither environment needs it again.

---

## Quick command reminders
```bash
cd /Users/ramiz.bozai/cfb-saturday-hq
databricks secrets create-scope cfb_saturday_hq
databricks secrets put-secret cfb_saturday_hq cfbd_api_key

# after setting workspace host; the target picks the catalog on both sides
databricks bundle deploy -t dev
databricks bundle deploy -t prod
```
