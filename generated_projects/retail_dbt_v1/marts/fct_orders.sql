{{ config(
    materialized='incremental',
    schema='marts',
    tags=['marts', 'fact', 'orders'],
    unique_key='order_id',
    incremental_strategy='merge'
) }}

-- Description: Order fact table containing transactional details and derived status flags.
-- Grain: One row per order_id
-- Unique Key: order_id

with orders as (
    select * from {{ ref('stg_ecom__orders') }}
    {% if is_incremental() %}
    where order_date >= (select max(order_date) from {{ this }})
    {% endif %}
),

transformed as (
    select
        order_id,
        customer_id,
        order_date,
        status,
        total_amount,
        coalesce(case when status = 'completed' then true else false end, false) as is_completed
    from orders
)

select * from transformed
