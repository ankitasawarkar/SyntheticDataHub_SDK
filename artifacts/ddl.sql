CREATE TABLE IF NOT EXISTS "Customer" (
  "customer_id" VARCHAR(36) NOT NULL,
  "first_name" VARCHAR(50) NOT NULL,
  "last_name" VARCHAR(50) NOT NULL,
  "date_of_birth" DATE NOT NULL,
  "email" VARCHAR(100),
  "created_at" TIMESTAMP NOT NULL,
  "kyc_status" VARCHAR(20) NOT NULL,
  PRIMARY KEY ("customer_id")
);
CREATE TABLE IF NOT EXISTS "Branch" (
  "branch_id" VARCHAR(16) NOT NULL,
  "branch_name" VARCHAR(100) NOT NULL,
  "city" VARCHAR(50) NOT NULL,
  "country" VARCHAR(50) NOT NULL,
  PRIMARY KEY ("branch_id")
);
CREATE TABLE IF NOT EXISTS "Account" (
  "account_id" VARCHAR(24) NOT NULL,
  "customer_id" VARCHAR(36) NOT NULL,
  "branch_id" VARCHAR(16) NOT NULL,
  "account_type" VARCHAR(20) NOT NULL,
  "currency" VARCHAR(3) NOT NULL,
  "opened_date" DATE NOT NULL,
  "status" VARCHAR(20) NOT NULL,
  "current_balance" DECIMAL(18,2) NOT NULL,
  PRIMARY KEY ("account_id")
);
CREATE TABLE IF NOT EXISTS "Card" (
  "card_id" VARCHAR(24) NOT NULL,
  "account_id" VARCHAR(24) NOT NULL,
  "card_number" VARCHAR(16) NOT NULL,
  "card_type" VARCHAR(20) NOT NULL,
  "issued_date" DATE NOT NULL,
  "expiry_date" DATE NOT NULL,
  "status" VARCHAR(20) NOT NULL,
  PRIMARY KEY ("card_id")
);
CREATE TABLE IF NOT EXISTS "Merchant" (
  "merchant_id" VARCHAR(24) NOT NULL,
  "merchant_name" VARCHAR(100) NOT NULL,
  "category" VARCHAR(50) NOT NULL,
  "country" VARCHAR(50) NOT NULL,
  PRIMARY KEY ("merchant_id")
);
CREATE TABLE IF NOT EXISTS "Transaction" (
  "txn_id" VARCHAR(32) NOT NULL,
  "account_id" VARCHAR(24) NOT NULL,
  "card_id" VARCHAR(24),
  "merchant_id" VARCHAR(24),
  "txn_timestamp" TIMESTAMP NOT NULL,
  "amount" DECIMAL(18,2) NOT NULL,
  "currency" VARCHAR(3) NOT NULL,
  "txn_type" VARCHAR(20) NOT NULL,
  "status" VARCHAR(20) NOT NULL,
  PRIMARY KEY ("txn_id")
);
CREATE TABLE IF NOT EXISTS "Loan" (
  "loan_id" VARCHAR(24) NOT NULL,
  "customer_id" VARCHAR(36) NOT NULL,
  "account_id" VARCHAR(24) NOT NULL,
  "principal_amount" DECIMAL(18,2) NOT NULL,
  "interest_rate" DECIMAL(5,2) NOT NULL,
  "start_date" DATE NOT NULL,
  "end_date" DATE NOT NULL,
  "status" VARCHAR(20) NOT NULL,
  PRIMARY KEY ("loan_id")
);
CREATE TABLE IF NOT EXISTS "LoanPayment" (
  "payment_id" VARCHAR(24) NOT NULL,
  "loan_id" VARCHAR(24) NOT NULL,
  "payment_date" DATE NOT NULL,
  "amount" DECIMAL(18,2) NOT NULL,
  "method" VARCHAR(20) NOT NULL,
  PRIMARY KEY ("payment_id")
);
ALTER TABLE "Account" ADD CONSTRAINT fk_account_customer_id FOREIGN KEY ("customer_id") REFERENCES "Customer"("customer_id");
ALTER TABLE "Account" ADD CONSTRAINT fk_account_branch_id FOREIGN KEY ("branch_id") REFERENCES "Branch"("branch_id");
ALTER TABLE "Card" ADD CONSTRAINT fk_card_account_id FOREIGN KEY ("account_id") REFERENCES "Account"("account_id");
ALTER TABLE "Transaction" ADD CONSTRAINT fk_transaction_account_id FOREIGN KEY ("account_id") REFERENCES "Account"("account_id");
ALTER TABLE "Transaction" ADD CONSTRAINT fk_transaction_card_id FOREIGN KEY ("card_id") REFERENCES "Card"("card_id");
ALTER TABLE "Transaction" ADD CONSTRAINT fk_transaction_merchant_id FOREIGN KEY ("merchant_id") REFERENCES "Merchant"("merchant_id");
ALTER TABLE "Loan" ADD CONSTRAINT fk_loan_customer_id FOREIGN KEY ("customer_id") REFERENCES "Customer"("customer_id");
ALTER TABLE "Loan" ADD CONSTRAINT fk_loan_account_id FOREIGN KEY ("account_id") REFERENCES "Account"("account_id");
ALTER TABLE "LoanPayment" ADD CONSTRAINT fk_loanpayment_loan_id FOREIGN KEY ("loan_id") REFERENCES "Loan"("loan_id");
