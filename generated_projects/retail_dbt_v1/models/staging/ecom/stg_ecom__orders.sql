{{ config(
    materialized='view',
    schema='staging',
    tags=['staging', 'ecom', 'orders']
) }}

/*
    Staging model for raw orders.
    Grain: One row per order_id
    Casts order IDs, customer IDs, and monetary amounts to proper data types.
*/

with source as (
    select *
    from {{ source('RAW', 'ORDERS') }}
),

cleaned as (
    select
        CAST(order_id AS NUMBER) as order_id,
        CAST(customer_id AS NUMBER) as customer_id,
        CAST(order_date AS DATE) as order_date,
        COALESCE(UPPER(TRIM(status)), 'PENDING') as status,
        COALESCE(CAST(total_amount AS NUMERIC(10,2)), 0.00) as total_amount
    from source
    where order_id is not null
),

deduplicated as (
    select
        order_id,
        customer_id,
        order_date,
        status,
        total_amount
    from cleaned
    qualify row_number() over (partition by order_id order by order_date desc) = 1
)

select
    order_id,
    customer_id,
    order_date,
    status,
    total_amount
from deduplicated
