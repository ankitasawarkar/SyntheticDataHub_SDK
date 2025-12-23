-- Optional: dedicated schema
CREATE SCHEMA IF NOT EXISTS synthetic_demo;
SET search_path TO synthetic_demo;

-- =====================================================
-- 1. Reference and enum-like tables
-- =====================================================

CREATE TABLE country (
    country_code        CHAR(2) PRIMARY KEY,
    country_name        VARCHAR(100) NOT NULL,
    iso3_code           CHAR(3) UNIQUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE state_province (
    state_id            SERIAL PRIMARY KEY,
    country_code        CHAR(2) NOT NULL REFERENCES country(country_code),
    state_code          VARCHAR(10) NOT NULL,
    state_name          VARCHAR(100) NOT NULL,
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE (country_code, state_code)
);

-- Emulate enum via lookup table
CREATE TABLE contact_type (
    contact_type_code   VARCHAR(20) PRIMARY KEY,
    description         VARCHAR(200) NOT NULL
);

-- =====================================================
-- 2. Party model: person / organization (inheritance via type)
-- =====================================================

CREATE TABLE party (
    party_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    party_type          VARCHAR(20) NOT NULL CHECK (party_type IN ('PERSON', 'ORGANIZATION')),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ,
    is_active           BOOLEAN NOT NULL DEFAULT TRUE
);

-- Person details (1:1 with party)
CREATE TABLE person (
    party_id            UUID PRIMARY KEY REFERENCES party(party_id) ON DELETE CASCADE,
    first_name          VARCHAR(100) NOT NULL,
    middle_name         VARCHAR(100),
    last_name           VARCHAR(100) NOT NULL,
    date_of_birth       DATE,
    gender              VARCHAR(20) CHECK (gender IN ('MALE', 'FEMALE', 'NON_BINARY', 'OTHER')),
    -- SSN with strict US format: 123-45-6789
    ssn                 CHAR(11),
    CONSTRAINT chk_person_ssn_format
        CHECK (ssn IS NULL OR ssn ~ '^[0-9]{3}-[0-9]{2}-[0-9]{4}$')
);

-- Organization details (1:1 with party)
CREATE TABLE organization (
    party_id            UUID PRIMARY KEY REFERENCES party(party_id) ON DELETE CASCADE,
    legal_name          VARCHAR(255) NOT NULL,
    trade_name          VARCHAR(255),
    tax_id              VARCHAR(20),
    incorporation_date  DATE
);

-- =====================================================
-- 3. Contact info tables with formatted fields
-- =====================================================

CREATE TABLE address (
    address_id          BIGSERIAL PRIMARY KEY,
    party_id            UUID NOT NULL REFERENCES party(party_id) ON DELETE CASCADE,
    line1               VARCHAR(255) NOT NULL,
    line2               VARCHAR(255),
    city                VARCHAR(100) NOT NULL,
    state_id            INT REFERENCES state_province(state_id),
    postal_code         VARCHAR(20) NOT NULL,
    country_code        CHAR(2) NOT NULL REFERENCES country(country_code),
    is_primary          BOOLEAN NOT NULL DEFAULT FALSE,
    valid_from          DATE NOT NULL DEFAULT CURRENT_DATE,
    valid_to            DATE,
    CONSTRAINT chk_address_validity
        CHECK (valid_to IS NULL OR valid_to >= valid_from)
);

CREATE TABLE email_address (
    email_id            BIGSERIAL PRIMARY KEY,
    party_id            UUID NOT NULL REFERENCES party(party_id) ON DELETE CASCADE,
    email               VARCHAR(320) NOT NULL,
    is_primary          BOOLEAN NOT NULL DEFAULT FALSE,
    contact_type_code   VARCHAR(20) REFERENCES contact_type(contact_type_code),
    -- Basic email format validation
    CONSTRAINT chk_email_format
        CHECK (email ~ '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+.[A-Za-z]{2,}$')
);

CREATE TABLE phone_number (
    phone_id            BIGSERIAL PRIMARY KEY,
    party_id            UUID NOT NULL REFERENCES party(party_id) ON DELETE CASCADE,
    -- Store in E.164-like format: +1-555-123-4567 or +15551234567
    phone_number        VARCHAR(25) NOT NULL,
    is_primary          BOOLEAN NOT NULL DEFAULT FALSE,
    contact_type_code   VARCHAR(20) REFERENCES contact_type(contact_type_code),
    CONSTRAINT chk_phone_format
        CHECK (phone_number ~ '^+?[0-9-() ]{7,25}$')
);

-- Only one primary email and phone per party
CREATE UNIQUE INDEX ux_email_primary_per_party
    ON email_address(party_id)
    WHERE is_primary = TRUE;

CREATE UNIQUE INDEX ux_phone_primary_per_party
    ON phone_number(party_id)
    WHERE is_primary = TRUE;

-- =====================================================
-- 4. User accounts and credentials
-- =====================================================

CREATE TABLE user_account (
    user_id             BIGSERIAL PRIMARY KEY,
    party_id            UUID NOT NULL UNIQUE REFERENCES party(party_id),
    username            VARCHAR(50) NOT NULL UNIQUE,
    password_hash       BYTEA NOT NULL,
    password_salt       BYTEA NOT NULL,
    email_for_login     VARCHAR(320) NOT NULL,
    is_locked           BOOLEAN NOT NULL DEFAULT FALSE,
    last_login_at       TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- Derived consistency: email_for_login must be valid format
    CONSTRAINT chk_user_email_format
        CHECK (email_for_login ~ '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+.[A-Za-z]{2,}$')
);

-- =====================================================
-- 5. HR-style domain: departments, employees, projects
-- =====================================================

CREATE TABLE department (
    department_id       SMALLINT PRIMARY KEY,
    department_code     VARCHAR(10) NOT NULL UNIQUE,
    department_name     VARCHAR(100) NOT NULL,
    manager_party_id    UUID REFERENCES party(party_id), -- Manager is a person/party
    budget              NUMERIC(15,2) NOT NULL DEFAULT 0,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE employee (
    employee_id         BIGSERIAL PRIMARY KEY,
    party_id            UUID NOT NULL UNIQUE REFERENCES party(party_id) ON DELETE CASCADE,
    department_id       SMALLINT NOT NULL REFERENCES department(department_id),
    hire_date           DATE NOT NULL,
    termination_date    DATE,
    employment_type     VARCHAR(20) NOT NULL CHECK (employment_type IN ('FULL_TIME', 'PART_TIME', 'CONTRACTOR')),
    annual_salary       NUMERIC(15,2),
    hourly_rate         NUMERIC(10,2),
    -- Either salary or hourly_rate must be non-null depending on type
    CONSTRAINT chk_compensation
        CHECK (
            (employment_type IN ('FULL_TIME', 'PART_TIME') AND annual_salary IS NOT NULL)
            OR (employment_type = 'CONTRACTOR' AND hourly_rate IS NOT NULL)
        ),
    -- Validity constraint
    CONSTRAINT chk_employment_dates
        CHECK (termination_date IS NULL OR termination_date >= hire_date)
);

CREATE TABLE project (
    project_id          BIGSERIAL PRIMARY KEY,
    project_code        VARCHAR(20) NOT NULL UNIQUE,
    project_name        VARCHAR(200) NOT NULL,
    owning_department   SMALLINT NOT NULL REFERENCES department(department_id),
    start_date          DATE NOT NULL,
    end_date            DATE,
    budget              NUMERIC(15,2),
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    metadata            JSONB, -- semi-structured
    CONSTRAINT chk_project_dates
        CHECK (end_date IS NULL OR end_date >= start_date)
);

-- Many-to-many: employee <-> project with roles and composite PK
CREATE TABLE employee_project (
    employee_id         BIGINT NOT NULL REFERENCES employee(employee_id) ON DELETE CASCADE,
    project_id          BIGINT NOT NULL REFERENCES project(project_id) ON DELETE CASCADE,
    role_name           VARCHAR(100) NOT NULL,
    allocation_percent  NUMERIC(5,2) NOT NULL CHECK (allocation_percent BETWEEN 0 AND 100),
    assigned_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (employee_id, project_id)
);

-- =====================================================
-- 6. Orders domain: fact tables with multiple relationships
-- =====================================================

CREATE TABLE product (
    product_id          BIGSERIAL PRIMARY KEY,
    sku                 VARCHAR(50) NOT NULL UNIQUE,
    product_name        VARCHAR(200) NOT NULL,
    description         TEXT,
    base_price          NUMERIC(12,2) NOT NULL CHECK (base_price >= 0),
    tags                TEXT[],
    attributes          JSONB, -- arbitrary attributes
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    discontinued_at     TIMESTAMPTZ
);

CREATE TABLE customer (
    customer_id         BIGSERIAL PRIMARY KEY,
    party_id            UUID NOT NULL UNIQUE REFERENCES party(party_id),
    customer_since      DATE NOT NULL DEFAULT CURRENT_DATE,
    credit_limit        NUMERIC(15,2) DEFAULT 0,
    risk_score          REAL CHECK (risk_score BETWEEN 0 AND 1),
    loyalty_tier        VARCHAR(20) CHECK (loyalty_tier IN ('BRONZE', 'SILVER', 'GOLD', 'PLATINUM'))
);

CREATE TABLE order_header (
    order_id            BIGSERIAL PRIMARY KEY,
    customer_id         BIGINT NOT NULL REFERENCES customer(customer_id),
    billing_address_id  BIGINT NOT NULL REFERENCES address(address_id),
    shipping_address_id BIGINT NOT NULL REFERENCES address(address_id),
    order_status        VARCHAR(20) NOT NULL CHECK (order_status IN ('PENDING', 'PAID', 'SHIPPED', 'CANCELLED', 'RETURNED')),
    order_total         NUMERIC(15,2) NOT NULL DEFAULT 0,
    currency_code       CHAR(3) NOT NULL,
    placed_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    shipped_at          TIMESTAMPTZ,
    cancelled_at        TIMESTAMPTZ,
    -- Logical constraints (non-enforced but testable)
    CONSTRAINT chk_order_dates
        CHECK (
            (shipped_at IS NULL OR shipped_at >= placed_at)
            AND (cancelled_at IS NULL OR cancelled_at >= placed_at)
        )
);

CREATE TABLE order_line (
    order_id            BIGINT NOT NULL REFERENCES order_header(order_id) ON DELETE CASCADE,
    line_number         INTEGER NOT NULL,
    product_id          BIGINT NOT NULL REFERENCES product(product_id),
    quantity            INTEGER NOT NULL CHECK (quantity > 0),
    unit_price          NUMERIC(12,2) NOT NULL CHECK (unit_price >= 0),
    discount_amount     NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (discount_amount >= 0),
    line_total          NUMERIC(15,2) NOT NULL,
    PRIMARY KEY (order_id, line_number)
);

-- Payment with composite constraints and enums
CREATE TABLE payment (
    payment_id          BIGSERIAL PRIMARY KEY,
    order_id            BIGINT NOT NULL REFERENCES order_header(order_id),
    payment_method      VARCHAR(20) NOT NULL CHECK (payment_method IN ('CARD', 'BANK_TRANSFER', 'CASH', 'VOUCHER')),
    amount              NUMERIC(15,2) NOT NULL CHECK (amount > 0),
    paid_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    transaction_ref     VARCHAR(100),
    is_refund           BOOLEAN NOT NULL DEFAULT FALSE
);

-- =====================================================
-- 7. Audit / logging with flexible types
-- =====================================================

CREATE TABLE audit_log (
    audit_id            BIGSERIAL PRIMARY KEY,
    entity_type         VARCHAR(50) NOT NULL,
    entity_id           VARCHAR(100) NOT NULL,
    operation           VARCHAR(10) NOT NULL CHECK (operation IN ('INSERT', 'UPDATE', 'DELETE')),
    performed_by        BIGINT REFERENCES user_account(user_id),
    performed_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- Before & after as JSON
    data_before         JSONB,
    data_after          JSONB
);

-- Optional: example of generated column (Postgres 12+)
CREATE TABLE document_store (
    document_id         BIGSERIAL PRIMARY KEY,
    owner_party_id      UUID NOT NULL REFERENCES party(party_id),
    filename            VARCHAR(255) NOT NULL,
    mime_type           VARCHAR(100) NOT NULL,
    content             BYTEA NOT NULL,
    size_bytes          BIGINT GENERATED ALWAYS AS (octet_length(content)) STORED,
    uploaded_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
