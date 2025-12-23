# Verification Queries for SyntheticDataHub SDK

This document collects useful SQL queries to validate and explore the synthetic data loaded into Postgres by the SDK.

All examples assume you are using Docker Compose and the default database `finance_synth`.

## Connecting to Postgres

From the project root:

```powershell
docker compose exec -it postgres psql -U postgres -d finance_synth
```

Inside `psql` you should see a prompt like:

```text
finance_synth=#
```

Useful `psql` commands:

- List tables: `\dt`
- Switch database: `\c finance_synth`
- Quit: `\q`

## 1. Row Counts per Table

Quick overview of how many rows are in each business table:

```sql
SELECT 'Customer'    AS table_name, COUNT(*) AS rows FROM "Customer"
UNION ALL
SELECT 'Branch',     COUNT(*) FROM "Branch"
UNION ALL
SELECT 'Account',    COUNT(*) FROM "Account"
UNION ALL
SELECT 'Card',       COUNT(*) FROM "Card"
UNION ALL
SELECT 'Merchant',   COUNT(*) FROM "Merchant"
UNION ALL
SELECT 'Transaction',COUNT(*) FROM "Transaction"
UNION ALL
SELECT 'Loan',       COUNT(*) FROM "Loan"
UNION ALL
SELECT 'LoanPayment',COUNT(*) FROM "LoanPayment";
```

## 2. Customer → Account → Transaction Coverage

Top customers by activity across accounts and transactions:

```sql
SELECT
  c.customer_id,
  COUNT(DISTINCT a.account_id)    AS account_count,
  COUNT(DISTINCT t.txn_id)        AS txn_count,
  SUM(t.amount)                   AS total_txn_amount
FROM "Customer" c
LEFT JOIN "Account" a
  ON a.customer_id = c.customer_id
LEFT JOIN "Transaction" t
  ON t.account_id = a.account_id
GROUP BY c.customer_id
ORDER BY txn_count DESC
LIMIT 10;
```

This lets you check that:

- Customers have accounts.
- Accounts have transactions.
- Amounts look reasonable and non-zero.

## 3. Loan vs. Loan Payments Consistency

Compare total payments to principal per loan.

Treat missing payments as zero:

```sql
SELECT
  l.loan_id,
  l.principal_amount,
  COALESCE(SUM(lp.amount), 0) AS total_payments,
  COALESCE(SUM(lp.amount), 0) - l.principal_amount AS diff
FROM "Loan" l
LEFT JOIN "LoanPayment" lp
  ON lp.loan_id = l.loan_id
GROUP BY l.loan_id, l.principal_amount
ORDER BY ABS(COALESCE(SUM(lp.amount), 0) - l.principal_amount) DESC
LIMIT 20;
```

Only loans that have at least one payment:

```sql
SELECT
  l.loan_id,
  l.principal_amount,
  SUM(lp.amount) AS total_payments,
  l.principal_amount - SUM(lp.amount) AS remaining_principal
FROM "Loan" l
JOIN "LoanPayment" lp ON lp.loan_id = l.loan_id
GROUP BY l.loan_id, l.principal_amount
ORDER BY remaining_principal DESC
LIMIT 20;
```

These queries help verify that loans and their payments are linked correctly and that payment amounts are in a plausible range relative to principal.

## 4. Transaction Status and Type Distribution

Check how transactions are distributed across statuses and types:

```sql
SELECT status, txn_type, COUNT(*) AS cnt
FROM "Transaction"
GROUP BY status, txn_type
ORDER BY cnt DESC;
```

This is useful to confirm that allowed values (e.g., status codes) are present and reasonably balanced.

## 5. Quick Samples from Each Table

Inspect a few rows from each table:

```sql
SELECT * FROM "Customer"    LIMIT 5;
SELECT * FROM "Account"     LIMIT 5;
SELECT * FROM "Transaction" LIMIT 5;
SELECT * FROM "Loan"        LIMIT 5;
SELECT * FROM "LoanPayment" LIMIT 5;
```

Use these to spot-check that field formats, date ranges, and relationships look correct.

---

You can customize these queries with additional `WHERE` filters (for dates, amounts, countries, etc.) depending on the specific behaviors you want to test in your synthetic data.
