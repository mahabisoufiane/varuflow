/**
 * Widget-specific layout. Skips the app-wide chrome so the iframe
 * renders as a standalone page — no sidebar, no auth redirect, no
 * locale-prefix routing.
 */
import "../globals.css";

export const metadata = {
  title: "Book appointment",
  robots: { index: false, follow: false },
};

export default function WidgetLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html>
      <body className="bg-white text-gray-900">{children}</body>
    </html>
  );
}
