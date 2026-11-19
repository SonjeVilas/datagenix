{{ config(
    materialized='ephemeral',
    schema='intermediate',
    tags=['intermediate', 'orders']
) }}

/*
    Model: int_orders__enriched
    Layer: intermediate
    Grain: One row per order
    Purpose: Enriches orders from staging with computed status flags and metrics.
*/

with stage_orders as (
    select
        order_id,
        customer_id,
        order_date,
        status,
        total_amount
    from {{ ref('stg_ecom__orders') }}
),

enrich_orders as (
    select
        order_id,
        customer_id,
        order_date,
        status,
        total_amount,
        coalesce(
            case 
                when status = 'completed' then true 
                else false 
            end, 
            false
        ) as is_completed
    from stage_orders
)

select
    order_id,
    customer_id,
    order_date,
    status,
    total_amount,
    is_completed
from enrich_orders
