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


{# Power 4 / G6 / Independent bucketing used by the gold marts. #}
{% macro conference_group(conference_col, is_notre_dame_col) -%}
    case
        when {{ conference_col }} in ('ACC', 'Big Ten', 'Big 12', 'SEC') then 'Power4'
        when {{ conference_col }} in ('American', 'CUSA', 'MAC', 'Mountain West', 'Pac-12', 'Sun Belt') then 'G6'
        when {{ is_notre_dame_col }} then 'Independent'
        else 'Other'
    end
{%- endmacro %}
