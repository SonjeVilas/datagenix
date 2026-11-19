{{ config(
    materialized='view',
    schema='staging',
    tags=['staging', 'ecom', 'customers']
) }}

/*
    Staging model for raw ECOM_DB.RAW.CUSTOMERS.
    Grain: One row per customer_id
    Purpose: Standardize names, lowercase email addresses, handle nulls, and filter invalid records.
*/

with source as (
    select *
    from {{ source('RAW', 'CUSTOMERS') }}
),

transformed as (
    select
        CAST(CUSTOMER_ID AS NUMBER) as customer_id,
        COALESCE(INITCAP(TRIM(FIRST_NAME)), 'Unknown') as first_name,
        COALESCE(INITCAP(TRIM(LAST_NAME)), 'Unknown') as last_name,
        LOWER(TRIM(EMAIL)) as email,
        CAST(CREATED_AT AS TIMESTAMP_NTZ) as created_at,
        CURRENT_TIMESTAMP() as standard_timestamp
    from source
    where CUSTOMER_ID is not NULL
      and LOWER(TRIM(EMAIL)) NOT LIKE '%test%'
)

select * from transformed
