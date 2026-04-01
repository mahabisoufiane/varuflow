-- ============================================================
-- Varuflow — Row Level Security Policies
-- Apply AFTER the initial schema migration.
-- ============================================================

-- ---- Helper function ----
-- Returns the org_id for the currently authenticated user.
-- Used in all RLS policies so the logic lives in one place.

CREATE OR REPLACE FUNCTION get_user_org_id()
RETURNS UUID
LANGUAGE sql
STABLE
SECURITY DEFINER
AS $$
    SELECT org_id
    FROM organization_members
    WHERE user_id = auth.uid()
    LIMIT 1;
$$;

-- ---- Enable RLS on all tables ----

ALTER TABLE organizations          ENABLE ROW LEVEL SECURITY;
ALTER TABLE organization_members   ENABLE ROW LEVEL SECURITY;
ALTER TABLE products               ENABLE ROW LEVEL SECURITY;
ALTER TABLE suppliers              ENABLE ROW LEVEL SECURITY;
ALTER TABLE warehouses             ENABLE ROW LEVEL SECURITY;
ALTER TABLE stock_levels           ENABLE ROW LEVEL SECURITY;
ALTER TABLE stock_movements        ENABLE ROW LEVEL SECURITY;
ALTER TABLE purchase_orders        ENABLE ROW LEVEL SECURITY;
ALTER TABLE purchase_order_items   ENABLE ROW LEVEL SECURITY;
ALTER TABLE customers              ENABLE ROW LEVEL SECURITY;
ALTER TABLE invoices               ENABLE ROW LEVEL SECURITY;
ALTER TABLE invoice_line_items     ENABLE ROW LEVEL SECURITY;
ALTER TABLE payments               ENABLE ROW LEVEL SECURITY;
ALTER TABLE recurring_invoices     ENABLE ROW LEVEL SECURITY;
-- waitlist is public (no RLS needed for inserts; reads restricted)
ALTER TABLE waitlist               ENABLE ROW LEVEL SECURITY;

-- ============================================================
-- organizations
-- ============================================================

CREATE POLICY "Users can view their own organization"
    ON organizations FOR SELECT
    USING (id = get_user_org_id());

CREATE POLICY "Owners can update their organization"
    ON organizations FOR UPDATE
    USING (
        id = get_user_org_id()
        AND EXISTS (
            SELECT 1 FROM organization_members
            WHERE user_id = auth.uid()
              AND org_id = organizations.id
              AND role = 'OWNER'
        )
    );

-- ============================================================
-- organization_members
-- ============================================================

CREATE POLICY "Members can view their org's members"
    ON organization_members FOR SELECT
    USING (org_id = get_user_org_id());

CREATE POLICY "Owners/admins can insert members"
    ON organization_members FOR INSERT
    WITH CHECK (
        org_id = get_user_org_id()
        AND EXISTS (
            SELECT 1 FROM organization_members AS om
            WHERE om.user_id = auth.uid()
              AND om.org_id = organization_members.org_id
              AND om.role IN ('OWNER', 'ADMIN')
        )
    );

CREATE POLICY "Owners/admins can delete members"
    ON organization_members FOR DELETE
    USING (
        org_id = get_user_org_id()
        AND EXISTS (
            SELECT 1 FROM organization_members AS om
            WHERE om.user_id = auth.uid()
              AND om.org_id = organization_members.org_id
              AND om.role IN ('OWNER', 'ADMIN')
        )
    );

-- ============================================================
-- Macro: all business tables with a direct org_id column
-- Pattern: SELECT/INSERT/UPDATE/DELETE all check org_id = get_user_org_id()
-- ============================================================

-- products
CREATE POLICY "org_select" ON products FOR SELECT USING (org_id = get_user_org_id());
CREATE POLICY "org_insert" ON products FOR INSERT WITH CHECK (org_id = get_user_org_id());
CREATE POLICY "org_update" ON products FOR UPDATE USING (org_id = get_user_org_id());
CREATE POLICY "org_delete" ON products FOR DELETE USING (org_id = get_user_org_id());

-- suppliers
CREATE POLICY "org_select" ON suppliers FOR SELECT USING (org_id = get_user_org_id());
CREATE POLICY "org_insert" ON suppliers FOR INSERT WITH CHECK (org_id = get_user_org_id());
CREATE POLICY "org_update" ON suppliers FOR UPDATE USING (org_id = get_user_org_id());
CREATE POLICY "org_delete" ON suppliers FOR DELETE USING (org_id = get_user_org_id());

-- warehouses
CREATE POLICY "org_select" ON warehouses FOR SELECT USING (org_id = get_user_org_id());
CREATE POLICY "org_insert" ON warehouses FOR INSERT WITH CHECK (org_id = get_user_org_id());
CREATE POLICY "org_update" ON warehouses FOR UPDATE USING (org_id = get_user_org_id());
CREATE POLICY "org_delete" ON warehouses FOR DELETE USING (org_id = get_user_org_id());

-- stock_levels
CREATE POLICY "org_select" ON stock_levels FOR SELECT USING (org_id = get_user_org_id());
CREATE POLICY "org_insert" ON stock_levels FOR INSERT WITH CHECK (org_id = get_user_org_id());
CREATE POLICY "org_update" ON stock_levels FOR UPDATE USING (org_id = get_user_org_id());
CREATE POLICY "org_delete" ON stock_levels FOR DELETE USING (org_id = get_user_org_id());

-- stock_movements
CREATE POLICY "org_select" ON stock_movements FOR SELECT USING (org_id = get_user_org_id());
CREATE POLICY "org_insert" ON stock_movements FOR INSERT WITH CHECK (org_id = get_user_org_id());
CREATE POLICY "org_delete" ON stock_movements FOR DELETE USING (org_id = get_user_org_id());

-- purchase_orders
CREATE POLICY "org_select" ON purchase_orders FOR SELECT USING (org_id = get_user_org_id());
CREATE POLICY "org_insert" ON purchase_orders FOR INSERT WITH CHECK (org_id = get_user_org_id());
CREATE POLICY "org_update" ON purchase_orders FOR UPDATE USING (org_id = get_user_org_id());
CREATE POLICY "org_delete" ON purchase_orders FOR DELETE USING (org_id = get_user_org_id());

-- purchase_order_items — no direct org_id; scope via parent purchase_order
CREATE POLICY "org_select" ON purchase_order_items FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM purchase_orders po
            WHERE po.id = purchase_order_items.purchase_order_id
              AND po.org_id = get_user_org_id()
        )
    );
CREATE POLICY "org_insert" ON purchase_order_items FOR INSERT
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM purchase_orders po
            WHERE po.id = purchase_order_items.purchase_order_id
              AND po.org_id = get_user_org_id()
        )
    );
CREATE POLICY "org_update" ON purchase_order_items FOR UPDATE
    USING (
        EXISTS (
            SELECT 1 FROM purchase_orders po
            WHERE po.id = purchase_order_items.purchase_order_id
              AND po.org_id = get_user_org_id()
        )
    );
CREATE POLICY "org_delete" ON purchase_order_items FOR DELETE
    USING (
        EXISTS (
            SELECT 1 FROM purchase_orders po
            WHERE po.id = purchase_order_items.purchase_order_id
              AND po.org_id = get_user_org_id()
        )
    );

-- customers
CREATE POLICY "org_select" ON customers FOR SELECT USING (org_id = get_user_org_id());
CREATE POLICY "org_insert" ON customers FOR INSERT WITH CHECK (org_id = get_user_org_id());
CREATE POLICY "org_update" ON customers FOR UPDATE USING (org_id = get_user_org_id());
CREATE POLICY "org_delete" ON customers FOR DELETE USING (org_id = get_user_org_id());

-- invoices
CREATE POLICY "org_select" ON invoices FOR SELECT USING (org_id = get_user_org_id());
CREATE POLICY "org_insert" ON invoices FOR INSERT WITH CHECK (org_id = get_user_org_id());
CREATE POLICY "org_update" ON invoices FOR UPDATE USING (org_id = get_user_org_id());
CREATE POLICY "org_delete" ON invoices FOR DELETE USING (org_id = get_user_org_id());

-- invoice_line_items — scope via parent invoice
CREATE POLICY "org_select" ON invoice_line_items FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM invoices i
            WHERE i.id = invoice_line_items.invoice_id
              AND i.org_id = get_user_org_id()
        )
    );
CREATE POLICY "org_insert" ON invoice_line_items FOR INSERT
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM invoices i
            WHERE i.id = invoice_line_items.invoice_id
              AND i.org_id = get_user_org_id()
        )
    );
CREATE POLICY "org_update" ON invoice_line_items FOR UPDATE
    USING (
        EXISTS (
            SELECT 1 FROM invoices i
            WHERE i.id = invoice_line_items.invoice_id
              AND i.org_id = get_user_org_id()
        )
    );
CREATE POLICY "org_delete" ON invoice_line_items FOR DELETE
    USING (
        EXISTS (
            SELECT 1 FROM invoices i
            WHERE i.id = invoice_line_items.invoice_id
              AND i.org_id = get_user_org_id()
        )
    );

-- payments
CREATE POLICY "org_select" ON payments FOR SELECT USING (org_id = get_user_org_id());
CREATE POLICY "org_insert" ON payments FOR INSERT WITH CHECK (org_id = get_user_org_id());
CREATE POLICY "org_delete" ON payments FOR DELETE USING (org_id = get_user_org_id());

-- recurring_invoices
CREATE POLICY "org_select" ON recurring_invoices FOR SELECT USING (org_id = get_user_org_id());
CREATE POLICY "org_insert" ON recurring_invoices FOR INSERT WITH CHECK (org_id = get_user_org_id());
CREATE POLICY "org_update" ON recurring_invoices FOR UPDATE USING (org_id = get_user_org_id());
CREATE POLICY "org_delete" ON recurring_invoices FOR DELETE USING (org_id = get_user_org_id());

-- ============================================================
-- waitlist — public insert, no public reads
-- ============================================================

CREATE POLICY "Anyone can join waitlist"
    ON waitlist FOR INSERT
    WITH CHECK (true);

-- No SELECT policy = only service role can read waitlist entries
