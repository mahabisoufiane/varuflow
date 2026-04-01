-- ============================================================
-- Varuflow — Initial Schema
-- Apply this in the Supabase SQL editor or via: supabase db push
-- ============================================================

-- ---- Enums ----

CREATE TYPE org_plan AS ENUM ('FREE', 'PRO');
CREATE TYPE org_role AS ENUM ('OWNER', 'ADMIN', 'MEMBER');
CREATE TYPE stock_movement_type AS ENUM ('IN', 'OUT', 'ADJUSTMENT');
CREATE TYPE purchase_order_status AS ENUM ('DRAFT', 'SENT', 'RECEIVED');
CREATE TYPE invoice_status AS ENUM ('DRAFT', 'SENT', 'PAID', 'OVERDUE');
CREATE TYPE payment_method AS ENUM ('BANK_TRANSFER', 'CARD', 'CASH', 'OTHER');
CREATE TYPE recurring_frequency AS ENUM ('WEEKLY', 'MONTHLY');

-- ---- Organizations ----

CREATE TABLE organizations (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL,
    org_number  TEXT,               -- Swedish org number (XXXXXX-XXXX)
    vat_number  TEXT,
    address     TEXT,
    plan        org_plan NOT NULL DEFAULT 'FREE',
    is_active   BOOLEAN NOT NULL DEFAULT true,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE organization_members (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id      UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id     UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    role        org_role NOT NULL DEFAULT 'MEMBER',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (org_id, user_id)
);

-- ---- Inventory ----

CREATE TABLE suppliers (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id      UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    email       TEXT,
    phone       TEXT,
    address     TEXT,
    country     TEXT NOT NULL DEFAULT 'Sweden',
    is_active   BOOLEAN NOT NULL DEFAULT true,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_suppliers_org_id ON suppliers(org_id);

CREATE TABLE products (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    sku             TEXT NOT NULL,
    category        TEXT,
    unit            TEXT NOT NULL DEFAULT 'st',
    purchase_price  NUMERIC(12,2) NOT NULL,
    sell_price      NUMERIC(12,2) NOT NULL,
    tax_rate        NUMERIC(5,2) NOT NULL DEFAULT 25.00,  -- 25%, 12%, 6%
    description     TEXT,
    is_active       BOOLEAN NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (org_id, sku)
);

CREATE INDEX idx_products_org_id ON products(org_id);

CREATE TABLE warehouses (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id      UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    location    TEXT,
    is_active   BOOLEAN NOT NULL DEFAULT true,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_warehouses_org_id ON warehouses(org_id);

CREATE TABLE stock_levels (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    product_id      UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    warehouse_id    UUID NOT NULL REFERENCES warehouses(id) ON DELETE CASCADE,
    quantity        INTEGER NOT NULL DEFAULT 0,
    min_threshold   INTEGER NOT NULL DEFAULT 0,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (product_id, warehouse_id)
);

CREATE INDEX idx_stock_levels_org_id ON stock_levels(org_id);

CREATE TABLE stock_movements (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    product_id      UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    warehouse_id    UUID NOT NULL REFERENCES warehouses(id) ON DELETE CASCADE,
    type            stock_movement_type NOT NULL,
    quantity        INTEGER NOT NULL,
    reference       TEXT,
    note            TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_stock_movements_org_id ON stock_movements(org_id);
CREATE INDEX idx_stock_movements_product_id ON stock_movements(product_id);

CREATE TABLE purchase_orders (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id      UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    supplier_id UUID NOT NULL REFERENCES suppliers(id) ON DELETE RESTRICT,
    status      purchase_order_status NOT NULL DEFAULT 'DRAFT',
    total       NUMERIC(14,2) NOT NULL DEFAULT 0.00,
    notes       TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_purchase_orders_org_id ON purchase_orders(org_id);

CREATE TABLE purchase_order_items (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    purchase_order_id   UUID NOT NULL REFERENCES purchase_orders(id) ON DELETE CASCADE,
    product_id          UUID NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
    quantity            INTEGER NOT NULL,
    unit_price          NUMERIC(12,2) NOT NULL,
    line_total          NUMERIC(14,2) NOT NULL
);

-- ---- Invoicing ----

CREATE TABLE customers (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id              UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    company_name        TEXT NOT NULL,
    org_number          TEXT,   -- Swedish org number
    vat_number          TEXT,
    email               TEXT,
    phone               TEXT,
    address             TEXT,
    payment_terms_days  INTEGER NOT NULL DEFAULT 30,
    is_active           BOOLEAN NOT NULL DEFAULT true,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_customers_org_id ON customers(org_id);

CREATE TABLE invoices (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    customer_id     UUID NOT NULL REFERENCES customers(id) ON DELETE RESTRICT,
    invoice_number  TEXT NOT NULL,
    issue_date      DATE NOT NULL,
    due_date        DATE NOT NULL,
    status          invoice_status NOT NULL DEFAULT 'DRAFT',
    subtotal        NUMERIC(14,2) NOT NULL DEFAULT 0.00,
    vat_amount      NUMERIC(14,2) NOT NULL DEFAULT 0.00,
    total_sek       NUMERIC(14,2) NOT NULL DEFAULT 0.00,
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (org_id, invoice_number)
);

CREATE INDEX idx_invoices_org_id ON invoices(org_id);
CREATE INDEX idx_invoices_status ON invoices(status);
CREATE INDEX idx_invoices_due_date ON invoices(due_date);

CREATE TABLE invoice_line_items (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_id  UUID NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    product_id  UUID REFERENCES products(id) ON DELETE SET NULL,
    description TEXT NOT NULL,
    quantity    NUMERIC(10,3) NOT NULL,
    unit_price  NUMERIC(12,2) NOT NULL,
    tax_rate    NUMERIC(5,2) NOT NULL DEFAULT 25.00,
    line_total  NUMERIC(14,2) NOT NULL
);

CREATE TABLE payments (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    invoice_id      UUID NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    amount          NUMERIC(14,2) NOT NULL,
    payment_date    DATE NOT NULL,
    method          payment_method NOT NULL DEFAULT 'BANK_TRANSFER',
    reference       TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_payments_org_id ON payments(org_id);

CREATE TABLE recurring_invoices (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id              UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    customer_id         UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    frequency           recurring_frequency NOT NULL,
    next_run_date       DATE NOT NULL,
    template_invoice_id UUID REFERENCES invoices(id) ON DELETE SET NULL,
    is_active           BOOLEAN NOT NULL DEFAULT true,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_recurring_invoices_org_id ON recurring_invoices(org_id);

-- ---- Landing page waitlist ----

CREATE TABLE waitlist (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           TEXT UNIQUE NOT NULL,
    company_name    TEXT,
    welcome_sent    BOOLEAN NOT NULL DEFAULT false,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
