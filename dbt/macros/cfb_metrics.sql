{#
    Collapse CFBD's conference spellings onto the canonical names used by
    src/saturday_hq/config.py (POWER4_CANONICAL / G6_CANONICAL). Names that are
    already canonical fall through the else branch unchanged.
#}
{% macro normalize_conference(col) -%}
    case {{ col }}
        when 'B1G' then 'Big Ten'
        when 'American Athletic' then 'American'
        when 'AAC' then 'American'
        when 'Conference USA' then 'CUSA'
        when 'Mid-American' then 'MAC'
        when 'MWC' then 'Mountain West'
        when 'Ind' then 'FBS Independents'
        else {{ col }}
    end
{%- endmacro %}


{# American moneyline to implied win probability. No vig removal. #}
{% macro american_ml_to_prob(col) -%}
    case
        when {{ col }} is null then cast(null as double)
        when {{ col }} < 0 then (-{{ col }}) / ((-{{ col }}) + 100.0)
        else 100.0 / ({{ col }} + 100.0)
    end
{%- endmacro %}


{#
    Two-way de-vig of a moneyline pair.

    Raw implied probabilities do not sum to 1 — in this data they average 1.045, and that 4.5%
    overround is the book's margin, not an opinion about the game. Left in, it inflates the home
    side by 2-3 points on every game, which biases any model-minus-market comparison in a single
    direction. Normalizing by the pair recovers the market's actual view.

    Null when either price is missing, since one side alone cannot be de-vigged.
#}
{% macro no_vig_home_prob(home_ml, away_ml) -%}
    case
        when {{ home_ml }} is null or {{ away_ml }} is null then cast(null as double)
        else ({{ american_ml_to_prob(home_ml) }})
            / nullif(
                ({{ american_ml_to_prob(home_ml) }}) + ({{ american_ml_to_prob(away_ml) }}),
                0
            )
    end
{%- endmacro %}


{#
    Stable sportsbook preference used by the three canonical market tables.

    Completeness is enforced in each model's WHERE clause before this tie-break runs, so a sparse
    Consensus row can never beat a complete real-book quote for moneylines or opening lines.
    Keep the two DraftKings spellings because both occur in the historical CFBD payloads.
#}
{% macro market_provider_priority(provider_col='provider') -%}
    case lower({{ provider_col }})
        when 'consensus' then 0
        when 'draftkings' then 1
        when 'draft kings' then 1
        when 'bovada' then 2
        when 'espn bet' then 3
        when 'caesars' then 4
        else 9
    end
{%- endmacro %}


{# Power 4 / G6 / Independent bucketing used by the gold marts. #}
{% macro conference_group(conference_col, is_notre_dame_col) -%}
    case
        when {{ conference_col }} in ('ACC', 'Big Ten', 'Big 12', 'SEC') then 'Power4'
        when {{ conference_col }} in ('American', 'CUSA', 'MAC', 'Mountain West', 'Pac-12', 'Sun Belt') then 'G6'
        when {{ is_notre_dame_col }} then 'Independent'
        else 'Other'
    end
{%- endmacro %}


{#
    Defensive contribution score when CFBD usage/PPA are missing (DL/LB/DB).

    CFBD / NCAA TFL includes sacks, so we score non-sack TFLs and sacks separately:
      tackles + 2*(TFL − sacks) + 3*sacks + 2*INT
    Equivalent when TFL ≥ sacks: tackles + 2*TFL + sacks + 2*INT.

    Rough index (same impact gate as offense production >= 15):
      ~15 rotational / impact floor, ~40–80 solid starter, 100+ elite season.
#}
{% macro defense_production_score(tackles_col, tfl_col, sacks_col, int_col) -%}
    (
        coalesce({{ tackles_col }}, 0.0)
        + 2.0 * greatest(
            coalesce({{ tfl_col }}, 0.0) - coalesce({{ sacks_col }}, 0.0),
            0.0
        )
        + 3.0 * coalesce({{ sacks_col }}, 0.0)
        + 2.0 * coalesce({{ int_col }}, 0.0)
    )
{%- endmacro %}


{#
    Season Preview impact / depth / unknown.
    OL/ST: talent or high stars (no CFBD usage/PPA).
    Skill/defense with prior stats: usage / production gates.
    Missing prior: stricter talent fallback (starter-bar), else unknown — not auto-depth.
#}
{% macro preview_impact_class(position_group_col, usage_col, production_col, talent_col, stars_col, has_prior_col) -%}
    case
        when {{ position_group_col }} in ('OL', 'ST') then
            case
                when coalesce({{ talent_col }}, 0.0) >= 0.85
                  or coalesce({{ stars_col }}, 0) >= 4
                then 'impact'
                when coalesce({{ talent_col }}, 0.0) > 0
                  or {{ stars_col }} is not null
                then 'depth'
                else 'unknown'
            end
        when {{ has_prior_col }} then
            case
                when coalesce({{ usage_col }}, 0.0) >= 0.15
                  or coalesce({{ production_col }}, 0.0) >= 15.0
                then 'impact'
                else 'depth'
            end
        -- No prior season stats: only promote on high talent (not ordinary 3★)
        when coalesce({{ talent_col }}, 0.0) >= 0.90
          or coalesce({{ stars_col }}, 0) >= 4
        then 'impact'
        when coalesce({{ talent_col }}, 0.0) > 0
          or {{ stars_col }} is not null
        then 'depth'
        else 'unknown'
    end
{%- endmacro %}


{% macro preview_projected_starter(position_group_col, usage_col, production_col, talent_col, stars_col, has_prior_col) -%}
    case
        when {{ position_group_col }} in ('OL', 'ST') then (
            coalesce({{ talent_col }}, 0.0) >= 0.90
            or coalesce({{ stars_col }}, 0) >= 4
        )
        when {{ position_group_col }} in ('RB', 'WR/TE') then (
            (
                {{ has_prior_col }}
                and (
                    coalesce({{ usage_col }}, 0.0) >= 0.25
                    or coalesce({{ production_col }}, 0.0) >= 40.0
                )
            )
            or (
                coalesce({{ talent_col }}, 0.0) >= 0.85
                and (
                    coalesce({{ production_col }}, 0.0) >= 10.0
                    or coalesce({{ usage_col }}, 0.0) >= 0.08
                )
            )
        )
        when {{ has_prior_col }} then (
            coalesce({{ usage_col }}, 0.0) >= 0.25
            or coalesce({{ production_col }}, 0.0) >= 40.0
        )
        else (
            coalesce({{ talent_col }}, 0.0) >= 0.90
            or coalesce({{ stars_col }}, 0) >= 4
        )
    end
{%- endmacro %}
