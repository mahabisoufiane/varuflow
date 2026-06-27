import { Card, CardHeader, CardTitle, CardDescription, CardContent } from 'varuflow-ui';

export function TitleOnly() {
  return (
    <Card style={{ maxWidth: '320px' }}>
      <CardHeader>
        <CardTitle>Recent invoices</CardTitle>
      </CardHeader>
      <CardContent>
        <p style={{ fontSize: '13px', color: '#6b7280', margin: 0 }}>3 invoices pending payment</p>
      </CardContent>
    </Card>
  );
}

export function TitleAndDescription() {
  return (
    <Card style={{ maxWidth: '320px' }}>
      <CardHeader>
        <CardTitle>Customer profile</CardTitle>
        <CardDescription>Manage contact details and payment terms</CardDescription>
      </CardHeader>
      <CardContent>
        <p style={{ fontSize: '13px', color: '#6b7280', margin: 0 }}>Eriksson & Partners AB · SE556123-4567</p>
      </CardContent>
    </Card>
  );
}
