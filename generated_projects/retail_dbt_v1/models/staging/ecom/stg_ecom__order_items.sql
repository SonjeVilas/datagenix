{{ config(
    materialized='view',
    schema='staging',
    tags=['staging', 'ecom', 'order_items']
) }}

/*
    Staging model for raw order items line details.
    Grain: One row per item_id
    Casts IDs and calculates line item totals.
*/

with source as (
    select *
    from {{ source('RAW', 'ORDER_ITEMS') }}
),

cleaned as (
    select
        CAST(item_id AS NUMBER) as item_id,
        CAST(order_id AS NUMBER) as order_id,
        CAST(product_id AS NUMBER) as product_id,
        COALESCE(CAST(quantity AS NUMBER), 0) as quantity,
        COALESCE(CAST(unit_price AS NUMERIC(10,2)), 0.00) as unit_price,
        (COALESCE(CAST(quantity AS NUMBER), 0) * COALESCE(CAST(unit_price AS NUMERIC(10,2)), 0.00)) as item_total
    from source
    where item_id is not null
)

select
    item_id,
    order_id,
    product_id,
    quantity,
    unit_price,
    item_total
from cleaned
