{#
    Map nflverse college strings onto CFBD roster `team` labels.
    Identity passthrough when the string already matches; null for non-FBS / unknown.
#}
{% macro normalize_nfl_college(col) -%}
    case lower(trim({{ col }}))
        when 'louisiana state' then 'LSU'
        when 'lsu' then 'LSU'
        when 'southern california' then 'USC'
        when 'usc' then 'USC'
        when 'texas christian' then 'TCU'
        when 'tcu' then 'TCU'
        when 'southern methodist' then 'SMU'
        when 'smu' then 'SMU'
        when 'brigham young' then 'BYU'
        when 'byu' then 'BYU'
        when 'central florida' then 'UCF'
        when 'ucf' then 'UCF'
        when 'texas-san antonio' then 'UTSA'
        when 'utsa' then 'UTSA'
        when 'alabama-birmingham' then 'UAB'
        when 'uab' then 'UAB'
        when 'mississippi' then 'Ole Miss'
        when 'ole miss' then 'Ole Miss'
        when 'north carolina state' then 'NC State'
        when 'nc state' then 'NC State'
        when 'n.c. state' then 'NC State'
        when 'pennsylvania state' then 'Penn State'
        when 'penn state' then 'Penn State'
        when 'miami (fl)' then 'Miami'
        when 'miami fl' then 'Miami'
        when 'miami florida' then 'Miami'
        when 'miami' then 'Miami'
        when 'florida international' then 'Florida International'
        when 'fiu' then 'Florida International'
        when 'middle tennessee' then 'Middle Tennessee'
        when 'middle tennessee state' then 'Middle Tennessee'
        when 'texas a&m' then 'Texas A&M'
        when 'texas am' then 'Texas A&M'
        when 'texas a and m' then 'Texas A&M'
        when 'boston college' then 'Boston College'
        when 'virginia tech' then 'Virginia Tech'
        when 'georgia tech' then 'Georgia Tech'
        when 'oklahoma state' then 'Oklahoma State'
        when 'mississippi state' then 'Mississippi State'
        when 'ohio state' then 'Ohio State'
        when 'florida state' then 'Florida State'
        when 'michigan state' then 'Michigan State'
        when 'oregon state' then 'Oregon State'
        when 'washington state' then 'Washington State'
        when 'arizona state' then 'Arizona State'
        when 'kansas state' then 'Kansas State'
        when 'colorado state' then 'Colorado State'
        when 'san diego state' then 'San Diego State'
        when 'san jose state' then 'San José State'
        when 'san josé state' then 'San José State'
        when 'fresno state' then 'Fresno State'
        when 'boise state' then 'Boise State'
        when 'appalachian state' then 'App State'
        when 'app state' then 'App State'
        when 'coastal carolina' then 'Coastal Carolina'
        when 'georgia southern' then 'Georgia Southern'
        when 'georgia state' then 'Georgia State'
        when 'james madison' then 'James Madison'
        when 'jacksonville state' then 'Jacksonville State'
        when 'kennesaw state' then 'Kennesaw State'
        when 'liberty' then 'Liberty'
        when 'massachusetts' then 'UMass'
        when 'umass' then 'UMass'
        when 'connecticut' then 'UConn'
        when 'uconn' then 'UConn'
        when 'hawaii' then 'Hawai''i'
        when 'hawai''i' then 'Hawai''i'
        when 'southern mississippi' then 'Southern Mississippi'
        when 'southern miss' then 'Southern Mississippi'
        when 'louisiana monroe' then 'Louisiana Monroe'
        when 'ul monroe' then 'Louisiana Monroe'
        when 'louisiana-lafayette' then 'Louisiana'
        when 'louisiana lafayette' then 'Louisiana'
        when 'ull' then 'Louisiana'
        when 'western kentucky' then 'Western Kentucky'
        when 'western michigan' then 'Western Michigan'
        when 'eastern michigan' then 'Eastern Michigan'
        when 'central michigan' then 'Central Michigan'
        when 'northern illinois' then 'Northern Illinois'
        when 'bowling green' then 'Bowling Green'
        when 'miami (oh)' then 'Miami (OH)'
        when 'miami oh' then 'Miami (OH)'
        when 'miami ohio' then 'Miami (OH)'
        else nullif(trim({{ col }}), '')
    end
{%- endmacro %}


{#
    College players who leave for the NFL before season N: drafted (CFBD) + UDFAs (nflverse).
    Grain: one row per (season, athlete_id). season == draft_year / rookie_year.
#}
{% macro nfl_college_exits() -%}
(
    select
        draft_year as season,
        athlete_id,
        college_team,
        position_group,
        'draft' as exit_source
    from {{ ref('silver_draft_picks') }}
    where athlete_id is not null

    union all

    select
        u.rookie_year as season,
        u.athlete_id,
        u.college_team,
        u.position_group,
        'udfa' as exit_source
    from {{ ref('silver_nfl_udfa') }} as u
    where u.athlete_id is not null
      and not exists (
          select 1
          from {{ ref('silver_draft_picks') }} as d
          where d.draft_year = u.rookie_year
            and d.athlete_id = u.athlete_id
      )
)
{%- endmacro %}
