-- ============================================================
-- Wealth Management CRM Synthetic Dataset - PostgreSQL DDL
-- Generated from the current corrected Excel schema
-- Load order:
--   1) customers
--   2) advisors
--   3) risk_profiles
--   4) accounts
--   5) portfolios
--   6) holdings
--   7) transactions
--   8) interactions
-- ============================================================

-- Optional cleanup (drop child tables first)
DROP TABLE IF EXISTS interactions;
DROP TABLE IF EXISTS transactions;
DROP TABLE IF EXISTS holdings;
DROP TABLE IF EXISTS portfolios;
DROP TABLE IF EXISTS accounts;
DROP TABLE IF EXISTS risk_profiles;
DROP TABLE IF EXISTS advisors;
DROP TABLE IF EXISTS customers;

CREATE TABLE customers (
    customer_id            INTEGER PRIMARY KEY,
    customer_name          VARCHAR(120) NOT NULL,
    date_of_birth          DATE NOT NULL,
    gender                 VARCHAR(20),
    country                VARCHAR(60) NOT NULL,
    city                   VARCHAR(80) NOT NULL,
    net_worth_band         VARCHAR(30),
    onboarding_date        DATE NOT NULL,
    customer_segment       VARCHAR(40)
);

CREATE TABLE advisors (
    advisor_id             INTEGER PRIMARY KEY,
    advisor_name           VARCHAR(120) NOT NULL,
    region                 VARCHAR(50) NOT NULL,
    country                VARCHAR(60) NOT NULL,
    city                   VARCHAR(80) NOT NULL,
    experience_years       INTEGER NOT NULL,
    specialization         VARCHAR(80)
);

CREATE TABLE risk_profiles (
    risk_profile_id        INTEGER PRIMARY KEY,
    customer_id            INTEGER NOT NULL UNIQUE,
    risk_tolerance         VARCHAR(30) NOT NULL,
    investment_horizon_years INTEGER NOT NULL,
    last_review_date       DATE NOT NULL,
    CONSTRAINT fk_risk_profiles_customer
        FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE accounts (
    account_id             INTEGER PRIMARY KEY,
    customer_id            INTEGER NOT NULL,
    account_type           VARCHAR(40) NOT NULL,
    base_currency          CHAR(3) NOT NULL,
    opened_date            DATE NOT NULL,
    status                 VARCHAR(20) NOT NULL,
    CONSTRAINT fk_accounts_customer
        FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE portfolios (
    portfolio_id           INTEGER PRIMARY KEY,
    account_id             INTEGER NOT NULL,
    portfolio_type         VARCHAR(40) NOT NULL,
    current_value          NUMERIC(18,2) NOT NULL,
    inception_date         DATE NOT NULL,
    CONSTRAINT fk_portfolios_account
        FOREIGN KEY (account_id) REFERENCES accounts(account_id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE holdings (
    holding_id             INTEGER PRIMARY KEY,
    portfolio_id           INTEGER NOT NULL,
    asset_class            VARCHAR(40) NOT NULL,
    instrument_name        VARCHAR(120) NOT NULL,
    quantity               NUMERIC(18,4) NOT NULL,
    market_value           NUMERIC(18,2) NOT NULL,
    CONSTRAINT fk_holdings_portfolio
        FOREIGN KEY (portfolio_id) REFERENCES portfolios(portfolio_id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE transactions (
    transaction_id         INTEGER PRIMARY KEY,
    account_id             INTEGER NOT NULL,
    transaction_date       DATE NOT NULL,
    transaction_type       VARCHAR(40) NOT NULL,
    amount                 NUMERIC(18,2) NOT NULL,
    CONSTRAINT fk_transactions_account
        FOREIGN KEY (account_id) REFERENCES accounts(account_id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE interactions (
    interaction_id         INTEGER PRIMARY KEY,
    customer_id            INTEGER NOT NULL,
    advisor_id             INTEGER NOT NULL,
    interaction_type       VARCHAR(40) NOT NULL,
    interaction_date       DATE NOT NULL,
    sentiment              VARCHAR(20) NOT NULL,
    notes                  TEXT,
    CONSTRAINT fk_interactions_customer
        FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_interactions_advisor
        FOREIGN KEY (advisor_id) REFERENCES advisors(advisor_id)
        ON UPDATE CASCADE ON DELETE RESTRICT
);

-- =====================================
-- Recommended indexes for agent queries
-- =====================================
CREATE INDEX idx_customers_country_city ON customers(country, city);
CREATE INDEX idx_customers_segment ON customers(customer_segment);

CREATE INDEX idx_accounts_customer_id ON accounts(customer_id);
CREATE INDEX idx_accounts_status ON accounts(status);
CREATE INDEX idx_accounts_currency ON accounts(base_currency);

CREATE INDEX idx_risk_profiles_customer_id ON risk_profiles(customer_id);
CREATE INDEX idx_risk_profiles_tolerance ON risk_profiles(risk_tolerance);

CREATE INDEX idx_portfolios_account_id ON portfolios(account_id);
CREATE INDEX idx_portfolios_type ON portfolios(portfolio_type);

CREATE INDEX idx_holdings_portfolio_id ON holdings(portfolio_id);
CREATE INDEX idx_holdings_asset_class ON holdings(asset_class);
CREATE INDEX idx_holdings_instrument_name ON holdings(instrument_name);

CREATE INDEX idx_transactions_account_id ON transactions(account_id);
CREATE INDEX idx_transactions_date ON transactions(transaction_date);
CREATE INDEX idx_transactions_type ON transactions(transaction_type);

CREATE INDEX idx_interactions_customer_id ON interactions(customer_id);
CREATE INDEX idx_interactions_advisor_id ON interactions(advisor_id);
CREATE INDEX idx_interactions_date ON interactions(interaction_date);
CREATE INDEX idx_interactions_sentiment ON interactions(sentiment);

-- =====================================
-- Optional data quality constraints
-- =====================================
ALTER TABLE customers
    ADD CONSTRAINT chk_customers_gender
    CHECK (gender IN ('Male', 'Female'));

ALTER TABLE customers
    ADD CONSTRAINT chk_customers_net_worth_band
    CHECK (net_worth_band IN ('<500K', '500K-1M', '1M-5M', '5M+'));

ALTER TABLE customers
    ADD CONSTRAINT chk_customers_segment
    CHECK (customer_segment IN ('Mass Affluent', 'HNW', 'UHNW'));

ALTER TABLE advisors
    ADD CONSTRAINT chk_advisors_experience_years
    CHECK (experience_years >= 0);

ALTER TABLE risk_profiles
    ADD CONSTRAINT chk_risk_profiles_tolerance
    CHECK (risk_tolerance IN ('Conservative', 'Moderate', 'Aggressive'));

ALTER TABLE risk_profiles
    ADD CONSTRAINT chk_risk_profiles_horizon
    CHECK (investment_horizon_years >= 0);

ALTER TABLE accounts
    ADD CONSTRAINT chk_accounts_type
    CHECK (account_type IN ('Brokerage', 'Retirement', 'Trust', 'Advisory'));

ALTER TABLE accounts
    ADD CONSTRAINT chk_accounts_status
    CHECK (status IN ('Active', 'Closed', 'Restricted'));

ALTER TABLE portfolios
    ADD CONSTRAINT chk_portfolios_type
    CHECK (portfolio_type IN ('Equity', 'Fixed Income', 'Hybrid', 'Goal-Based'));

ALTER TABLE portfolios
    ADD CONSTRAINT chk_portfolios_current_value
    CHECK (current_value >= 0);

ALTER TABLE holdings
    ADD CONSTRAINT chk_holdings_asset_class
    CHECK (asset_class IN ('Equity', 'Bond', 'Mutual Fund', 'ETF', 'Cash'));

ALTER TABLE holdings
    ADD CONSTRAINT chk_holdings_quantity
    CHECK (quantity >= 0);

ALTER TABLE holdings
    ADD CONSTRAINT chk_holdings_market_value
    CHECK (market_value >= 0);

ALTER TABLE transactions
    ADD CONSTRAINT chk_transactions_type
    CHECK (transaction_type IN ('Buy', 'Sell', 'Dividend', 'Contribution', 'Withdrawal', 'Rebalance'));

ALTER TABLE transactions
    ADD CONSTRAINT chk_transactions_amount
    CHECK (amount >= 0);

ALTER TABLE interactions
    ADD CONSTRAINT chk_interactions_type
    CHECK (interaction_type IN ('Call', 'Email', 'Meeting', 'Video Conference'));

ALTER TABLE interactions
    ADD CONSTRAINT chk_interactions_sentiment
    CHECK (sentiment IN ('Positive', 'Neutral', 'Negative'));

-- =====================================
-- COPY examples (PostgreSQL)
-- Convert XLSX to CSV before using COPY, or load through ETL / Python.
-- =====================================
-- COPY customers FROM '/path/customers.csv' WITH (FORMAT csv, HEADER true);
-- COPY advisors FROM '/path/advisors.csv' WITH (FORMAT csv, HEADER true);
-- COPY risk_profiles FROM '/path/risk_profiles.csv' WITH (FORMAT csv, HEADER true);
-- COPY accounts FROM '/path/accounts.csv' WITH (FORMAT csv, HEADER true);
-- COPY portfolios FROM '/path/portfolios.csv' WITH (FORMAT csv, HEADER true);
-- COPY holdings FROM '/path/holdings.csv' WITH (FORMAT csv, HEADER true);
-- COPY transactions FROM '/path/transactions.csv' WITH (FORMAT csv, HEADER true);
-- COPY interactions FROM '/path/interactions.csv' WITH (FORMAT csv, HEADER true);
