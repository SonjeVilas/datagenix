{{ config(
    materialized='view',
    schema='staging',
    tags=['staging', 'ecom', 'order_items']
) }}

/*
    Staging model for raw ECOM_DB.RAW.ORDER_ITEMS.
    Grain: One row per item_id
    Purpose: Standardize line-item quantities and prices, handle nulls, and ensure valid primary keys.
*/

with source as (
    select *
    from {{ source('RAW', 'ORDER_ITEMS') }}
),

transformed as (
    select
        CAST(ITEM_ID AS NUMBER) as item_id,
        CAST(ORDER_ID AS NUMBER) as order_id,
        CAST(PRODUCT_ID AS NUMBER) as product_id,
        COALESCE(CAST(QUANTITY AS NUMBER), 0) as quantity,
        COALESCE(CAST(UNIT_PRICE AS NUMBER(10,2)), 0.00) as unit_price,
        CURRENT_TIMESTAMP() as standard_timestamp
    from source
    where ITEM_ID is not NULL
)

select * from transformed
