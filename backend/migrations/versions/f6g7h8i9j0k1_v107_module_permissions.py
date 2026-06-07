"""v107 — module permission system (tables + member column)

Revision ID: f6g7h8i9j0k1
Revises: e5f6g7h8i9j0
Create Date: 2026-06-06
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "f6g7h8i9j0k1"
down_revision = "e5f6g7h8i9j0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "modules",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("key", sa.String(50), unique=True, nullable=False),
        sa.Column("label", sa.String(100), nullable=False),
        sa.Column("icon", sa.String(50), nullable=True),
        sa.Column("routes", JSONB, nullable=False),
        sa.Column("api_prefixes", JSONB, nullable=False),
        sa.Column("min_plan", sa.String(20), server_default="FREE", nullable=False),
        sa.Column("sort_order", sa.Integer, server_default="0", nullable=False),
    )

    op.create_table(
        "member_modules",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "member_id",
            UUID(as_uuid=True),
            sa.ForeignKey("organization_members.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "module_key",
            sa.String(50),
            sa.ForeignKey("modules.key", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("granted_by", UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("member_id", "module_key", name="uq_member_modules_member_key"),
    )
    op.create_index("ix_member_modules_member_id", "member_modules", ["member_id"])

    op.add_column(
        "organization_members",
        sa.Column(
            "module_access_mode",
            sa.String(20),
            server_default="ALL",
            nullable=False,
        ),
    )

    # Seed the module registry
    op.execute("""
        INSERT INTO modules (id, key, label, icon, routes, api_prefixes, min_plan, sort_order) VALUES
        (gen_random_uuid(), 'dashboard', 'Dashboard', 'LayoutDashboard', '["/", "/dashboard"]'::jsonb, '["/api/dashboard"]'::jsonb, 'FREE', 0),
        (gen_random_uuid(), 'pos', 'Point of Sale', 'ShoppingCart', '["/pos"]'::jsonb, '["/api/pos"]'::jsonb, 'FREE', 1),
        (gen_random_uuid(), 'invoicing', 'Invoicing', 'FileText', '["/invoices", "/recurring", "/quotes"]'::jsonb, '["/api/invoicing", "/api/recurring"]'::jsonb, 'FREE', 2),
        (gen_random_uuid(), 'inventory', 'Inventory', 'Package', '["/inventory", "/manufacturing", "/kitting"]'::jsonb, '["/api/inventory"]'::jsonb, 'FREE', 3),
        (gen_random_uuid(), 'crm', 'CRM', 'Users', '["/crm", "/customers"]'::jsonb, '["/api/crm", "/api/customers"]'::jsonb, 'PRO', 4),
        (gen_random_uuid(), 'analytics', 'Analytics', 'BarChart3', '["/analytics", "/reports"]'::jsonb, '["/api/analytics"]'::jsonb, 'PRO', 5),
        (gen_random_uuid(), 'hr', 'HR & People', 'UserCog', '["/hr", "/scheduling", "/projects"]'::jsonb, '["/api/hr", "/api/scheduling"]'::jsonb, 'PRO', 6),
        (gen_random_uuid(), 'finance', 'Finance', 'Wallet', '["/accounting", "/ceo", "/budget", "/expenses"]'::jsonb, '["/api/accounting", "/api/ceo", "/api/budget", "/api/expenses"]'::jsonb, 'PRO', 7),
        (gen_random_uuid(), 'ai', 'AI Assistant', 'Sparkles', '["/ai", "/ai-tools"]'::jsonb, '["/api/ai", "/api/integrations/chat"]'::jsonb, 'PRO', 8),
        (gen_random_uuid(), 'settings', 'Settings', 'Settings', '["/settings", "/integrations"]'::jsonb, '["/api/settings", "/api/integrations", "/api/team", "/api/billing"]'::jsonb, 'FREE', 9)
    """)


def downgrade() -> None:
    op.drop_column("organization_members", "module_access_mode")
    op.drop_table("member_modules")
    op.drop_table("modules")
