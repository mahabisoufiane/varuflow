import { Card, CardContent } from 'varuflow-ui';

export function WithText() {
  return (
    <Card style={{ maxWidth: '320px' }}>
      <CardContent>
        <p style={{ fontSize: '14px', color: '#374151', margin: 0 }}>
          CardContent provides consistent padding and spacing inside a Card. Place any content here — text, lists, form fields, or data.
        </p>
      </CardContent>
    </Card>
  );
}

export function WithData() {
  return (
    <Card style={{ maxWidth: '320px' }}>
      <CardContent>
        <dl style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px 16px', fontSize: '13px', margin: 0 }}>
          <dt style={{ color: '#6b7280' }}>Customer</dt>
          <dd style={{ color: '#111827', margin: 0, fontWeight: 500 }}>Eriksson & Partners</dd>
          <dt style={{ color: '#6b7280' }}>Invoice</dt>
          <dd style={{ color: '#111827', margin: 0, fontWeight: 500 }}>INV-2024-0142</dd>
          <dt style={{ color: '#6b7280' }}>Amount</dt>
          <dd style={{ color: '#111827', margin: 0, fontWeight: 500 }}>12 500 kr</dd>
        </dl>
      </CardContent>
    </Card>
  );
}
