{#
    Map CFBD roster / portal / usage / draft position strings onto Preview unit groups.
    Draft picks use full names (Quarterback, Wide Receiver, …); rosters use abbreviations.
#}
{% macro position_group(col) -%}
    case upper(trim({{ col }}))
        when 'QB' then 'QB'
        when 'QUARTERBACK' then 'QB'
        when 'RB' then 'RB'
        when 'FB' then 'RB'
        when 'RUNNING BACK' then 'RB'
        when 'FULLBACK' then 'RB'
        when 'WR' then 'WR/TE'
        when 'TE' then 'WR/TE'
        when 'WIDE RECEIVER' then 'WR/TE'
        when 'TIGHT END' then 'WR/TE'
        when 'OL' then 'OL'
        when 'OT' then 'OL'
        when 'OG' then 'OL'
        when 'OC' then 'OL'
        when 'C' then 'OL'
        when 'G' then 'OL'
        when 'T' then 'OL'
        when 'IOL' then 'OL'
        when 'CENTER' then 'OL'
        when 'OFFENSIVE GUARD' then 'OL'
        when 'OFFENSIVE TACKLE' then 'OL'
        when 'OFFENSIVE LINEMAN' then 'OL'
        when 'DL' then 'DL'
        when 'DE' then 'DL'
        when 'DT' then 'DL'
        when 'NT' then 'DL'
        when 'EDGE' then 'DL'
        when 'DEFENSIVE EDGE' then 'DL'
        when 'DEFENSIVE END' then 'DL'
        when 'DEFENSIVE TACKLE' then 'DL'
        when 'DEFENSIVE LINEMAN' then 'DL'
        when 'NOSE TACKLE' then 'DL'
        when 'LB' then 'LB'
        when 'ILB' then 'LB'
        when 'OLB' then 'LB'
        when 'MLB' then 'LB'
        when 'LINEBACKER' then 'LB'
        when 'INSIDE LINEBACKER' then 'LB'
        when 'OUTSIDE LINEBACKER' then 'LB'
        when 'DB' then 'DB'
        when 'CB' then 'DB'
        when 'S' then 'DB'
        when 'FS' then 'DB'
        when 'SS' then 'DB'
        when 'SAF' then 'DB'
        when 'CORNERBACK' then 'DB'
        when 'SAFETY' then 'DB'
        when 'DEFENSIVE BACK' then 'DB'
        when 'K' then 'ST'
        when 'P' then 'ST'
        when 'LS' then 'ST'
        when 'PK' then 'ST'
        when 'KR' then 'ST'
        when 'PR' then 'ST'
        when 'PLACE KICKER' then 'ST'
        when 'KICKER' then 'ST'
        when 'PUNTER' then 'ST'
        when 'LONG SNAPPER' then 'ST'
        else 'OTHER'
    end
{%- endmacro %}


{# Stable person key for portal rows that lack athleteId. #}
{% macro player_name_key(first_name_col, last_name_col) -%}
    lower(trim(coalesce({{ first_name_col }}, ''))) || '|' || lower(trim(coalesce({{ last_name_col }}, '')))
{%- endmacro %}
