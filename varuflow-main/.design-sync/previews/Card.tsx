import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from 'varuflow-ui';

export function ProductCard() {
  return (
    <div style={{ padding: '24px', maxWidth: '360px' }}>
      <Card>
        <CardHeader>
          <CardTitle>Wireless Headphones Pro</CardTitle>
          <CardDescription>SKU: WHP-2024 · In stock: 42 units</CardDescription>
        </CardHeader>
        <CardContent>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
            <span style={{ fontSize: '13px', color: '#64748b' }}>Price</span>
            <span style={{ fontWeight: 600, fontSize: '14px' }}>€149.00</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
            <span style={{ fontSize: '13px', color: '#64748b' }}>Category</span>
            <span style={{ fontSize: '14px' }}>Electronics</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ fontSize: '13px', color: '#64748b' }}>Reorder at</span>
            <span style={{ fontSize: '14px' }}>10 units</span>
          </div>
        </CardContent>
        <CardFooter style={{ gap: '8px' }}>
          <button style={{ flex: 1, padding: '8px', borderRadius: '6px', background: '#2563eb', color: 'white', border: 'none', cursor: 'pointer', fontSize: '13px' }}>Edit</button>
          <button style={{ flex: 1, padding: '8px', borderRadius: '6px', background: 'transparent', color: '#64748b', border: '1px solid #e2e8f0', cursor: 'pointer', fontSize: '13px' }}>Archive</button>
        </CardFooter>
      </Card>
    </div>
  );
}

export function InteractiveCard() {
  return (
    <div style={{ padding: '24px', maxWidth: '360px' }}>
      <Card interactive>
        <CardHeader>
          <CardTitle>Q3 Sales Report</CardTitle>
          <CardDescription>Generated 23 Jun 2026 · PDF · 2.1 MB</CardDescription>
        </CardHeader>
        <CardContent>
          <p style={{ fontSize: '14px', color: '#374151', lineHeight: '1.5' }}>
            Revenue up 18% YoY. Top performer: Electronics category with €84,200 total.
          </p>
        </CardContent>
        <CardFooter>
          <span style={{ fontSize: '12px', color: '#94a3b8' }}>Click to download</span>
        </CardFooter>
      </Card>
    </div>
  );
}

export function CustomerCard() {
  return (
    <div style={{ padding: '24px', maxWidth: '360px' }}>
      <Card>
        <CardHeader>
          <CardTitle>Anna Lindström</CardTitle>
          <CardDescription>anna.lindstrom@example.se · +46 70 123 4567</CardDescription>
        </CardHeader>
        <CardContent>
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            <span style={{ fontSize: '12px', background: '#f0fdf4', color: '#16a34a', padding: '2px 8px', borderRadius: '12px' }}>Gold Member</span>
            <span style={{ fontSize: '12px', background: '#eff6ff', color: '#2563eb', padding: '2px 8px', borderRadius: '12px' }}>14 orders</span>
            <span style={{ fontSize: '12px', background: '#f8fafc', color: '#64748b', padding: '2px 8px', borderRadius: '12px' }}>Since 2021</span>
          </div>
        </CardContent>
        <CardFooter>
          <span style={{ fontSize: '13px', color: '#64748b' }}>Last purchase: 3 days ago</span>
        </CardFooter>
      </Card>
    </div>
  );
}
