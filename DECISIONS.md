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
| Ongoing refresh | CFBD **API** daily |
| Refresh SLA | Daily |
| CFP logic | Published 2026 12-team rules; model ranking is a stand-in for committee rank |

## Disclaimers (show in App + Dashboards)

1. For analysis and entertainment only. Not gambling advice.
2. Playoff projections use Saturday HQ ratings + published CFP structure. Not an official CFP selection.
