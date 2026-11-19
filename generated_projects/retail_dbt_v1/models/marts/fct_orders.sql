{{ config(
    materialized='incremental',
    schema='marts',
    tags=['marts', 'fact', 'orders'],
    unique_key='order_id',
    incremental_strategy='merge'
) }}

/*
    Model: fct_orders
    Description: Order fact table containing individual transaction metrics, order status, and completion flag.
    Grain: One row per order_id
*/

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
        COALESCE(status, 'pending') as status,
        COALESCE(total_amount, 0.00) as total_amount,
        CASE WHEN status = 'completed' THEN true ELSE false END as is_completed,
        CURRENT_TIMESTAMP() as standard_timestamp
    from orders
)

select * from transformed
