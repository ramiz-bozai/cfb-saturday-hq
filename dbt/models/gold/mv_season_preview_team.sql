{{
  config(
    materialized='metric_view',
    alias='mv_season_preview_team',
    tags=['gold', 'metric_view', 'preview'],
  )
}}
version: 1.1
comment: >
  Season Preview team KPIs for Genie: returning production, transfer dependency,
  and portal ledger. Grain is team x season. Percent and score measures use AVG
  (equals the team value when grouped by team). Count measures use SUM.
source: {{ ref('gold_returning_production_team') }}
joins:
  - name: dependency
    source: {{ ref('gold_transfer_dependency') }}
    on: source.season = dependency.season AND source.team = dependency.team
    rely:
      at_most_one_match: true
  - name: ledger
    source: {{ ref('gold_portal_team_ledger') }}
    on: source.season = ledger.season AND source.team = ledger.team
    rely:
      at_most_one_match: true
filter: source.conference IS NOT NULL
fields:
  - name: season
    expr: source.season
    comment: Season Preview target year
  - name: team
    expr: source.team
    comment: FBS school name
  - name: conference
    expr: source.conference
    comment: Conference as of the prior completed season (membership join)
  - name: returning_source
    expr: source.source
    comment: cfbd when published roster plus CFBD returning row; else computed
measures:
  - name: team_count
    expr: COUNT(1)
    comment: Number of teams in the group
  - name: pct_offense_returning
    expr: AVG(source.percent_offense_returning)
    comment: Share of prior offense yards retained by non-transfer roster players
  - name: pct_defense_returning
    expr: AVG(source.percent_defense_returning)
    comment: Share of prior defense production score retained by non-transfers
  - name: pct_production_returning
    expr: AVG(source.percent_production)
    comment: Share of prior production_score retained by non-transfers
  - name: pct_usage_returning
    expr: AVG(source.percent_usage)
    comment: Share of prior usage retained by non-transfers
  - name: pct_ppa_returning
    expr: AVG(source.percent_ppa)
    comment: Share of prior PPA retained (CFBD when source=cfbd)
  - name: transfer_dependency_score
    expr: AVG(dependency.transfer_dependency_score)
    comment: 0-100; higher means more roster risk from transfers
  - name: offense_transfer_dependency_score
    expr: AVG(dependency.offense_transfer_dependency_score)
    comment: Transfer dependency for QB/RB/WR-TE/OL
  - name: defense_transfer_dependency_score
    expr: AVG(dependency.defense_transfer_dependency_score)
    comment: Transfer dependency for DL/LB/DB
  - name: pct_usage_from_transfers
    expr: AVG(dependency.pct_usage_from_transfers)
    comment: Share of prior usage on the roster from portal arrivals
  - name: critical_units_on_transfers
    expr: SUM(dependency.critical_units_on_transfers)
    comment: Units with elevated/high replacement risk that also added impact transfers
  - name: impact_additions
    expr: SUM(ledger.impact_additions)
    comment: Portal arrivals classified as impact
  - name: impact_losses
    expr: SUM(ledger.impact_losses)
    comment: Portal/draft exits classified as impact
  - name: depth_additions
    expr: SUM(ledger.depth_additions)
    comment: Portal arrivals classified as depth
  - name: depth_losses
    expr: SUM(ledger.depth_losses)
    comment: Portal/draft exits classified as depth
  - name: net_production_gained
    expr: SUM(ledger.net_production_gained)
    comment: Prior production in minus prior production out across units
  - name: net_talent_gained
    expr: AVG(ledger.net_talent_gained)
    comment: Avg talent in minus avg talent out (quality delta, not a sum)
  - name: avg_continuity_score
    expr: AVG(ledger.avg_continuity_score)
    comment: Mean continuity_score across position groups
  - name: projected_starters_added
    expr: SUM(ledger.projected_starters_added)
    comment: Arrivals meeting projected-starter usage/production rule
  - name: projected_starters_lost
    expr: SUM(ledger.projected_starters_lost)
    comment: Departures meeting projected-starter usage/production rule
