"use client";
import { useParams } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import Link from "next/link";

export default function B2BHubPage() {
  const { locale } = useParams<{ locale: string }>();

  const sections = [
    {
      href: `/${locale}/b2b/buyer-pos`,
      title: "Buyer POs",
      description: "Manage purchase orders submitted by your buyers",
    },
    {
      href: `/${locale}/b2b/org-members`,
      title: "Org Members",
      description: "Buyer organization team members and approval workflows",
    },
    {
      href: `/${locale}/b2b/negotiated-pricing`,
      title: "Negotiated Pricing",
      description: "View custom pricing tiers visible to buyers",
    },
    {
      href: `/${locale}/b2b/quote-comparisons`,
      title: "Quote Comparisons",
      description: "Side-by-side quote comparison tool",
    },
  ];

  return (
    <div className="p-6 space-y-6 max-w-4xl mx-auto">
      <div>
        <h1 className="text-2xl font-bold">B2B Hub</h1>
        <p className="text-muted-foreground mt-1">
          Manage buyer relationships, purchase orders, and pricing agreements.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {sections.map((section) => (
          <Link key={section.href} href={section.href}>
            <Card className="h-full cursor-pointer hover:border-primary transition-colors">
              <CardHeader>
                <CardTitle className="text-lg">{section.title}</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">
                  {section.description}
                </p>
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
