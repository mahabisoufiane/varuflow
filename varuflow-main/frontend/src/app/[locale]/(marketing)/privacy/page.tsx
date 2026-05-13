import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Privacy policy — Varuflow",
};

export default function PrivacyPage() {
  const updated = "2026-04-21";
  return (
    <main className="mx-auto max-w-3xl px-6 py-12 text-sm leading-relaxed">
      <h1 className="mb-2 text-3xl font-semibold">Privacy policy</h1>
      <p className="mb-8 text-neutral-500">Last updated: {updated}</p>

      <p className="mb-4">
        This document describes how <strong>Varuflow AB</strong> ("we", "us")
        processes personal data when you use the Varuflow service. This page is
        a plain-language summary — the formal terms in our Data Processing
        Agreement (available on request) take precedence in case of conflict.
      </p>

      <h2 className="mt-8 mb-3 text-xl font-medium">1. Data we process</h2>
      <ul className="list-disc space-y-1 pl-6">
        <li>Account data: email, full name, organization, role.</li>
        <li>Organization data: company name, VAT / org number, address.</li>
        <li>Customer data you upload: contact details for your customers.</li>
        <li>Invoice / inventory / POS records you create in the app.</li>
        <li>Technical logs: IP address, timestamps, error traces (90-day retention).</li>
      </ul>

      <h2 className="mt-8 mb-3 text-xl font-medium">2. Legal bases</h2>
      <p>
        Contract (Art. 6(1)(b) GDPR) for running the service; legitimate
        interest (Art. 6(1)(f)) for fraud prevention and product improvement;
        legal obligation (Art. 6(1)(c)) for bookkeeping retention.
      </p>

      <h2 className="mt-8 mb-3 text-xl font-medium">3. Sub-processors</h2>
      <p>We use a small set of processors to run the service:</p>
      <ul className="list-disc space-y-1 pl-6">
        <li>Supabase (EU region) — authentication and database hosting.</li>
        <li>Railway — backend hosting.</li>
        <li>Vercel — frontend hosting and CDN.</li>
        <li>Stripe — payment processing.</li>
        <li>Resend — transactional email.</li>
        <li>OpenAI — AI assistant responses (prompts are not stored for training).</li>
        <li>Sentry — error monitoring (PII scrubbing enabled).</li>
      </ul>

      <h2 className="mt-8 mb-3 text-xl font-medium">4. Cookies</h2>
      <p>
        We use strictly-necessary cookies and localStorage to keep you signed in
        and remember UI preferences. We do not use advertising or cross-site
        tracking cookies.
      </p>

      <h2 className="mt-8 mb-3 text-xl font-medium">5. Your rights</h2>
      <ul className="list-disc space-y-1 pl-6">
        <li>Right of access: export every record in your organization from Settings → Data & privacy.</li>
        <li>Right to rectification: edit records directly in the app.</li>
        <li>Right to erasure: delete your organization from Settings → Data & privacy. Accounting records are retained in anonymised form for 7 years as required by <em>bokföringslagen</em> (BFL 7 kap. 2 §).</li>
        <li>Right to object / restrict: email <a className="underline" href="mailto:privacy@varuflow.se">privacy@varuflow.se</a>.</li>
        <li>Right to lodge a complaint with <em>Integritetsskyddsmyndigheten</em> (IMY).</li>
      </ul>

      <h2 className="mt-8 mb-3 text-xl font-medium">6. Contact</h2>
      <p>
        Data-protection questions: <a className="underline" href="mailto:privacy@varuflow.se">privacy@varuflow.se</a>.
      </p>
    </main>
  );
}
