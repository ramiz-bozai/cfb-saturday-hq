{#
    Helpers for reading CFBD JSONL out of the Unity Catalog Volume.

    Layouts written by notebooks/01_download_historical_to_volume.py and notebooks/04_weekly_ingest.py:
      historical/<domain>/year=YYYY/<domain>.jsonl
      incremental/dt=YYYY-MM-DD/<domain>/<domain>.jsonl
#}

{#
    Ordering for the silver dedupes: when the same natural key lands more than once, keep
    the newest copy. Incremental drops beat the historical backfill, and a later
    dt=YYYY-MM-DD beats an earlier one because the path sorts lexicographically. This is
    what makes re-running the weekly refresh safe — a game that was scheduled in one drop and
    final in a later one resolves to the later row.
#}
{% macro latest_ingest_first() -%}
    case when _ingest_mode = 'incremental' then 1 else 0 end desc, _source_path desc
{%- endmacro %}


{#
    Season for a landed file, derived from its path.

    /teams/fbs is the one CFBD payload with no season field of its own — the endpoint takes
    ?year= but does not echo it back — so the partition the file was written into is the only
    record of which season it describes.

      historical/<domain>/year=YYYY/...    -> YYYY
      incremental/dt=YYYY-MM-DD/<domain>/  -> the season containing that date

    The incremental branch mirrors current_cfb_season() in src/saturday_hq/config.py: a season
    is named for the calendar year it kicks off in and rolls over in August. Keep the 8 below in
    step with SEASON_START_MONTH there.
#}
{% macro landing_season(path_col='_metadata.file_path') -%}
    {%- set dt = "to_date(regexp_extract(" ~ path_col ~ ", 'dt=([0-9]+-[0-9]+-[0-9]+)', 1))" -%}
    case
        when {{ path_col }} rlike 'year=[0-9]+'
            then cast(regexp_extract({{ path_col }}, 'year=([0-9]+)', 1) as int)
        when {{ path_col }} rlike 'dt=[0-9]+-[0-9]+-[0-9]+'
            then case
                when month({{ dt }}) >= 8 then year({{ dt }})
                else year({{ dt }}) - 1
            end
    end
{%- endmacro %}


{% macro cfbd_read(domain, mode) -%}
    {%- set root = var('landing_root') -%}
    {%- if mode == 'historical' -%}
        {%- set path = root ~ '/historical/' ~ domain ~ '/*/*.jsonl' -%}
    {%- elif mode == 'incremental' -%}
        {%- set path = root ~ '/incremental/*/' ~ domain ~ '/*.jsonl' -%}
    {%- else -%}
        {{ exceptions.raise_compiler_error("cfbd_read: mode must be 'historical' or 'incremental', got " ~ mode) }}
    {%- endif -%}
    read_files('{{ path }}', format => 'json')
{%- endmacro %}


{#
    Apply one projection to both landing paths. The projection is passed in rather than
    selected with *, so the two branches always have identical column lists and can be
    unioned even when a JSON drop is missing an optional field.
#}
{% macro cfbd_union(domain, projection) -%}
select
    {{ projection }},
    _metadata.file_path as _source_path,
    'historical' as _ingest_mode,
    current_timestamp() as _ingested_at
from {{ cfbd_read(domain, 'historical') }}
{%- if var('include_incremental') %}

union all

select
    {{ projection }},
    _metadata.file_path as _source_path,
    'incremental' as _ingest_mode,
    current_timestamp() as _ingested_at
from {{ cfbd_read(domain, 'incremental') }}
{%- endif %}
{%- endmacro %}
