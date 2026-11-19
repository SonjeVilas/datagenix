{{ config(
    materialized='table',
    schema='marts',
    tags=['marts', 'dimension', 'customers'],
    unique_key='customer_id'
) }}

/*
    Model: dim_customers
    Description: Customer dimension containing profile information and lifetime monetary and order metrics.
    Grain: One row per customer_id
*/

with customers as (
    select * from {{ ref('stg_ecom__customers') }}
),

customer_metrics as (
    select * from {{ ref('int_customers__aggregated_metrics') }}
),

joined as (
    select
        customers.customer_id,
        customers.first_name,
        customers.last_name,
        customers.email,
        customers.created_at,
        COALESCE(customer_metrics.total_orders, 0) as total_orders,
        COALESCE(customer_metrics.total_spend, 0.00) as total_spend,
        CURRENT_TIMESTAMP() as standard_timestamp
    from customers
    left join customer_metrics
        on customers.customer_id = customer_metrics.customer_id
    where customers.email not like '%test%'
)

select * from joined
