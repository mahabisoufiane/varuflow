"use client";
import { useParams } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import Link from "next/link";

const NAV_CARDS = [
  {
    title: "Reviews & Ratings",
    description: "View and manage verified customer reviews for your services.",
    href: "trust/reviews",
  },
  {
    title: "Staff Credentials",
    description: "Track certifications, training records, and awards for your team.",
    href: "trust/credentials",
  },
  {
    title: "Booking Capacity",
    description: "Monitor and configure slot availability and urgency messaging.",
    href: "trust/capacity",
  },
  {
    title: "Portfolio Gallery",
    description: "Showcase staff work through a curated photo portfolio.",
    href: "trust/portfolio",
  },
];

export default function TrustHubPage() {
  const params = useParams();
  const locale = params.locale as string;

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Trust &amp; Verification Hub</h1>
        <p className="text-muted-foreground mt-1">
          Build credibility with customers through reviews, credentials, and showcased work.
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
