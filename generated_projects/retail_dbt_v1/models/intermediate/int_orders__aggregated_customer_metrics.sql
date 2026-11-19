{{ config(
    materialized='ephemeral',
    schema='intermediate',
    tags=['intermediate', 'orders', 'customers']
) }}

/*
    Model: int_orders__aggregated_customer_metrics
    Purpose: Aggregates order metrics (total orders, total spend, first order date, most recent order date) per customer.
    Grain: One row per customer_id
*/

with orders as (

    select
        customer_id,
        order_id,
        order_date,
        total_amount
    from {{ ref('stg_ecom__orders') }}

),

customer_order_metrics as (

    select
        customer_id,
        count(order_id) as total_orders,
        sum(total_amount) as total_spend,
        min(order_date) as first_order_date,
        max(order_date) as most_recent_order_date
    from orders
    group by customer_id

)

select
    customer_id,
    total_orders,
    total_spend,
    first_order_date,
    most_recent_order_date
from customer_order_metrics
