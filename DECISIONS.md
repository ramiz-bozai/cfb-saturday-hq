# Saturday HQ — Locked Decisions

| Decision | Choice |
|---|---|
| Scope | FBS only |
| History | 2015 onward |
| Primary metrics | SP+ and PPA (first-class) |
| Betting lines | Include in UI as **Model vs market** (not betting advice) |
| Model training | Train **without** line as a feature so model-vs-market is meaningful |
| Play-by-play | Out of scope for v1 |
| Audience | Demo-able / clean |
| Historical load | Download files into a Unity Catalog **Volume**, then load bronze from Volume |
| Transformation layer | **dbt** for bronze → silver → gold; Python only for ingest, ML, projections, briefs |
| Bronze ingestion | dbt models over `read_files()` on the Volume (no Python bronze loader) |
| Tool handoffs | Exactly one each way: Python ingest → dbt → Python scoring/serving. `matchup_card` is a dbt **view** so nothing in dbt runs after scoring |
| Where dbt runs | Job **dbt tasks**, never from a notebook, against a committed `dbt/profiles.yml`. No `warehouse_id` on the task, so Databricks injects `DBT_ACCESS_TOKEN` for the Run As principal; `.env` supplies it locally |
| Environments | `cfb_saturday_hq_dev` and `cfb_saturday_hq_prod` each hold a full bronze → silver → gold. Selected by `SATURDAY_HQ_ENV` (Python) and `--target` (dbt), both from the bundle target |
| Raw data | One shared volume in `cfb_saturday_hq_raw.landing`, outside both environments: the CFBD API is called once and dev reads exactly what prod reads. Bronze is still per-environment, because it is code output |
| Model registry | Unity Catalog, `<catalog>.cfb_ml.matchup`, so the model follows the environment. Scored via the `production` alias, falling back to the newest version |
| Current season | Derived from the date with an August rollover; never edited between runs |
| Ongoing refresh | CFBD **API** daily |
| Refresh SLA | Daily |
| CFP logic | Published 2026 12-team rules; model ranking is a stand-in for committee rank |

## Disclaimers (show in App + Dashboards)

1. For analysis and entertainment only. Not gambling advice.
2. Playoff projections use Saturday HQ ratings + published CFP structure. Not an official CFP selection.
