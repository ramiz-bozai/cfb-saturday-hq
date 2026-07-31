{{
  config(
    materialized='metric_view',
    alias='mv_unit_continuity',
    tags=['gold', 'metric_view', 'preview'],
  )
}}
version: 1.1
comment: >
  Season Preview unit continuity for Genie. Grain is team x position_group x season.
  Continuity and returning shares use AVG; net production and impact counts use SUM;
  departed_share comes from replacement_risk when a callout row exists.
source: {{ ref('gold_unit_continuity') }}
joins:
  - name: returning
    source: {{ ref('gold_returning_production_team') }}
    on: source.season = returning.season AND source.team = returning.team
    rely:
      at_most_one_match: true
  - name: risk
    source: {{ ref('gold_replacement_risk') }}
    on: source.season = risk.season AND source.team = risk.team AND source.position_group = risk.position_group
    rely:
      at_most_one_match: true
filter: returning.conference IS NOT NULL
fields:
  - name: season
    expr: source.season
    comment: Season Preview target year
  - name: team
    expr: source.team
    comment: FBS school name
  - name: conference
    expr: returning.conference
    comment: Conference from returning_production_team join
  - name: position_group
    expr: source.position_group
    comment: QB, RB, WR/TE, OL, DL, LB, DB, or ST
  - name: replacement_risk
    expr: source.replacement_risk
    comment: high, elevated, or manageable from unit_continuity rules
measures:
  - name: unit_count
    expr: COUNT(1)
    comment: Number of unit rows in the group
  - name: continuity_score
    expr: AVG(source.continuity_score)
    comment: 0-100; higher means more continuity
  - name: pct_production_returning
    expr: AVG(source.production_returning_pct)
    comment: Returning share of prior group production (0-1)
  - name: pct_usage_returning
    expr: AVG(source.usage_returning_pct)
    comment: Returning share of prior group usage (0-1)
  - name: net_production_gained
    expr: SUM(source.net_production_gained)
    comment: Prior production in minus out for the unit
  - name: net_talent_gained
    expr: AVG(source.net_talent_gained)
    comment: Avg talent in minus avg talent out for the unit
  - name: impact_additions
    expr: SUM(source.impact_additions)
    comment: Impact portal arrivals at this position group
  - name: impact_losses
    expr: SUM(source.impact_losses)
    comment: Impact portal/draft exits at this position group
  - name: projected_starters_added
    expr: SUM(source.projected_starters_added)
  - name: projected_starters_lost
    expr: SUM(source.projected_starters_lost)
  - name: departed_share
    expr: AVG(risk.departed_share)
    comment: >
      Share of prior unit production metric that left (from replacement_risk);
      null when the unit has no callout row
  - name: best_returner_metric
    expr: AVG(risk.best_returner_metric)
    comment: Best returner's unit-specific prior metric when a callout exists
