from app.database import Base  # noqa: F401

# Import all models so Alembic can detect them
from app.models.organization import Organization, OrganizationMember  # noqa: F401
from app.models.inventory import (  # noqa: F401
    Product,
    Supplier,
    Warehouse,
    StockLevel,
    StockMovement,
    PurchaseOrder,
    PurchaseOrderItem,
)
from app.models.invoicing import (  # noqa: F401
    Customer,
    Invoice,
    InvoiceLineItem,
    Payment,
    RecurringInvoice,
)
from app.models.pos import PosSession, PosSale, PosSaleItem  # noqa: F401
from app.models.waitlist import Waitlist  # noqa: F401
