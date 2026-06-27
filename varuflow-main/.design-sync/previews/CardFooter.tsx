import { Card, CardContent, CardFooter } from 'varuflow-ui';
import { Button } from 'varuflow-ui';

export function WithActions() {
  return (
    <Card style={{ maxWidth: '320px' }}>
      <CardContent>
        <p style={{ fontSize: '14px', color: '#374151', margin: 0 }}>
          Delete this invoice? This action cannot be undone.
        </p>
      </CardContent>
      <CardFooter style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
        <Button variant="outline" size="sm">Cancel</Button>
        <Button variant="destructive" size="sm">Delete</Button>
      </CardFooter>
    </Card>
  );
}

export function WithLink() {
  return (
    <Card style={{ maxWidth: '320px' }}>
      <CardContent>
        <p style={{ fontSize: '14px', color: '#374151', margin: 0 }}>
          Invoice INV-2024-0148 sent to anna@lindstrom.se
        </p>
      </CardContent>
      <CardFooter>
        <span style={{ fontSize: '12px', color: '#6b7280' }}>Sent 2 min ago</span>
      </CardFooter>
    </Card>
  );
}
