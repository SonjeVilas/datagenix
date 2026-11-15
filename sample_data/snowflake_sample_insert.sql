-- =====================================================================
-- Snowflake Sample Setup Script for ECOM_DB.RAW
-- Run this in Snowflake Worksheets to populate sample data
-- =====================================================================

USE DATABASE ECOM_DB;
CREATE SCHEMA IF NOT EXISTS RAW;
USE SCHEMA RAW;

-- 1. Create CUSTOMERS table
CREATE TABLE IF NOT EXISTS CUSTOMERS (
    CUSTOMER_ID NUMBER(38,0),
    FIRST_NAME VARCHAR(100),
    LAST_NAME VARCHAR(100),
    EMAIL VARCHAR(255),
    CREATED_AT TIMESTAMP_NTZ(9)
);

-- 2. Create ORDERS table
CREATE TABLE IF NOT EXISTS ORDERS (
    ORDER_ID NUMBER(38,0),
    CUSTOMER_ID NUMBER(38,0),
    ORDER_DATE DATE,
    STATUS VARCHAR(50),
    TOTAL_AMOUNT NUMBER(10,2)
);

-- 3. Populate sample CUSTOMERS
TRUNCATE TABLE IF EXISTS CUSTOMERS;
INSERT INTO CUSTOMERS (CUSTOMER_ID, FIRST_NAME, LAST_NAME, EMAIL, CREATED_AT) VALUES
    (1, 'Alice', 'Smith', 'alice.smith@example.com', '2024-01-15 08:30:00'),
    (2, 'Bob', 'Jones', 'bob.jones@example.com', '2024-02-20 11:15:00'),
    (3, 'Charlie', 'Brown', 'charlie.brown@example.com', '2024-03-05 14:45:00'),
    (4, 'Diana', 'Prince', 'diana.prince@example.com', '2024-04-10 16:20:00');

-- 4. Populate sample ORDERS
TRUNCATE TABLE IF EXISTS ORDERS;
INSERT INTO ORDERS (ORDER_ID, CUSTOMER_ID, ORDER_DATE, STATUS, TOTAL_AMOUNT) VALUES
    (101, 1, '2024-01-20', 'completed', 150.00),
    (102, 1, '2024-02-14', 'completed', 85.50),
    (103, 2, '2024-02-25', 'pending', 42.00),
    (104, 3, '2024-03-12', 'completed', 310.25),
    (105, 2, '2024-03-18', 'cancelled', 60.00),
    (106, 4, '2024-04-15', 'completed', 220.00);

-- 5. Verification query
SELECT 'CUSTOMERS' AS tbl, COUNT(*) AS row_cnt FROM CUSTOMERS
UNION ALL
SELECT 'ORDERS' AS tbl, COUNT(*) AS row_cnt FROM ORDERS;
