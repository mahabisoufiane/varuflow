-- ============================================================
-- Varuflow — RLS Policies for POS tables
-- These tables were added after the initial RLS migration and
-- were missing row-level security. All have a direct org_id column.
-- ============================================================

-- ---- pos_sessions ----
ALTER TABLE pos_sessions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "org_select" ON pos_sessions FOR SELECT USING (org_id = get_user_org_id());
CREATE POLICY "org_insert" ON pos_sessions FOR INSERT WITH CHECK (org_id = get_user_org_id());
CREATE POLICY "org_update" ON pos_sessions FOR UPDATE USING (org_id = get_user_org_id());
CREATE POLICY "org_delete" ON pos_sessions FOR DELETE USING (org_id = get_user_org_id());

-- ---- pos_sales ----
ALTER TABLE pos_sales ENABLE ROW LEVEL SECURITY;

CREATE POLICY "org_select" ON pos_sales FOR SELECT USING (org_id = get_user_org_id());
CREATE POLICY "org_insert" ON pos_sales FOR INSERT WITH CHECK (org_id = get_user_org_id());
CREATE POLICY "org_update" ON pos_sales FOR UPDATE USING (org_id = get_user_org_id());
CREATE POLICY "org_delete" ON pos_sales FOR DELETE USING (org_id = get_user_org_id());

-- ---- pos_sale_items — no direct org_id; scope via parent pos_sales ----
ALTER TABLE pos_sale_items ENABLE ROW LEVEL SECURITY;

CREATE POLICY "org_select" ON pos_sale_items FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM pos_sales ps
            WHERE ps.id = pos_sale_items.sale_id
              AND ps.org_id = get_user_org_id()
        )
    );
CREATE POLICY "org_insert" ON pos_sale_items FOR INSERT
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM pos_sales ps
            WHERE ps.id = pos_sale_items.sale_id
              AND ps.org_id = get_user_org_id()
        )
    );
CREATE POLICY "org_update" ON pos_sale_items FOR UPDATE
    USING (
        EXISTS (
            SELECT 1 FROM pos_sales ps
            WHERE ps.id = pos_sale_items.sale_id
              AND ps.org_id = get_user_org_id()
        )
    );
CREATE POLICY "org_delete" ON pos_sale_items FOR DELETE
    USING (
        EXISTS (
            SELECT 1 FROM pos_sales ps
            WHERE ps.id = pos_sale_items.sale_id
              AND ps.org_id = get_user_org_id()
        )
    );
