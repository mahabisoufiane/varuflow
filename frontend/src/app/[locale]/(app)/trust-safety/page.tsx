"use client";
import { useParams, useRouter } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const NAV_CARDS = [
  {
    title: "Identity Verification",
    description: "Verify customer and partner identities via document checks.",
    href: "trust-safety/identity-verification",
  },
  {
    title: "Background Checks",
    description: "Run and track staff background and criminal record checks.",
    href: "trust-safety/background-checks",
  },
  {
    title: "Insurance Add-ons",
    description: "Manage insurance products available for customers to purchase.",
    href: "trust-safety/insurance",
  },
  {
    title: "Dispute Resolution",
    description: "Handle and resolve disputes between customers and merchants.",
    href: "trust-safety/disputes",
  },
  {
    title: "Merchant Reviews",
    description: "Internal merchant reviews and reputation scoring for customers.",
    href: "trust-safety/merchant-reviews",
  },
];

export default function TrustSafetyHubPage() {
  const params = useParams();
  const router = useRouter();
  const locale = params.locale as string;

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Trust &amp; Safety</h1>
        <p className="text-muted-foreground mt-1">
          Manage verification, compliance, and trust tools for your platform.
        </p>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {NAV_CARDS.map((card) => (
          <Card
            key={card.href}
            className="cursor-pointer hover:border-primary transition-colors"
            onClick={() => router.push(`/${locale}/${card.href}`)}
          >
            <CardHeader>
              <CardTitle className="text-lg">{card.title}</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">{card.description}</p>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
