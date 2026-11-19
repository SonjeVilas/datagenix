# Retail Customer & Orders Analytics (`retail_dbt_v1`)

## Project Overview
`retail_dbt_v1` is a modular, dimensional dbt project built on top of Snowflake data. It standardizes raw customer and order data, computes customer lifetime metrics, builds robust order fact tables, and provides clean dimensional datasets ready for business consumption and BI reporting.

## Prerequisites
- **Snowflake Database Access**: `ECOM_DB.RAW` database and schema access.
- **dbt Core**: Version 1.6+ installed locally or via an orchestration tool.
- **Authentication**: Valid Snowflake credentials configured via environment variables.

## Setup Instructions
1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd retail_dbt_v1
   ```
2. Configure your `profiles.yml` (refer to `profiles.yml.example`). Set the necessary environment variables:
   ```bash
   export DBT_SNOWFLAKE_ACCOUNT="your_account"
   export DBT_SNOWFLAKE_USER="your_user"
   export DBT_SNOWFLAKE_PASSWORD="your_password"
   export DBT_SNOWFLAKE_ROLE="your_role"
   export DBT_SNOWFLAKE_WAREHOUSE="your_warehouse"
   ```
3. Install dependencies:
   ```bash
   dbt deps
   ```
4. Test your connection:
   ```bash
   dbt debug
   ```
5. Run the models:
   ```bash
   dbt run
   ```
6. Execute data tests:
   ```bash
   dbt test
   ```

## Model Layers
- **Staging (`models/staging`)**: Views mapping 1:1 to raw tables (`ECOM_DB.RAW`). Performs light type casting, string trimming, proper casing, lowercase email normalization, and null handling.
- **Intermediate (`models/intermediate`)**: Ephemeral models executing business logic encapsulations, joins, pre-aggregations (e.g., customer lifetime spend and order counts), and filtering.
- **Marts (`models/marts`)**: Final analytical models exposed to BI and business analysts. Includes tables and incremental models (`dim_customers`, `fct_orders`).

## High-Level DAG Summary
```
ECOM_DB.RAW.CUSTOMERS ---> stg_ecom__customers --\
                                                   v
ECOM_DB.RAW.ORDERS -------> stg_ecom__orders ----+---> int_customers__aggregated_metrics ---> dim_customers
                               |
                               +----------------------------------------------------------> fct_orders
```

## Contribution Guidelines
1. Create a feature branch off `main`.
2. Follow established naming conventions (`stg_`, `int_`, `dim_`, `fct_`).
3. Add schema tests (`unique`, `not_null`, `relationships`) for all new primary and foreign keys.
4. Update documentation in schema YAML files.
5. Open a pull request for review.