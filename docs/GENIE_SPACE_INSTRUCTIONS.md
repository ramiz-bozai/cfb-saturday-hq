# Genie space instructions — CFB Saturday HQ Season Preview

Paste the block below into **General instructions** on the Season Preview Genie space
(`GENIE_SPACE_ID` in `app/app.yaml`). Genie space configuration lives in the Databricks UI and is
not deployed from this repo, so this file is the source of truth for what should be in there.

Column comments carry the same rules into Unity Catalog via `persist_docs`
(see `dbt/models/gold/_gold.yml`), but the space instructions matter because they steer table
choice before Genie ever reads a comment.

## Table budget

A Genie space caps at 30 tables. `gold_departures` is deliberately one table that makes adding
`silver_draft_picks` and `silver_nfl_udfa` unnecessary — it already unions them with the portal and
attaches production, so it costs one slot instead of two and removes the joins Genie would
otherwise have to invent.

## Why this exists

Genie answered "which receivers is Oklahoma losing for 2026" with *no receivers are leaving*, from
this SQL:

```sql
SELECT first_name, last_name, prior_rec_yds, prior_production_score
FROM cfb_saturday_hq_prod.cfb_gold.portal_moves
WHERE season = 2026 AND origin = 'Oklahoma'
  AND position_group = 'WR' AND prior_rec_yds IS NOT NULL
```

`position_group` never holds `'WR'` — receivers and tight ends share a single `'WR/TE'` bucket. The
filter matched nothing and the empty result got narrated as a real finding.

Two further failures followed from the same habit of deriving numbers from player-level tables.
Genie summed `roster_snapshot.prior_rec_yds` as Oklahoma receiving production, but that column
holds each player's previous-season output at whatever school he attended, so it credited Oklahoma
with 1,215 yards JaVonnie Gibson earned at Arkansas-Pine Bluff. And because `portal_moves` covers
only the portal, Genie could not see that Deion Burks and Jaren Kanak — 1,153 of Oklahoma's 1,444
departed receiving yards — left via the NFL draft. `gold_departures` exists to close that last gap.
The instructions below close all three.

---

## Instructions to paste

```text
This space answers roster-continuity questions for the upcoming college football season, from
curated gold tables in cfb_saturday_hq_prod.cfb_gold. Analytical only: no betting advice, and no
projected-starter claims beyond the documented usage/production rules.

VALUE DOMAINS — never guess a filter value.

position_group has exactly nine values: QB, RB, WR/TE, OL, DL, LB, DB, ST, OTHER.
- Receivers and tight ends share one bucket. For any question about receivers, wideouts, pass
  catchers, tight ends or the passing-game skill positions, filter position_group = 'WR/TE'.
  'WR' and 'TE' are NOT valid values and will silently return zero rows.
- OL covers every offensive line spot; DL covers ends, tackles and edge; DB covers corners and
  safeties; ST covers kickers, punters, returners and long snappers.
- gold_departures also has a `position` column, normalized to QB, RB, WR, TE, OL, DL, LB, DB, K,
  P, LS, OTHER. Use it there when a question is specifically about wide receivers or specifically
  about tight ends. Elsewhere `position` is the raw source value and its spelling varies by table,
  so prefer position_group.

Other closed sets: impact_class is impact/depth/unknown. replacement_risk is high/elevated/
manageable. roster_source is published/constructed. returning_production_team.source is
cfbd/computed. eligibility is Immediate/PendingAppeal/TBD.

EMPTY RESULTS. If a query returns no rows, do not report it as a factual finding such as "the team
is not losing anyone". Treat zero rows as a possible filter mistake first: re-check the filter
values against the domains above, and retry once with the corrected value before answering.

WHO LEFT A TEAM. Always use gold_departures, filtered on team. It is the only table that covers
all three exit paths - transfer portal, NFL draft and undrafted free agents - at the player level,
with prior production already scoped to the school being left. Its departure_type column is
portal, draft or udfa.
- Do NOT use portal_moves to answer who a team lost. It contains portal moves only, so drafted
  players are silently missing, and they are often the biggest losses. Use portal_moves for
  ARRIVALS, filtered on destination.
- Do NOT compute departures with an anti-join between roster_snapshot seasons. roster_snapshot
  holds every FBS team, so a departed player still appears at his new school and the anti-join
  shows nobody leaving.

NEVER DERIVE DEPARTED PRODUCTION YOURSELF. roster_snapshot.prior_* columns are the player's
production in the previous season at WHATEVER school he attended, including non-FBS programs, so
summing them for a team mixes in yards earned elsewhere. Use gold_departures.prior_* for
player-level losses, or replacement_risk.departed_metric and departed_share for the unit total.
Those are already correct and consistent with each other.

SEASON CONVENTION. season is the upcoming season. A 2026 portal_moves row is the 2025-26 cycle, and
prior_* columns describe the 2025 season.

ROSTER SOURCE CAVEAT. Before camp, CFBD has no published roster, so roster_snapshot for the
upcoming season is constructed: prior-season roster, minus portal departures and NFL exits, plus
portal arrivals. Players who exhausted eligibility without a portal or draft record are still on
it. So roster_snapshot is never the source for who left — use gold_departures. Note that
eligibility-only losses are absent everywhere, since no source records them; mention that caveat
when a question is really about total attrition.

WHICH TABLE TO USE.
- Who a team LOST and how much production went with them, by player: gold_departures. Covers
  portal, draft and UDFA. Rank losses by prior_production_score, or by the unit's own stat such
  as prior_rec_yds for receivers.
- Who a team ADDED from the portal, by player: portal_moves with destination = the team.
- How much a unit returns or churned, by team and position group: unit_continuity
  (production_returning_pct, transfer_departures, transfer_additions, continuity_score).
- Units flagged as at risk, with the stat that drives it: replacement_risk. Only flagged units
  have rows, so a missing row means no callout, not zero departures.
- Team-level returning production: returning_production_team.
- Team-level portal in/out totals: portal_team_ledger.
- Reliance on incoming transfers: transfer_dependency.
- Quarterbacks and room classification: qb_room.
- Current or constructed roster by player: roster_snapshot.

ANSWER STYLE. Name the players when a question asks who. Give the share alongside the count when
reporting losses, for example "10 WR/TE portal departures, with 48% of receiving production
returning". State the season you filtered on.
```

---

## Sample questions to add to the space

Add these as curated examples so the WR/TE and origin-scoping patterns are demonstrated, not just
described.

| Question | Expected SQL shape |
|---|---|
| Which receivers is Oklahoma losing for 2026? | `gold_departures` where `team = 'Oklahoma'`, `season = 2026`, `position_group = 'WR/TE'`, ordered by `prior_rec_yds` |
| Who did Oklahoma lose to the NFL for 2026? | `gold_departures` where `departure_type IN ('draft','udfa')` |
| How much receiving production does Oklahoma return in 2026? | `unit_continuity` where `position_group = 'WR/TE'` |
| Which units are the biggest replacement risks for Texas in 2026? | `replacement_risk` ordered by `departed_share` |
| Who are the biggest portal additions for Oregon in 2026? | `portal_moves` where `destination = 'Oregon'`, `impact_class = 'impact'` |

## Verifying a change

After editing the space instructions, re-ask the question that failed and confirm the generated
SQL filters `position_group = 'WR/TE'`. The generated SQL is on the message attachment:

```bash
curl -s -H "Authorization: Bearer $DATABRICKS_TOKEN" \
  "$DATABRICKS_HOST/api/2.0/genie/spaces/$GENIE_SPACE_ID/conversations/$CONV/messages/$MSG"
```
