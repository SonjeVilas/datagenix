{{
    config(
        materialized='ephemeral',
        schema='intermediate',
        tags=['intermediate', 'customers', 'orders']
    )
}}

/*
    Model: int_customers__aggregated_orders
    Purpose: Intermediate model aggregating order counts, total spend, and date ranges per customer.
    Grain: One row per customer_id
    Dependencies: stg_ecom__orders
*/

with orders as (
    select
        customer_id,
        order_id,
        total_amount,
        order_date
    from {{ ref('stg_ecom__orders') }}
    where customer_id is not null
),

customer_order_aggregations as (
    select
        customer_id,
        count(order_id) as total_orders,
        sum(total_amount) as total_spend,
        max(order_date) as last_order_date,
        min(order_date) as first_order_date
    from orders
    group by customer_id
),

final as (
    select
        customer_id,
        total_orders,
        total_spend,
        last_order_date,
        first_order_date
    from customer_order_aggregations
)

select
    customer_id,
    total_orders,
    total_spend,
    last_order_date,
    first_order_date
from final
