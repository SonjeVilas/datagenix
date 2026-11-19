{{ config(
    materialized='view',
    schema='staging',
    tags=['staging', 'ecom', 'customers']
) }}

/*
    Staging model for raw customer profiles.
    Grain: One row per customer_id
    Standardizes names, lowercases and cleans emails, and casts timestamps.
*/

with source as (
    select *
    from {{ source('RAW', 'CUSTOMERS') }}
),

cleaned as (
    select
        CAST(customer_id AS NUMBER) as customer_id,
        INITCAP(TRIM(first_name)) as first_name,
        INITCAP(TRIM(last_name)) as last_name,
        COALESCE(LOWER(TRIM(email)), 'unknown@unknown.com') as email,
        CAST(created_at AS TIMESTAMP_NTZ) as created_at
    from source
    where customer_id is not null
),

deduplicated as (
    select
        customer_id,
        first_name,
        last_name,
        email,
        created_at
    from cleaned
    qualify row_number() over (partition by customer_id order by created_at desc) = 1
)

select
    customer_id,
    first_name,
    last_name,
    email,
    created_at
from deduplicated
