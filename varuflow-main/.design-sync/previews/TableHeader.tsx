import { Table, TableHead, TableHeader, TableRow } from 'varuflow-ui';

export function Default() {
  return (
    <div style={{ padding: '16px', maxWidth: '480px' }}>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Invoice #</TableHead>
            <TableHead>Due date</TableHead>
            <TableHead>Amount</TableHead>
            <TableHead>Actions</TableHead>
          </TableRow>
        </TableHeader>
      </Table>
    </div>
  );
}
