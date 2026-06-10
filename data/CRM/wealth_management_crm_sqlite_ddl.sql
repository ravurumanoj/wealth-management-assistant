-- ============================================================
-- Wealth Management CRM Synthetic Dataset - SQLite DDL
-- Generated from the current corrected Excel schema
-- Notes:
--   * SQLite requires PRAGMA foreign_keys = ON for FK enforcement.
--   * Recommended load order:
--       1) customers
--       2) advisors
--       3) risk_profiles
--       4) accounts
--       5) portfolios
--       6) holdings
--       7) transactions
--       8) interactions
-- ============================================================

PRAGMA foreign_keys = ON;

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
    customer_name          TEXT NOT NULL,
    date_of_birth          TEXT NOT NULL,
    gender                 TEXT,
    country                TEXT NOT NULL,
    city                   TEXT NOT NULL,
    net_worth_band         TEXT,
    onboarding_date        TEXT NOT NULL,
    customer_segment       TEXT,
    CHECK (gender IN ('Male', 'Female') OR gender IS NULL),
    CHECK (net_worth_band IN ('<500K', '500K-1M', '1M-5M', '5M+') OR net_worth_band IS NULL),
    CHECK (customer_segment IN ('Mass Affluent', 'HNW', 'UHNW') OR customer_segment IS NULL)
);

CREATE TABLE advisors (
    advisor_id             INTEGER PRIMARY KEY,
    advisor_name           TEXT NOT NULL,
    region                 TEXT NOT NULL,
    country                TEXT NOT NULL,
    city                   TEXT NOT NULL,
    experience_years       INTEGER NOT NULL,
    specialization         TEXT,
    CHECK (experience_years >= 0)
);

CREATE TABLE risk_profiles (
    risk_profile_id          INTEGER PRIMARY KEY,
    customer_id              INTEGER NOT NULL UNIQUE,
    risk_tolerance           TEXT NOT NULL,
    investment_horizon_years INTEGER NOT NULL,
    last_review_date         TEXT NOT NULL,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CHECK (risk_tolerance IN ('Conservative', 'Moderate', 'Aggressive')),
    CHECK (investment_horizon_years >= 0)
);

CREATE TABLE accounts (
    account_id             INTEGER PRIMARY KEY,
    customer_id            INTEGER NOT NULL,
    account_type           TEXT NOT NULL,
    base_currency          TEXT NOT NULL,
    opened_date            TEXT NOT NULL,
    status                 TEXT NOT NULL,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CHECK (account_type IN ('Brokerage', 'Retirement', 'Trust', 'Advisory')),
    CHECK (status IN ('Active', 'Closed', 'Restricted')),
    CHECK (length(base_currency) = 3)
);

CREATE TABLE portfolios (
    portfolio_id           INTEGER PRIMARY KEY,
    account_id             INTEGER NOT NULL,
    portfolio_type         TEXT NOT NULL,
    current_value          NUMERIC NOT NULL,
    inception_date         TEXT NOT NULL,
    FOREIGN KEY (account_id) REFERENCES accounts(account_id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CHECK (portfolio_type IN ('Equity', 'Fixed Income', 'Hybrid', 'Goal-Based')),
    CHECK (current_value >= 0)
);

CREATE TABLE holdings (
    holding_id             INTEGER PRIMARY KEY,
    portfolio_id           INTEGER NOT NULL,
    asset_class            TEXT NOT NULL,
    instrument_name        TEXT NOT NULL,
    quantity               NUMERIC NOT NULL,
    market_value           NUMERIC NOT NULL,
    FOREIGN KEY (portfolio_id) REFERENCES portfolios(portfolio_id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CHECK (asset_class IN ('Equity', 'Bond', 'Mutual Fund', 'ETF', 'Cash')),
    CHECK (quantity >= 0),
    CHECK (market_value >= 0)
);

CREATE TABLE transactions (
    transaction_id         INTEGER PRIMARY KEY,
    account_id             INTEGER NOT NULL,
    transaction_date       TEXT NOT NULL,
    transaction_type       TEXT NOT NULL,
    amount                 NUMERIC NOT NULL,
    FOREIGN KEY (account_id) REFERENCES accounts(account_id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CHECK (transaction_type IN ('Buy', 'Sell', 'Dividend', 'Contribution', 'Withdrawal', 'Rebalance')),
    CHECK (amount >= 0)
);

CREATE TABLE interactions (
    interaction_id         INTEGER PRIMARY KEY,
    customer_id            INTEGER NOT NULL,
    advisor_id             INTEGER NOT NULL,
    interaction_type       TEXT NOT NULL,
    interaction_date       TEXT NOT NULL,
    sentiment              TEXT NOT NULL,
    notes                  TEXT,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY (advisor_id) REFERENCES advisors(advisor_id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CHECK (interaction_type IN ('Call', 'Email', 'Meeting', 'Video Conference')),
    CHECK (sentiment IN ('Positive', 'Neutral', 'Negative'))
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
