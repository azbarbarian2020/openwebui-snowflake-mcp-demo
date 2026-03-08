/*
================================================================================
 OPEN WEBUI + SNOWFLAKE MCP DEMO - COMPLETE SETUP WORKSHEET
================================================================================
 
 This worksheet creates ALL Snowflake objects needed for the demo:
 - Database, Schema, Warehouse
 - Roles and Users (WEST_MANAGER, EAST_MANAGER, WEST_USER, EAST_USER)
 - Sample DRIVERS table with 8 rows
 - Row Access Policy (region-based RLS)
 - Masking Policy (phone number masking for non-admins)
 - Semantic View (for Cortex Analyst)
 - MCP Server (exposes semantic view via MCP protocol)
 
 INSTRUCTIONS:
 1. Run this entire worksheet as ACCOUNTADMIN
 2. After completion, generate PATs for WEST_USER, EAST_USER, and your admin user
 3. Update config/user_credentials.json with the generated PATs
 
 ESTIMATED TIME: 2-3 minutes
================================================================================
*/

-- ============================================================================
-- STEP 1: SET CONTEXT
-- ============================================================================
USE ROLE ACCOUNTADMIN;

-- ============================================================================
-- STEP 2: CREATE DATABASE AND SCHEMA
-- ============================================================================
CREATE DATABASE IF NOT EXISTS SECURITY_WORKSHOP
    COMMENT = 'Demo database for Open WebUI + Snowflake MCP integration';

CREATE SCHEMA IF NOT EXISTS SECURITY_WORKSHOP.TRUCKING
    COMMENT = 'Trucking operations data with RLS and masking policies';

USE DATABASE SECURITY_WORKSHOP;
USE SCHEMA TRUCKING;

-- ============================================================================
-- STEP 3: CREATE WAREHOUSE
-- ============================================================================
CREATE WAREHOUSE IF NOT EXISTS SECURITY_WH
    WAREHOUSE_SIZE = 'XSMALL'
    AUTO_SUSPEND = 60
    AUTO_RESUME = TRUE
    INITIALLY_SUSPENDED = TRUE
    COMMENT = 'Warehouse for security demo queries';

USE WAREHOUSE SECURITY_WH;

-- ============================================================================
-- STEP 4: CREATE ROLES
-- ============================================================================
CREATE ROLE IF NOT EXISTS WEST_MANAGER
    COMMENT = 'Can view WEST region drivers only';

CREATE ROLE IF NOT EXISTS EAST_MANAGER
    COMMENT = 'Can view EAST region drivers only';

-- Grant roles to ACCOUNTADMIN for management
GRANT ROLE WEST_MANAGER TO ROLE ACCOUNTADMIN;
GRANT ROLE EAST_MANAGER TO ROLE ACCOUNTADMIN;

-- ============================================================================
-- STEP 5: CREATE USERS
-- ============================================================================
-- NOTE: Change passwords before running in any non-demo environment!

CREATE USER IF NOT EXISTS WEST_USER
    PASSWORD = 'WestDemo123!'
    DEFAULT_ROLE = WEST_MANAGER
    DEFAULT_WAREHOUSE = SECURITY_WH
    MUST_CHANGE_PASSWORD = FALSE
    COMMENT = 'Demo user for WEST region access';

CREATE USER IF NOT EXISTS EAST_USER
    PASSWORD = 'EastDemo123!'
    DEFAULT_ROLE = EAST_MANAGER
    DEFAULT_WAREHOUSE = SECURITY_WH
    MUST_CHANGE_PASSWORD = FALSE
    COMMENT = 'Demo user for EAST region access';

-- Assign roles to users
GRANT ROLE WEST_MANAGER TO USER WEST_USER;
GRANT ROLE EAST_MANAGER TO USER EAST_USER;

-- ============================================================================
-- STEP 6: GRANT PERMISSIONS TO ROLES
-- ============================================================================
-- Database and schema access
GRANT USAGE ON DATABASE SECURITY_WORKSHOP TO ROLE WEST_MANAGER;
GRANT USAGE ON DATABASE SECURITY_WORKSHOP TO ROLE EAST_MANAGER;

GRANT USAGE ON SCHEMA SECURITY_WORKSHOP.TRUCKING TO ROLE WEST_MANAGER;
GRANT USAGE ON SCHEMA SECURITY_WORKSHOP.TRUCKING TO ROLE EAST_MANAGER;

-- Warehouse access
GRANT USAGE ON WAREHOUSE SECURITY_WH TO ROLE WEST_MANAGER;
GRANT USAGE ON WAREHOUSE SECURITY_WH TO ROLE EAST_MANAGER;

-- ============================================================================
-- STEP 7: CREATE DRIVERS TABLE
-- ============================================================================
CREATE OR REPLACE TABLE SECURITY_WORKSHOP.TRUCKING.DRIVERS (
    DRIVER_ID VARCHAR(10) PRIMARY KEY,
    DRIVER_NAME VARCHAR(100),
    REGION VARCHAR(10),
    PHONE_NUMBER VARCHAR(20),
    LICENSE_CLASS VARCHAR(5),
    YEARS_EXPERIENCE INT,
    SAFETY_RATING DECIMAL(3,2),
    HIRE_DATE DATE
)
COMMENT = 'Driver information with RLS by region and masked phone numbers';

-- Insert sample data: 4 WEST drivers, 4 EAST drivers
INSERT INTO SECURITY_WORKSHOP.TRUCKING.DRIVERS VALUES
    ('DRV001', 'John Martinez', 'WEST', '555-123-4567', 'CDL-A', 8, 4.5, '2017-03-15'),
    ('DRV002', 'Sarah Johnson', 'WEST', '555-234-5678', 'CDL-A', 12, 4.8, '2013-06-22'),
    ('DRV003', 'Mike Chen', 'EAST', '555-345-6789', 'CDL-A', 5, 4.2, '2020-01-10'),
    ('DRV004', 'Emily Davis', 'EAST', '555-456-7890', 'CDL-B', 3, 4.0, '2022-04-05'),
    ('DRV005', 'Robert Wilson', 'WEST', '555-567-8901', 'CDL-A', 15, 4.9, '2010-08-30'),
    ('DRV006', 'Lisa Anderson', 'EAST', '555-678-9012', 'CDL-A', 7, 4.6, '2018-02-14'),
    ('DRV007', 'David Brown', 'WEST', '555-789-0123', 'CDL-B', 4, 4.3, '2021-09-01'),
    ('DRV008', 'Jennifer Taylor', 'EAST', '555-890-1234', 'CDL-A', 9, 4.7, '2016-11-20');

-- Verify data
SELECT * FROM SECURITY_WORKSHOP.TRUCKING.DRIVERS;

-- ============================================================================
-- STEP 8: CREATE ROW ACCESS POLICY (RLS)
-- ============================================================================
CREATE OR REPLACE ROW ACCESS POLICY SECURITY_WORKSHOP.TRUCKING.REGION_RLS
AS (region_val VARCHAR) RETURNS BOOLEAN ->
    CASE
        -- ACCOUNTADMIN sees all data
        WHEN IS_ROLE_IN_SESSION('ACCOUNTADMIN') THEN TRUE
        -- WEST_MANAGER sees only WEST region
        WHEN IS_ROLE_IN_SESSION('WEST_MANAGER') AND region_val = 'WEST' THEN TRUE
        -- EAST_MANAGER sees only EAST region
        WHEN IS_ROLE_IN_SESSION('EAST_MANAGER') AND region_val = 'EAST' THEN TRUE
        -- Default: no access
        ELSE FALSE
    END
COMMENT = 'Restricts driver visibility by region based on user role';

-- Apply RLS policy to DRIVERS table
ALTER TABLE SECURITY_WORKSHOP.TRUCKING.DRIVERS
    ADD ROW ACCESS POLICY SECURITY_WORKSHOP.TRUCKING.REGION_RLS ON (REGION);

-- ============================================================================
-- STEP 9: CREATE MASKING POLICY
-- ============================================================================
CREATE OR REPLACE MASKING POLICY SECURITY_WORKSHOP.TRUCKING.PHONE_MASK
AS (val VARCHAR) RETURNS VARCHAR ->
    CASE
        -- ACCOUNTADMIN sees real phone numbers
        WHEN IS_ROLE_IN_SESSION('ACCOUNTADMIN') THEN val
        -- Everyone else sees MASKED
        ELSE 'MASKED'
    END
COMMENT = 'Masks phone numbers for non-admin users';

-- Apply masking policy to PHONE_NUMBER column
ALTER TABLE SECURITY_WORKSHOP.TRUCKING.DRIVERS
    MODIFY COLUMN PHONE_NUMBER SET MASKING POLICY SECURITY_WORKSHOP.TRUCKING.PHONE_MASK;

-- ============================================================================
-- STEP 10: GRANT TABLE ACCESS TO ROLES
-- ============================================================================
GRANT SELECT ON TABLE SECURITY_WORKSHOP.TRUCKING.DRIVERS TO ROLE WEST_MANAGER;
GRANT SELECT ON TABLE SECURITY_WORKSHOP.TRUCKING.DRIVERS TO ROLE EAST_MANAGER;

-- ============================================================================
-- STEP 11: CREATE SEMANTIC VIEW
-- ============================================================================
CREATE OR REPLACE SEMANTIC VIEW SECURITY_WORKSHOP.TRUCKING.TRUCKING_SEMANTIC_VIEW
    TABLES (
        d AS SECURITY_WORKSHOP.TRUCKING.DRIVERS
            PRIMARY KEY (DRIVER_ID)
            COMMENT = 'Fleet drivers with regions and contact info'
    )
    DIMENSIONS (
        d.driver_id AS d.DRIVER_ID COMMENT = 'Unique driver identifier',
        d.driver_name AS d.DRIVER_NAME COMMENT = 'Driver full name',
        d.region AS d.REGION COMMENT = 'Geographic region (WEST or EAST)',
        d.phone_number AS d.PHONE_NUMBER COMMENT = 'Contact phone number',
        d.license_class AS d.LICENSE_CLASS COMMENT = 'License class (CDL-A or CDL-B)',
        d.hire_date AS d.HIRE_DATE COMMENT = 'Date driver was hired'
    )
    METRICS (
        d.driver_count AS COUNT(*) COMMENT = 'Count of drivers',
        d.avg_experience AS AVG(d.YEARS_EXPERIENCE) COMMENT = 'Average years of experience',
        d.avg_safety AS AVG(d.SAFETY_RATING) COMMENT = 'Average safety rating'
    )
    COMMENT = 'Semantic view for trucking data with RLS and masking';

-- Grant semantic view access to roles
GRANT SELECT ON SEMANTIC VIEW SECURITY_WORKSHOP.TRUCKING.TRUCKING_SEMANTIC_VIEW TO ROLE WEST_MANAGER;
GRANT SELECT ON SEMANTIC VIEW SECURITY_WORKSHOP.TRUCKING.TRUCKING_SEMANTIC_VIEW TO ROLE EAST_MANAGER;

-- ============================================================================
-- STEP 12: CREATE MCP SERVER
-- ============================================================================
CREATE OR REPLACE MCP SERVER SECURITY_WORKSHOP.TRUCKING.TRUCKING_MCP
  FROM SPECIFICATION $$
    tools:
      - name: "trucking-analyst"
        type: "CORTEX_ANALYST_MESSAGE"
        identifier: "SECURITY_WORKSHOP.TRUCKING.TRUCKING_SEMANTIC_VIEW"
        description: "Query trucking operations data including drivers, routes, and fleet information."
        title: "Trucking Data Analyst"
  $$;

-- Grant MCP server access to roles
GRANT USAGE ON MCP SERVER SECURITY_WORKSHOP.TRUCKING.TRUCKING_MCP TO ROLE WEST_MANAGER;
GRANT USAGE ON MCP SERVER SECURITY_WORKSHOP.TRUCKING.TRUCKING_MCP TO ROLE EAST_MANAGER;

-- ============================================================================
-- STEP 13: VERIFY SETUP
-- ============================================================================

-- Test as ACCOUNTADMIN (should see all 8 drivers, real phone numbers)
USE ROLE ACCOUNTADMIN;
SELECT 'ACCOUNTADMIN' AS ROLE, COUNT(*) AS DRIVER_COUNT, 
       MAX(PHONE_NUMBER) AS SAMPLE_PHONE 
FROM SECURITY_WORKSHOP.TRUCKING.DRIVERS;

-- Test as WEST_MANAGER (should see 4 WEST drivers, MASKED phone numbers)
USE ROLE WEST_MANAGER;
SELECT 'WEST_MANAGER' AS ROLE, COUNT(*) AS DRIVER_COUNT, 
       MAX(PHONE_NUMBER) AS SAMPLE_PHONE 
FROM SECURITY_WORKSHOP.TRUCKING.DRIVERS;

-- Test as EAST_MANAGER (should see 4 EAST drivers, MASKED phone numbers)
USE ROLE EAST_MANAGER;
SELECT 'EAST_MANAGER' AS ROLE, COUNT(*) AS DRIVER_COUNT, 
       MAX(PHONE_NUMBER) AS SAMPLE_PHONE 
FROM SECURITY_WORKSHOP.TRUCKING.DRIVERS;

-- Return to ACCOUNTADMIN
USE ROLE ACCOUNTADMIN;

-- ============================================================================
-- STEP 14: SHOW CREATED OBJECTS
-- ============================================================================
SHOW TABLES IN SCHEMA SECURITY_WORKSHOP.TRUCKING;
SHOW ROW ACCESS POLICIES IN SCHEMA SECURITY_WORKSHOP.TRUCKING;
SHOW MASKING POLICIES IN SCHEMA SECURITY_WORKSHOP.TRUCKING;
SHOW SEMANTIC VIEWS IN SCHEMA SECURITY_WORKSHOP.TRUCKING;
SHOW MCP SERVERS IN SCHEMA SECURITY_WORKSHOP.TRUCKING;

-- ============================================================================
-- STEP 15: NETWORK POLICY FOR API ACCESS (IMPORTANT!)
-- ============================================================================
/*
 Network policies control which IP addresses can connect to your Snowflake account.
 For MCP/API access to work, you need to configure a network policy.
 
 Choose ONE of the options below based on your account type:
*/

-- -----------------------------------------------------------------------------
-- OPTION A: Trial/Standard Accounts (Recommended for demos)
-- -----------------------------------------------------------------------------
-- This creates a permissive policy allowing API access from any IP.
-- Simple and works immediately for trial accounts.

CREATE NETWORK POLICY IF NOT EXISTS api_access_policy
    ALLOWED_IP_LIST = ('0.0.0.0/0')
    COMMENT = 'Allow API access for MCP demo';

ALTER ACCOUNT SET NETWORK_POLICY = api_access_policy;

-- -----------------------------------------------------------------------------
-- OPTION B: Internal Snowflake Accounts (SE Demo Accounts)
-- -----------------------------------------------------------------------------
-- Internal Snowflake accounts often have existing network policies.
-- You may need to modify the existing policy instead of creating a new one.
--
-- First, check your current network policy:
-- SHOW PARAMETERS LIKE 'NETWORK_POLICY' IN ACCOUNT;
-- SHOW NETWORK POLICIES;
-- DESCRIBE NETWORK POLICY <your_policy_name>;
--
-- If you have an existing policy, you can either:
-- 1. Add your IP to the existing policy's ALLOWED_IP_LIST
-- 2. Work with your admin to ensure API access is allowed
--
-- Example to modify existing policy:
-- ALTER NETWORK POLICY <existing_policy> SET ALLOWED_IP_LIST = ('0.0.0.0/0', '<existing_ips>');

-- -----------------------------------------------------------------------------
-- OPTION C: Enterprise Accounts with Strict Security
-- -----------------------------------------------------------------------------
-- For production or security-conscious environments, restrict to specific IPs:
--
-- CREATE NETWORK POLICY IF NOT EXISTS api_access_policy
--     ALLOWED_IP_LIST = ('your.ip.address/32', 'another.ip/32')
--     COMMENT = 'Restricted API access for MCP demo';
-- ALTER ACCOUNT SET NETWORK_POLICY = api_access_policy;
--
-- To find your current IP: curl ifconfig.me

-- ============================================================================
-- STEP 16: VERIFY NETWORK POLICY
-- ============================================================================
SHOW PARAMETERS LIKE 'NETWORK_POLICY' IN ACCOUNT;

/*
================================================================================
 SETUP COMPLETE!
================================================================================

 NEXT STEPS:
 
 1. Generate Personal Access Tokens (PATs) for each user:
    - Go to Snowsight > User Menu > My Profile > Authentication
    - Click "Generate New Token"
    - Create PATs for: WEST_USER, EAST_USER, and your admin user
    - Set expiration to at least 30 days for demo purposes
 
 2. Update config/user_credentials.json with the PATs
 
 3. Note your account identifier for the MCP endpoint URL:
    - Trial accounts: abc12345.snowflakecomputing.com
    - Enterprise accounts: orgname-accountname.snowflakecomputing.com
 
 EXPECTED RESULTS:
 ┌─────────────────┬──────────────┬─────────────────┐
 │ User/Role       │ Drivers Seen │ Phone Numbers   │
 ├─────────────────┼──────────────┼─────────────────┤
 │ ACCOUNTADMIN    │ 8 (all)      │ Visible         │
 │ WEST_MANAGER    │ 4 (WEST)     │ MASKED          │
 │ EAST_MANAGER    │ 4 (EAST)     │ MASKED          │
 └─────────────────┴──────────────┴─────────────────┘

================================================================================
*/
