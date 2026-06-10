import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random
from pathlib import Path

# Deterministic output matching corrected dataset logic
np.random.seed(123)
random.seed(123)

# -----------------------------
# Parameters
# -----------------------------
n_customers = 1000
n_advisors = 50
n_accounts = 1500
n_portfolios = 2500
n_holdings = 5000
n_transactions = 15000
n_interactions = 6000

# -----------------------------
# Reference data
# -----------------------------
country_city_map = {
    "USA": ["New York", "San Francisco", "Chicago", "Boston", "Miami", "Seattle"],
    "UK": ["London", "Manchester", "Edinburgh", "Birmingham", "Bristol", "Leeds"],
    "Germany": ["Berlin", "Munich", "Frankfurt", "Hamburg", "Cologne", "Stuttgart"],
    "France": ["Paris", "Lyon", "Marseille", "Nice", "Toulouse", "Bordeaux"],
    "Canada": ["Toronto", "Vancouver", "Montreal", "Calgary", "Ottawa", "Edmonton"]
}
country_currency_map = {"USA": "USD", "UK": "GBP", "Germany": "EUR", "France": "EUR", "Canada": "CAD"}
first_names = [
    "James", "Mary", "John", "Patricia", "Robert", "Jennifer", "Michael", "Linda", "William", "Elizabeth",
    "David", "Barbara", "Richard", "Susan", "Joseph", "Jessica", "Thomas", "Sarah", "Charles", "Karen",
    "Daniel", "Nancy", "Matthew", "Lisa", "Anthony", "Betty", "Mark", "Sandra", "Donald", "Ashley",
    "Paul", "Emily", "Steven", "Donna", "Andrew", "Michelle", "Joshua", "Carol", "Kenneth", "Amanda",
    "Christopher", "Melissa", "George", "Deborah", "Edward", "Stephanie", "Brian", "Rebecca", "Ronald", "Laura",
    "Emma", "Olivia", "Liam", "Noah", "Sophia", "Isabella", "Lucas", "Mia", "Ethan", "Charlotte"
]
last_names = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez",
    "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin",
    "Lee", "Perez", "Thompson", "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson",
    "Walker", "Young", "Allen", "King", "Wright", "Scott", "Green", "Baker", "Adams", "Nelson",
    "Hall", "Campbell", "Turner", "Carter", "Phillips", "Parker", "Evans", "Edwards", "Collins", "Stewart"
]
advisor_specializations = ["Retirement Planning", "Tax Optimization", "Portfolio Management", "Estate Planning", "Wealth Preservation"]
account_types = ["Brokerage", "Retirement", "Trust", "Advisory"]
portfolio_types = ["Equity", "Fixed Income", "Hybrid", "Goal-Based"]
asset_classes = ["Equity", "Bond", "Mutual Fund", "ETF", "Cash"]
instruments_by_asset = {
    "Equity": ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "TSLA", "JPM", "V", "UNH", "NESN"],
    "Bond": ["UST 5Y", "UST 10Y", "Corp Bond A", "Corp Bond B", "Euro Gov Bond", "UK Gilt 2030"],
    "Mutual Fund": ["Global Growth Fund", "Balanced Income Fund", "US Bluechip Fund", "Euro Equity Fund"],
    "ETF": ["SPY", "QQQ", "VTI", "VGK", "EWU", "XIC"],
    "Cash": ["USD Cash", "EUR Cash", "GBP Cash", "CAD Cash"]
}
interaction_types = ["Call", "Email", "Meeting", "Video Conference"]
transaction_types = ["Buy", "Sell", "Dividend", "Contribution", "Withdrawal", "Rebalance"]
positive_notes = [
    "Client appreciated the portfolio review and agreed with the proposed allocation changes.",
    "Positive discussion on long-term goals; client is comfortable with the current strategy.",
    "Client expressed satisfaction with recent performance and welcomed follow-up next quarter.",
    "Meeting went well; client approved the recommended diversification plan.",
    "Constructive conversation with strong engagement; client requested additional retirement scenarios."
]
neutral_notes = [
    "Routine check-in completed; no major changes requested at this time.",
    "Provided account update and answered standard questions on holdings and recent activity.",
    "Client reviewed the summary materials and asked for periodic monitoring to continue.",
    "Interaction focused on regular portfolio maintenance with no urgent actions identified.",
    "General discussion on market conditions; client prefers to maintain the current plan for now."
]
negative_notes = [
    "Client raised concerns about recent volatility and requested a detailed risk review.",
    "Discussion reflected dissatisfaction with short-term performance; follow-up has been scheduled.",
    "Client requested clarification on fees and portfolio positioning after recent market movements.",
    "Interaction indicated frustration regarding drawdowns; advisor to prepare mitigation options.",
    "Client expressed concern over communication frequency and expects a more proactive update cadence."
]
net_worth_bands = ["<500K", "500K-1M", "1M-5M", "5M+"]
net_worth_probs = [0.30, 0.30, 0.28, 0.12]
customer_segments = ["Mass Affluent", "HNW", "UHNW"]
segment_probs = [0.50, 0.35, 0.15]
risk_levels = ["Conservative", "Moderate", "Aggressive"]
risk_probs = [0.30, 0.45, 0.25]

def random_name():
    return f"{random.choice(first_names)} {random.choice(last_names)}"

def random_date(start_date, end_date):
    delta_days = (end_date - start_date).days
    return start_date + timedelta(days=random.randint(0, delta_days))

# Generate customers
customer_ids = np.arange(1, n_customers + 1)
customer_countries = np.random.choice(list(country_city_map.keys()), size=n_customers, p=[0.35, 0.20, 0.15, 0.15, 0.15])
customer_cities = [random.choice(country_city_map[c]) for c in customer_countries]
customers = pd.DataFrame({
    "customer_id": customer_ids,
    "customer_name": [random_name() for _ in range(n_customers)],
    "date_of_birth": [random_date(datetime(1948,1,1), datetime(1997,12,31)).date().isoformat() for _ in range(n_customers)],
    "gender": np.random.choice(["Male","Female"], size=n_customers),
    "country": customer_countries,
    "city": customer_cities,
    "net_worth_band": np.random.choice(net_worth_bands, size=n_customers, p=net_worth_probs),
    "onboarding_date": [random_date(datetime(2015,1,1), datetime(2025,3,31)).date().isoformat() for _ in range(n_customers)],
    "customer_segment": np.random.choice(customer_segments, size=n_customers, p=segment_probs)
})

# Generate advisors
advisor_ids = np.arange(1, n_advisors + 1)
advisor_regions = np.random.choice(["North America", "Europe"], size=n_advisors, p=[0.6, 0.4])
advisor_country = [random.choice(["USA", "Canada"]) if r == "North America" else random.choice(["UK", "Germany", "France"]) for r in advisor_regions]
advisor_city = [random.choice(country_city_map[c]) for c in advisor_country]
advisors = pd.DataFrame({
    "advisor_id": advisor_ids,
    "advisor_name": [random_name() for _ in range(n_advisors)],
    "region": advisor_regions,
    "country": advisor_country,
    "city": advisor_city,
    "experience_years": np.random.randint(3,26,size=n_advisors),
    "specialization": np.random.choice(advisor_specializations, size=n_advisors)
})
customer_primary_advisor = pd.Series(np.random.choice(advisors["advisor_id"], size=n_customers), index=customers["customer_id"])

risk_profiles = pd.DataFrame({
    "risk_profile_id": np.arange(1, n_customers + 1),
    "customer_id": customers["customer_id"],
    "risk_tolerance": np.random.choice(risk_levels, size=n_customers, p=risk_probs),
    "investment_horizon_years": np.random.randint(1,26,size=n_customers),
    "last_review_date": [random_date(datetime(2023,1,1), datetime(2026,5,31)).date().isoformat() for _ in range(n_customers)]
})

account_customer_ids = np.random.choice(customers["customer_id"], size=n_accounts)
customer_country_lookup = customers.set_index('customer_id')['country'].to_dict()
accounts = pd.DataFrame({
    "account_id": np.arange(1, n_accounts+1),
    "customer_id": account_customer_ids,
    "account_type": np.random.choice(account_types, size=n_accounts, p=[0.45,0.25,0.15,0.15]),
    "base_currency": [country_currency_map[customer_country_lookup[cid]] for cid in account_customer_ids],
    "opened_date": [random_date(datetime(2016,1,1), datetime(2026,3,31)).date().isoformat() for _ in range(n_accounts)],
    "status": np.random.choice(["Active","Closed","Restricted"], size=n_accounts, p=[0.84,0.12,0.04])
})

portfolios = pd.DataFrame({
    "portfolio_id": np.arange(1, n_portfolios+1),
    "account_id": np.random.choice(accounts['account_id'], size=n_portfolios),
    "portfolio_type": np.random.choice(portfolio_types, size=n_portfolios, p=[0.35,0.25,0.30,0.10]),
    "current_value": np.round(np.random.lognormal(mean=12.0, sigma=0.9, size=n_portfolios), 2),
    "inception_date": [random_date(datetime(2017,1,1), datetime(2026,3,31)).date().isoformat() for _ in range(n_portfolios)]
})
portfolios['current_value'] = portfolios['current_value'].clip(lower=10000, upper=7500000)

holding_asset = np.random.choice(asset_classes, size=n_holdings, p=[0.35,0.20,0.20,0.20,0.05])
holding_instruments = [random.choice(instruments_by_asset[a]) for a in holding_asset]
quantities=[]; market_values=[]
for asset in holding_asset:
    if asset in ["Equity","ETF"]:
        q=random.randint(10,1000); mv=round(q*random.uniform(20,450),2)
    elif asset=="Bond":
        q=random.randint(5,300); mv=round(q*random.uniform(80,1200),2)
    elif asset=="Mutual Fund":
        q=random.randint(20,2500); mv=round(q*random.uniform(8,120),2)
    else:
        q=1; mv=round(random.uniform(1000,150000),2)
    quantities.append(q); market_values.append(mv)
holdings = pd.DataFrame({
    "holding_id": np.arange(1, n_holdings+1),
    "portfolio_id": np.random.choice(portfolios['portfolio_id'], size=n_holdings),
    "asset_class": holding_asset,
    "instrument_name": holding_instruments,
    "quantity": quantities,
    "market_value": market_values
})

transactions = pd.DataFrame({
    "transaction_id": np.arange(1, n_transactions+1),
    "account_id": np.random.choice(accounts['account_id'], size=n_transactions),
    "transaction_date": [random_date(datetime(2020,1,1), datetime(2026,5,31)).date().isoformat() for _ in range(n_transactions)],
    "transaction_type": np.random.choice(transaction_types, size=n_transactions, p=[0.33,0.20,0.10,0.17,0.10,0.10]),
    "amount": np.round(np.random.lognormal(mean=8.7, sigma=1.0, size=n_transactions), 2)
})
transactions['amount'] = transactions['amount'].clip(lower=50, upper=250000)

interaction_customer_ids = np.random.choice(customers['customer_id'], size=n_interactions)
interaction_advisor_ids = []
for cid in interaction_customer_ids:
    interaction_advisor_ids.append(int(customer_primary_advisor.loc[cid]) if random.random() < 0.75 else int(random.choice(advisors['advisor_id'].tolist())))

sentiments = np.random.choice(["Positive","Neutral","Negative"], size=n_interactions, p=[0.52,0.33,0.15])
notes=[]
for s in sentiments:
    notes.append(random.choice(positive_notes if s=="Positive" else neutral_notes if s=="Neutral" else negative_notes))
interactions = pd.DataFrame({
    "interaction_id": np.arange(1, n_interactions+1),
    "customer_id": interaction_customer_ids,
    "advisor_id": interaction_advisor_ids,
    "interaction_type": np.random.choice(interaction_types, size=n_interactions, p=[0.30,0.30,0.25,0.15]),
    "interaction_date": [random_date(datetime(2021,1,1), datetime(2026,5,31)).date().isoformat() for _ in range(n_interactions)],
    "sentiment": sentiments,
    "notes": notes
})

# Validate
assert all(city in country_city_map[country] for country, city in zip(customers['country'], customers['city']))
assert customers['customer_name'].str.strip().ne('').all()
assert advisors['advisor_name'].str.strip().ne('').all()
assert interactions['notes'].str.strip().ne('').all()

# SQLite DDL
sqlite_ddl = '''
PRAGMA foreign_keys = ON;
DROP TABLE IF EXISTS interactions;
DROP TABLE IF EXISTS transactions;
DROP TABLE IF EXISTS holdings;
DROP TABLE IF EXISTS portfolios;
DROP TABLE IF EXISTS accounts;
DROP TABLE IF EXISTS risk_profiles;
DROP TABLE IF EXISTS advisors;
DROP TABLE IF EXISTS customers;
CREATE TABLE customers (
    customer_id INTEGER PRIMARY KEY,
    customer_name TEXT NOT NULL,
    date_of_birth TEXT NOT NULL,
    gender TEXT,
    country TEXT NOT NULL,
    city TEXT NOT NULL,
    net_worth_band TEXT,
    onboarding_date TEXT NOT NULL,
    customer_segment TEXT,
    CHECK (gender IN ('Male', 'Female') OR gender IS NULL),
    CHECK (net_worth_band IN ('<500K', '500K-1M', '1M-5M', '5M+') OR net_worth_band IS NULL),
    CHECK (customer_segment IN ('Mass Affluent', 'HNW', 'UHNW') OR customer_segment IS NULL)
);
CREATE TABLE advisors (
    advisor_id INTEGER PRIMARY KEY,
    advisor_name TEXT NOT NULL,
    region TEXT NOT NULL,
    country TEXT NOT NULL,
    city TEXT NOT NULL,
    experience_years INTEGER NOT NULL,
    specialization TEXT,
    CHECK (experience_years >= 0)
);
CREATE TABLE risk_profiles (
    risk_profile_id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL UNIQUE,
    risk_tolerance TEXT NOT NULL,
    investment_horizon_years INTEGER NOT NULL,
    last_review_date TEXT NOT NULL,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id) ON UPDATE CASCADE ON DELETE CASCADE,
    CHECK (risk_tolerance IN ('Conservative', 'Moderate', 'Aggressive')),
    CHECK (investment_horizon_years >= 0)
);
CREATE TABLE accounts (
    account_id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL,
    account_type TEXT NOT NULL,
    base_currency TEXT NOT NULL,
    opened_date TEXT NOT NULL,
    status TEXT NOT NULL,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id) ON UPDATE CASCADE ON DELETE CASCADE,
    CHECK (account_type IN ('Brokerage', 'Retirement', 'Trust', 'Advisory')),
    CHECK (status IN ('Active', 'Closed', 'Restricted')),
    CHECK (length(base_currency) = 3)
);
CREATE TABLE portfolios (
    portfolio_id INTEGER PRIMARY KEY,
    account_id INTEGER NOT NULL,
    portfolio_type TEXT NOT NULL,
    current_value NUMERIC NOT NULL,
    inception_date TEXT NOT NULL,
    FOREIGN KEY (account_id) REFERENCES accounts(account_id) ON UPDATE CASCADE ON DELETE CASCADE,
    CHECK (portfolio_type IN ('Equity', 'Fixed Income', 'Hybrid', 'Goal-Based')),
    CHECK (current_value >= 0)
);
CREATE TABLE holdings (
    holding_id INTEGER PRIMARY KEY,
    portfolio_id INTEGER NOT NULL,
    asset_class TEXT NOT NULL,
    instrument_name TEXT NOT NULL,
    quantity NUMERIC NOT NULL,
    market_value NUMERIC NOT NULL,
    FOREIGN KEY (portfolio_id) REFERENCES portfolios(portfolio_id) ON UPDATE CASCADE ON DELETE CASCADE,
    CHECK (asset_class IN ('Equity', 'Bond', 'Mutual Fund', 'ETF', 'Cash')),
    CHECK (quantity >= 0),
    CHECK (market_value >= 0)
);
CREATE TABLE transactions (
    transaction_id INTEGER PRIMARY KEY,
    account_id INTEGER NOT NULL,
    transaction_date TEXT NOT NULL,
    transaction_type TEXT NOT NULL,
    amount NUMERIC NOT NULL,
    FOREIGN KEY (account_id) REFERENCES accounts(account_id) ON UPDATE CASCADE ON DELETE CASCADE,
    CHECK (transaction_type IN ('Buy', 'Sell', 'Dividend', 'Contribution', 'Withdrawal', 'Rebalance')),
    CHECK (amount >= 0)
);
CREATE TABLE interactions (
    interaction_id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL,
    advisor_id INTEGER NOT NULL,
    interaction_type TEXT NOT NULL,
    interaction_date TEXT NOT NULL,
    sentiment TEXT NOT NULL,
    notes TEXT,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id) ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY (advisor_id) REFERENCES advisors(advisor_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CHECK (interaction_type IN ('Call', 'Email', 'Meeting', 'Video Conference')),
    CHECK (sentiment IN ('Positive', 'Neutral', 'Negative'))
);
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
'''

db_path = './wealth-management-assistant/data/CRM/crm_wm.db'
if Path(db_path).exists():
    Path(db_path).unlink()

conn = sqlite3.connect(db_path)
conn.execute('PRAGMA foreign_keys = ON;')
conn.executescript(sqlite_ddl)

# Load in FK-safe order
customers.to_sql('customers', conn, if_exists='append', index=False)
advisors.to_sql('advisors', conn, if_exists='append', index=False)
risk_profiles.to_sql('risk_profiles', conn, if_exists='append', index=False)
accounts.to_sql('accounts', conn, if_exists='append', index=False)
portfolios.to_sql('portfolios', conn, if_exists='append', index=False)
holdings.to_sql('holdings', conn, if_exists='append', index=False)
transactions.to_sql('transactions', conn, if_exists='append', index=False)
interactions.to_sql('interactions', conn, if_exists='append', index=False)

# Sanity checks
counts = {}
for table in ['customers','advisors','risk_profiles','accounts','portfolios','holdings','transactions','interactions']:
    counts[table] = conn.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]

fk_check = conn.execute('PRAGMA foreign_key_check;').fetchall()
conn.commit()
conn.close()

summary = {
    'db_path': db_path,
    'counts': counts,
    'fk_violations': len(fk_check),
    'db_size_bytes': Path(db_path).stat().st_size
}
print(summary)