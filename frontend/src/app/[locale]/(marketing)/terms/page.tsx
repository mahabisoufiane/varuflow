import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Terms of service — Varuflow",
};

export default function TermsPage() {
  const updated = "2026-04-21";
  return (
    <main className="mx-auto max-w-3xl px-6 py-12 text-sm leading-relaxed">
      <h1 className="mb-2 text-3xl font-semibold">Terms of service</h1>
      <p className="mb-8 text-neutral-500">Last updated: {updated}</p>

      <p className="mb-4">
        These terms govern your use of the Varuflow service operated by
        <strong> Varuflow AB</strong>. By creating an account you agree to be
        bound by them. This is a plain-language draft — please consult the
        signed service agreement for your account if one exists; it takes
        precedence.
      </p>

      <h2 className="mt-8 mb-3 text-xl font-medium">1. The service</h2>
      <p>
        Varuflow provides inventory, invoicing and POS tooling for small and
        mid-sized wholesalers. Access is offered on a subscription basis in
        FREE and PRO tiers. Features and limits are described on the pricing
        page and may change with reasonable notice.
      </p>

      <h2 className="mt-8 mb-3 text-xl font-medium">2. Your account</h2>
      <ul className="list-disc space-y-1 pl-6">
        <li>You are responsible for the accuracy of the data you enter.</li>
        <li>You are responsible for keeping your credentials confidential.</li>
        <li>You must have authority to act on behalf of the organization you register.</li>
      </ul>

      <h2 className="mt-8 mb-3 text-xl font-medium">3. Acceptable use</h2>
      <p>
        You may not use the service to send spam, host malware, infringe
        third-party rights, or attempt to probe / bypass our security controls.
        We may suspend or terminate accounts that violate these rules.
      </p>

      <h2 className="mt-8 mb-3 text-xl font-medium">4. Billing</h2>
      <p>
        PRO subscriptions renew automatically until cancelled. You can cancel
        at any time from Settings → Billing; access continues until the end of
        the paid period. Refunds are handled on a case-by-case basis in line
        with Swedish consumer law where applicable.
      </p>

      <h2 className="mt-8 mb-3 text-xl font-medium">5. Data</h2>
      <p>
        You own the data you upload. We process it on your behalf under the
        Data Processing Agreement and Privacy Policy. Accounting records are
        retained for 7 years as required by <em>bokföringslagen</em> even
        after account deletion.
      </p>

      <h2 className="mt-8 mb-3 text-xl font-medium">6. Liability</h2>
      <p>
        The service is provided "as is". To the extent permitted by law, our
        aggregate liability is limited to fees paid in the 12 months preceding
        the claim. We are not liable for indirect or consequential losses.
      </p>

      <h2 className="mt-8 mb-3 text-xl font-medium">7. Governing law</h2>
      <p>
        These terms are governed by Swedish law. Disputes are resolved in
        Stockholm District Court unless mandatory consumer law requires
        otherwise.
      </p>

      <h2 className="mt-8 mb-3 text-xl font-medium">8. Contact</h2>
      <p>
        Legal questions: <a className="underline" href="mailto:legal@varuflow.se">legal@varuflow.se</a>.
      </p>
    </main>
  );
}
