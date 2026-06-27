"use client";
import { useParams } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function ReportingHubPage() {
  const params = useParams();
  const locale = params.locale as string;

  const cards = [
    {
      title: "Customer Statements",
      description: "Generate and download PDF, CSV, or JSON statements for customers.",
      href: `/${locale}/reporting/statements`,
    },
    {
      title: "Mobile Dashboard",
      description: "Configure live KPIs and push notification tokens for the mobile app.",
      href: `/${locale}/reporting/mobile-dashboard`,
    },
    {
      title: "Voice Reports",
      description: "Ask natural-language questions and get instant data answers.",
      href: `/${locale}/reporting/voice-reports`,
    },
    {
      title: "Anomaly Notifications",
      description: "Review detected anomalies and manage alert read-status.",
      href: `/${locale}/reporting/anomalies`,
    },
  ];

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">Reporting Hub</h1>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
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
