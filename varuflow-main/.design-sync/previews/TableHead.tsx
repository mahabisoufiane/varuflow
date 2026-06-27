import { Table, TableHead, TableHeader, TableRow } from 'varuflow-ui';

export function Default() {
  return (
    <div style={{ padding: '16px', maxWidth: '480px' }}>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Customer</TableHead>
            <TableHead>Date</TableHead>
            <TableHead style={{ textAlign: 'right' }}>Total</TableHead>
            <TableHead>Status</TableHead>
          </TableRow>
        </TableHeader>
      </Table>
    </div>
  );
}
