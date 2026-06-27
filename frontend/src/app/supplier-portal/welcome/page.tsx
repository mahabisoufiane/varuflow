export default function WelcomePage() {
  return (
    <div className="rounded-xl border bg-white p-8 text-center space-y-4">
      <h1 className="text-xl font-semibold text-gray-900">Supplier portal</h1>
      <p className="text-sm text-muted-foreground">
        This portal is accessed via a secure link sent by the organisation
        that purchases from you. If you've misplaced your link, please
        contact them to request a new one.
      </p>
    </div>
  );
}
