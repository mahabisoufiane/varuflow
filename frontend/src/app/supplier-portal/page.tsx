import { redirect } from "next/navigation";

// Root of the supplier-portal route — supplier always arrives via
// /supplier-portal/verify?token=..., so a bare /supplier-portal hit
// means the session is absent. Bounce to a friendly message.

export default function SupplierPortalIndex() {
  // The supplier-portal is purely link-driven; no login form. If a
  // curious user lands here, point them at the landing copy.
  redirect("/supplier-portal/welcome");
}
