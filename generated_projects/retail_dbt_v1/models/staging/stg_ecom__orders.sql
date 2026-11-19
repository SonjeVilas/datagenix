{{ config(
    materialized='view',
    schema='staging',
    tags=['staging', 'ecom', 'orders']
) }}

/*
    Staging model for raw ECOM_DB.RAW.ORDERS.
    Grain: One row per order_id
    Purpose: Clean data types, cast monetary values, normalize status, and handle nulls.
*/

with source as (
    select *
    from {{ source('RAW', 'ORDERS') }}
),

transformed as (
    select
        CAST(ORDER_ID AS NUMBER) as order_id,
        CAST(CUSTOMER_ID AS NUMBER) as customer_id,
        CAST(ORDER_DATE AS DATE) as order_date,
        COALESCE(LOWER(TRIM(STATUS)), 'pending') as status,
        COALESCE(CAST(TOTAL_AMOUNT AS NUMBER(10,2)), 0.00) as total_amount,
        CURRENT_TIMESTAMP() as standard_timestamp
    from source
    where ORDER_ID is not NULL
)

select * from transformed
