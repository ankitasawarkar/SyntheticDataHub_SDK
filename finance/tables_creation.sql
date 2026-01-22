CREATE TABLE IF NOT EXISTS public."Customer" (
    customer_id varchar(36) NOT NULL,
    first_name varchar(50) NOT NULL,
    last_name varchar(50) NOT NULL,
    date_of_birth date NOT NULL,
    email varchar(100),
    ssn varchar(11),
    marketing_opt_in integer,
    loyalty_points integer,
    created_at timestamp NOT NULL,
    kyc_status varchar(20) NOT NULL,
    CONSTRAINT "Customer_pkey" PRIMARY KEY (customer_id)
);

CREATE TABLE IF NOT EXISTS public."Branch" (
    branch_id varchar(16) NOT NULL,
    branch_name varchar(100) NOT NULL,
    city varchar(50) NOT NULL,
    country varchar(50) NOT NULL,
    employee_count integer,
    CONSTRAINT "Branch_pkey" PRIMARY KEY (branch_id)
);

CREATE TABLE IF NOT EXISTS public."Account" (
    account_id varchar(24) NOT NULL,
    customer_id varchar(36) NOT NULL,
    branch_id varchar(16) NOT NULL,
    account_type varchar(20) NOT NULL,
    currency varchar(3) NOT NULL,
    opened_date date NOT NULL,
    status varchar(20) NOT NULL,
    current_balance numeric(18,2) NOT NULL,
    CONSTRAINT "Account_pkey" PRIMARY KEY (account_id),
    CONSTRAINT fk_account_branch_id FOREIGN KEY (branch_id)
        REFERENCES public."Branch" (branch_id),
    CONSTRAINT fk_account_customer_id FOREIGN KEY (customer_id)
        REFERENCES public."Customer" (customer_id)
);

CREATE TABLE IF NOT EXISTS public."Card" (
    card_id varchar(24) NOT NULL,
    account_id varchar(24) NOT NULL,
    card_number varchar(16) NOT NULL,
    card_type varchar(20) NOT NULL,
    issued_date date NOT NULL,
    expiry_date date NOT NULL,
    status varchar(20) NOT NULL,
    CONSTRAINT "Card_pkey" PRIMARY KEY (card_id),
    CONSTRAINT fk_card_account_id FOREIGN KEY (account_id)
        REFERENCES public."Account" (account_id)
);

CREATE TABLE IF NOT EXISTS public."Merchant" (
    merchant_id varchar(24) NOT NULL,
    merchant_name varchar(100) NOT NULL,
    category varchar(50) NOT NULL,
    country varchar(50) NOT NULL,
    CONSTRAINT "Merchant_pkey" PRIMARY KEY (merchant_id)
);

CREATE TABLE IF NOT EXISTS public."Loan" (
    loan_id varchar(24) NOT NULL,
    customer_id varchar(36) NOT NULL,
    account_id varchar(24) NOT NULL,
    principal_amount numeric(18,2) NOT NULL,
    interest_rate numeric(5,2) NOT NULL,
    start_date date NOT NULL,
    end_date date NOT NULL,
    status varchar(20) NOT NULL,
    CONSTRAINT "Loan_pkey" PRIMARY KEY (loan_id),
    CONSTRAINT fk_loan_account_id FOREIGN KEY (account_id)
        REFERENCES public."Account" (account_id),
    CONSTRAINT fk_loan_customer_id FOREIGN KEY (customer_id)
        REFERENCES public."Customer" (customer_id)
);

CREATE TABLE IF NOT EXISTS public."LoanPayment" (
    payment_id varchar(24) NOT NULL,
    loan_id varchar(24) NOT NULL,
    payment_date date NOT NULL,
    amount numeric(18,2) NOT NULL,
    method varchar(20) NOT NULL,
    CONSTRAINT "LoanPayment_pkey" PRIMARY KEY (payment_id),
    CONSTRAINT fk_loanpayment_loan_id FOREIGN KEY (loan_id)
        REFERENCES public."Loan" (loan_id)
);

CREATE TABLE IF NOT EXISTS public."Transaction" (
    txn_id varchar(32) NOT NULL,
    account_id varchar(24) NOT NULL,
    card_id varchar(24),
    merchant_id varchar(24),
    txn_timestamp timestamp NOT NULL,
    amount numeric(18,2) NOT NULL,
    currency varchar(3) NOT NULL,
    exchange_rate double precision,
    txn_type varchar(20) NOT NULL,
    status varchar(20) NOT NULL,
    CONSTRAINT "Transaction_pkey" PRIMARY KEY (txn_id),
    CONSTRAINT fk_transaction_account_id FOREIGN KEY (account_id)
        REFERENCES public."Account" (account_id),
    CONSTRAINT fk_transaction_card_id FOREIGN KEY (card_id)
        REFERENCES public."Card" (card_id),
    CONSTRAINT fk_transaction_merchant_id FOREIGN KEY (merchant_id)
        REFERENCES public."Merchant" (merchant_id)
);

---------Join Query------------
SELECT account_id, customer_id, branch_id, account_type, currency, opened_date, status, current_balance
	FROM public."Account";

SELECT merchant_id, merchant_name, category, country
	FROM public."Merchant";

SELECT c.customer_id, c.first_name, c.last_name, c.email, b.branch_id, b.branch_name, 
-- Transactions 
COUNT(DISTINCT t.txn_id)     AS transaction_count, COALESCE(SUM(t.amount), 0)  AS total_transaction_amount, 
-- Loans 
COUNT(DISTINCT l.loan_id)   AS loan_count, COALESCE(SUM(l.principal_amount), 0) AS total_loan_principal 
FROM "Customer"   c 
JOIN "Account"    a ON a.customer_id = c.customer_id 
JOIN "Branch" b ON a.branch_id   = b.branch_id 
LEFT JOIN "Transaction" t ON t.account_id = a.account_id 
LEFT JOIN "Loan"    l ON l.account_id = a.account_id 
-- active loans and posted transactions
-- LEFT JOIN "Transaction" t ON t.account_id = a.account_id AND t.status = 'POSTED' 
-- LEFT JOIN "Loan"    l ON l.account_id = a.account_id AND l.status = 'ACTIVE' 
GROUP BY c.customer_id, c.first_name, c.last_name, c.email, b.branch_id, b.branch_name 
ORDER BY c.customer_id, b.branch_id;
