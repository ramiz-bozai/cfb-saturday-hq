# Saturday HQ — Cheatsheet Runbook

Quick reference for **historical vs incremental**, what jobs run, and what you actually need to touch. For the full narrative walkthrough see [`STEP_BY_STEP.md`](STEP_BY_STEP.md).

---

## Mental model

| Layer | Historical (one-time) | Incremental (ongoing) |
|---|---|---|
| Raw Volume | `historical/<domain>/year=YYYY/` | `incremental/dt=YYYY-MM-DD/<domain>/` |
| How it lands | Notebook `01` | Notebook `04` (weekly/market) or `06` (Season Preview) |
| First dbt | `dbt build --vars '{include_incremental: false}'` | — |
| Steady dbt | — | `dbt build` (default includes incremental) |
| Bronze | Unions historical (+ incremental when enabled) | Same models; silver dedupe keeps the newest copy |

- Catalogs: `cfb_saturday_hq_dev` / `cfb_saturday_hq_prod` (dbt target).
- Raw is shared: `cfb_saturday_hq_raw.landing` Volume — ingest once, both envs read it.
- **Season is date-derived** (August rollover). You do not edit the year between weekly runs.
- Same-day re-run is safe: the drop overwrites; silver keeps the latest copy.

---

## Right now (typical mid/late summer)

- Gold/bronze **games** usually stop at the last completed season (e.g. 2025).
- **Season Preview** for the upcoming year (e.g. 2026) comes from the **preview** incremental path (`06`), not from the Monday weekly games pull.
- Monday weekly ingest **exits early February–July** — it will not pull `games` / SP+ / PPA in the offseason window.
- Schedule-difficulty pill + Genie schedule notes stay **hidden** until that season’s games exist in silver.

---

## Jobs (Asset Bundle)

Defined in `resources/jobs.yml`. Deploy: `databricks bundle deploy -t dev` / `-t prod`.

| Job | When | Pipeline | Calls (approx) |
|---|---|---|---|
| `saturday-hq-weekly-refresh-<env>` | Mon 10:00 ET (PAUSED until ready) | `04` → `dbt build` → `05` | 7–9 |
| `saturday-hq-market-refresh-<env>` | Fri 10:00 ET (PAUSED) | `04` (market) → `dbt build` | 1–2 |
| `saturday-hq-preview-refresh-<env>` | Manual / as needed | `06` → selective `dbt build` | Preview domains |
| `saturday-hq-historical-backfill-<env>` | Once, by hand | `01` → dbt (`include_incremental: false`) → `02` → `03` | ~145 |

Keep schedules **PAUSED** until one successful end-to-end weekly pass.

---

## Incremental loop (steady state)

### Monday — weekly refresh

1. **`notebooks/04_weekly_ingest.py`**  
   CFBD → `incremental/dt=YYYY-MM-DD/`  
   Mode: `SATURDAY_HQ_INGEST_MODE=weekly`

2. **`dbt build --target <env>`**  
   bronze → silver → gold (full project)

3. **`notebooks/05_weekly_score_and_serve.py`**  
   Score slate, playoff sims, weekly briefs

**Weekly domains (every Monday in-season):**  
`games`, `sp_plus`, `ppa_teams`, `ppa_games`, `rankings`, `team_season_stats`, `lines`

**Also, when needed:**
- Season-static (`teams_fbs`, `talent`, `recruiting_teams`) — first in-season run; marker at `incremental/_state/season_static_<season>.json`
- Static (`conferences`) — once if missing under `incremental/`
- Postseason `games` / `lines` — skipped until December

**Guards in `04`:**
- Exits early **Feb–Jul** (nothing useful changing)
- `WEEK = None` on purpose (full-season pull; same call cost, catches corrections)
- Env is bundle/`SATURDAY_HQ_ENV` — ingest itself writes the shared raw volume

### Friday — market refresh

1. **`04`** with `SATURDAY_HQ_INGEST_MODE=market` → lines only  
2. **`dbt build`**  
No `05` — model features exclude lines; only market columns / `matchup_card` view move.

---

## Season Preview path (safe in July)

Not the Monday weekly job.

1. **`notebooks/06_preview_ingest.py`** (or local sync script)  
   Upcoming season + prior production player domains → `incremental/dt=…/`

2. **Selective dbt** (as in the preview job / STEP_BY_STEP):

```bash
cd dbt
dbt build --target prod --select \
  bronze_rosters+ bronze_player_portal+ bronze_player_returning+ \
  bronze_player_usage+ bronze_player_season_stats+ bronze_ppa_players_season+ \
  bronze_recruiting_players+ bronze_draft_picks+ bronze_nfl_udfa+
```

Job: `saturday-hq-preview-refresh-<env>`.

Roster note: if CFBD has no published roster yet, Season Preview **constructs** from prior roster ± portal and subtracts NFL exits (draft + UDFA).

---

## Historical backfill (once)

1. **`01_download_historical_to_volume.py`** → `historical/`  
   Optional: set `END_YEAR` to the upcoming year to load next season’s **schedule** early.
2. **`dbt build --target <env> --vars '{include_incremental: false}'`**
3. **`02_train_and_score.py`**
4. **`03_projections_and_briefs.py`**

Do **not** re-run full historical every week. After this, only incrementals.

---

## Manual end-to-end (laptop / Run now)

```text
04 (ingest)  →  dbt build --target prod  →  05 (score/serve)
```

First build ever (no incremental JSONL yet):

```bash
cd dbt
dbt build --target prod --vars '{include_incremental: false}'
```

After any valid `incremental/dt=…/` drop exists for bronze domains:

```bash
cd dbt
dbt build --target prod
```

---

## What you usually do *not* change

- Season year between weekly runs (date-derived)
- Domain lists every week (`plan_domains()` / tiers in `src/saturday_hq/config.py`)
- App code for a data refresh (app reads gold / `cfb_app`)

---

## Special cases

### Load 2026 (or upcoming) schedules before August weekly

Weekly `04` will not pull games in Feb–Jul. Options:

1. Historical/backfill games with `END_YEAR=<upcoming>` then dbt rebuild `bronze_games` → silver → gold as needed, **or**
2. Force an out-of-season games pull only if you intentionally set `FORCE_OUT_OF_SEASON` in `04` (use sparingly; costs calls)

Until games exist for that season in silver:
- Schedule-difficulty **pill** stays off
- Genie brief schedule sentence stays off  
  (both via `app/server/scheduleDifficulty.js`)

### Genie Season Preview briefs (not in the weekly job)

```bash
# Skeleton rows (once / when teams change)
cd dbt && dbt run --select app_genie_team_briefs --target prod

# Fill / refresh narratives
cd app && node scripts/warm_genie_briefs.js
cd app && node scripts/warm_genie_briefs.js --team=Texas --force
```

Needs Genie Can Run on the space + MODIFY on `cfb_app.genie_team_briefs`.  
Locally, Genie calls use your PAT if `DATABRICKS_TOKEN` / `DBT_ACCESS_TOKEN` is set (shows as you in Genie UI). Deployed app M2M uses the service principal when no user PAT is present.

### Force season-static re-pull

Delete `incremental/_state/season_static_<season>.json` so the next weekly run re-fetches `teams_fbs`, `talent`, `recruiting_teams`.

---

## Asset map (where to look)

| Concern | Asset |
|---|---|
| Weekly ingest | `notebooks/04_weekly_ingest.py` |
| Weekly score + sims + briefs | `notebooks/05_weekly_score_and_serve.py` |
| Preview ingest | `notebooks/06_preview_ingest.py` |
| Historical download | `notebooks/01_download_historical_to_volume.py` |
| Domain tiers / season helpers | `src/saturday_hq/config.py` |
| Job schedules | `resources/jobs.yml` |
| dbt models | `dbt/models/{bronze,silver,gold,app}/` |
| App + Genie API | `app/` |
| Schedule difficulty pill / Genie note | `app/server/scheduleDifficulty.js` |

---

## Checklist — “turn on the weekly machine”

1. Historical backfill + first dbt (`include_incremental: false`) done once.
2. One manual `04 → dbt build → 05` succeeds in-season (or after you accept forcing out of season).
3. Unpause `saturday-hq-weekly-refresh-<env>` and `saturday-hq-market-refresh-<env>`.
4. Season Preview: run preview job / `06` + selective dbt when roster/portal need refresh.
5. Optionally warm Genie briefs after preview gold is current.

---

*Last aligned with repo docs/jobs as of the Season Preview + Genie embed work. Prefer STEP_BY_STEP if this cheatsheet and the long guide disagree — update this file.*
