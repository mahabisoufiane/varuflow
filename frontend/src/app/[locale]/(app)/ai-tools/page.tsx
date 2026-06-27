"use client";
import { useParams } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function AiToolsHubPage() {
  const params = useParams();
  const locale = params.locale as string;

  const cards = [
    {
      title: "Product Descriptions",
      description: "Generate AI-written product descriptions tailored to your brand tone.",
      href: `/${locale}/ai-tools/product-descriptions`,
    },
    {
      title: "Email Drafts",
      description: "Auto-draft professional replies to customer messages.",
      href: `/${locale}/ai-tools/email-drafts`,
    },
    {
      title: "Photo Tags",
      description: "Analyze product photos and generate structured tags automatically.",
      href: `/${locale}/ai-tools/photo-tags`,
    },
    {
      title: "Pricing Suggestions",
      description: "Get AI-driven price recommendations based on cost and market data.",
      href: `/${locale}/ai-tools/pricing`,
    },
    {
      title: "Customer Personas",
      description: "Compute behavioral customer segments for targeted outreach.",
      href: `/${locale}/ai-tools/personas`,
    },
  ];

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">AI Tools Hub</h1>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {cards.map((card) => (
          <a key={card.href} href={card.href} className="block">
            <Card className="h-full hover:shadow-md transition-shadow cursor-pointer">
              <CardHeader>
                <CardTitle className="text-base">{card.title}</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">{card.description}</p>
              </CardContent>
            </Card>
          </a>
        ))}
      </div>
    </div>
  );
}
