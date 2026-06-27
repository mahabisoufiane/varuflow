import type { Metadata } from "next";
import "../globals.css";

export const metadata: Metadata = {
  title: "Shop",
  description: "Online shop",
};

export default function ShopLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-gray-50 antialiased">
        {children}
      </body>
    </html>
  );
}
