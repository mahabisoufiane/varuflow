"use client";
import { useParams } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import Link from "next/link";

const NAV_CARDS = [
  {
    title: "Live Chat",
    description: "Monitor and respond to live chat sessions with customers.",
    href: "customer-service/live-chat",
  },
  {
    title: "AI Chatbot",
    description: "Configure the AI chatbot and review automated conversations.",
    href: "customer-service/chatbot",
  },
  {
    title: "Knowledge Base",
    description: "Manage help articles and categories for self-service support.",
    href: "customer-service/knowledge-base",
  },
  {
    title: "Returns Pickup",
    description: "Schedule and track return pickups for customer orders.",
    href: "customer-service/return-pickups",
  },
];

export default function CustomerServiceHubPage() {
  const params = useParams();
  const locale = params.locale as string;

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Customer Service Hub</h1>
        <p className="text-muted-foreground mt-1">
          Manage all customer-facing support channels from one place.
        </p>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {NAV_CARDS.map((card) => (
          <Card key={card.href} className="hover:shadow-md transition-shadow">
            <CardHeader>
              <CardTitle className="text-lg">{card.title}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-muted-foreground">{card.description}</p>
              <Link href={`/${locale}/${card.href}`}>
                <Button variant="outline" className="w-full">
                  Open
                </Button>
              </Link>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
