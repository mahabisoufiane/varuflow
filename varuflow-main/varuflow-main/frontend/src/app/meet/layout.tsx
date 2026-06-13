import type { Metadata } from "next";
import "../globals.css";

export const metadata: Metadata = {
  title: "Schedule a Meeting",
};

export default function MeetLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-gray-50 antialiased">
        {children}
      </body>
    </html>
  );
}
