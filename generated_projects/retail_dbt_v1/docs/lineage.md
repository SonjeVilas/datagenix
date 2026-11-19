# Data Lineage Narrative

This document describes the flow of data through the `retail_dbt_v1` dbt project, tracing records from raw operational tables in Snowflake to the final business-ready dimensional models.

## 1. Raw Source Layer (`ECOM_DB.RAW`)
The pipeline begins with operational tables extracted from source systems into Snowflake:
- `ECOM_DB.RAW.CUSTOMERS`: Raw customer profile and creation timestamps.
- `ECOM_DB.RAW.ORDERS`: Raw transactional order data, order dates, status, and amounts.
- `ECOM_DB.RAW.ORDER_ITEMS`: Line-item details associated with orders.

## 2. Staging Layer (`models/staging`)
The staging layer establishes a clean 1:1 abstraction over the raw source tables. Views are utilized to avoid duplicate data storage and ensure downstream models always query the freshest source state.
- **`stg_ecom__customers`**: Cleans and casts customer data, standardizes first and last names to proper case (`INITCAP`), lowercases email addresses, filters out test emails, and drops null primary keys.
- **`stg_ecom__orders`**: Cleans and casts order IDs, customer IDs, order dates, lowercases and normalizes statuses, and casts monetary values to `NUMBER(10,2)`.
- **`stg_ecom__order_items`**: Standardizes quantities and unit prices, defaulting nulls safely.

## 3. Intermediate Layer (`models/intermediate`)
The intermediate layer isolates complex transformations and aggregations before they reach final presentation marts. Materialized as ephemeral models, these queries are compiled directly into downstream models without creating physical intermediate tables.
- **`int_customers__aggregated_metrics`**: Joins staging customers and orders to group transactions by `customer_id`, computing `total_orders` and `total_spend` per customer.

## 4. Marts Layer (`models/marts`)
The marts layer delivers consumption-ready analytical datasets tailored for business analysts, finance teams, and reporting dashboards.
- **`dim_customers`**: Materialized as a table, this customer dimension combines cleaned profile data with customer lifetime aggregations (`total_orders`, `total_spend`), defaulting non-transacting customers to zero.
- **`fct_orders`**: Materialized incrementally using a unique key merge strategy on `order_id`, this order fact table includes transaction details, monetary values, and a derived boolean `is_completed` flag based on order status.