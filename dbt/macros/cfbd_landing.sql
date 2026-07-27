{#
    Helpers for reading CFBD JSONL out of the Unity Catalog Volume.

    Layouts written by notebooks/01_download_historical_to_volume.py and the weekly refresh:
      historical/<domain>/year=YYYY/<domain>.jsonl
      incremental/dt=YYYY-MM-DD/<domain>/<domain>.jsonl
#}

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
