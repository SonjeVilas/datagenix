{{ config(
    materialized='ephemeral',
    schema='intermediate',
    tags=['intermediate', 'customers', 'orders']
) }}

-- Purpose: Aggregates order metrics per customer (total orders and total spend).
-- Grain: customer_id

with orders as (
    select
        customer_id,
        order_id,
        total_amount
    from {{ ref('stg_ecom__orders') }}
),

customer_order_aggregations as (
    select
        customer_id,
        count(order_id) as total_orders,
        sum(total_amount) as total_spend
    from orders
    group by customer_id
),

final as (
    select
        customer_id,
        total_orders,
        total_spend
    from customer_order_aggregations
)

select
    customer_id,
    total_orders,
    total_spend
from final
