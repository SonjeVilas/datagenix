{{ config(
    materialized='table',
    schema='marts',
    tags=['marts', 'dimension', 'customers']
) }}

-- Description: Customer dimension combining profile attributes with aggregated lifetime metrics.
-- Grain: One row per customer_id
-- Unique Key: customer_id

with customers as (
    select * from {{ ref('stg_ecom__customers') }}
),

customer_aggregates as (
    select * from {{ ref('int_customers__aggregated_orders') }}
),

joined as (
    select
        customers.customer_id,
        customers.first_name,
        customers.last_name,
        customers.first_name || ' ' || customers.last_name as full_name,
        customers.email,
        customers.created_at,
        coalesce(customer_aggregates.total_orders, 0) as total_orders,
        coalesce(customer_aggregates.total_spend, 0.00) as total_spend
    from customers
    left join customer_aggregates
        on customers.customer_id = customer_aggregates.customer_id
)

select * from joined
