{{ config(
    materialized='ephemeral',
    schema='intermediate',
    tags=['intermediate', 'customers']
) }}

-- Purpose: Intermediate model aggregating order counts and lifetime spend per customer.
-- Grain: One row per customer_id
-- Assumptions: Only valid non-test customers and orders are evaluated.

with customers as (
    select
        customer_id,
        email
    from {{ ref('stg_ecom__customers') }}
    where email not like '%test%'
),

orders as (
    select
        order_id,
        customer_id,
        total_amount
    from {{ ref('stg_ecom__orders') }}
),

customer_order_aggregates as (
    select
        o.customer_id,
        count(o.order_id) as total_orders,
        sum(o.total_amount) as total_spend
    from orders o
    inner join customers c
        on o.customer_id = c.customer_id
    group by o.customer_id
),

final as (
    select
        customer_id,
        total_orders,
        total_spend
    from customer_order_aggregates
)

select * from final
