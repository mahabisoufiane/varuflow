import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from 'varuflow-ui';

export function Default() {
  return (
    <div style={{ padding: '16px', maxWidth: '480px' }}>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Product</TableHead>
            <TableHead>SKU</TableHead>
            <TableHead>Stock</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow>
            <TableCell>Nordic Chair</TableCell>
            <TableCell style={{ color: '#6B7280', fontFamily: 'monospace' }}>NCH-001</TableCell>
            <TableCell style={{ fontWeight: 600, color: '#16A34A' }}>42 units</TableCell>
          </TableRow>
          <TableRow>
            <TableCell>Birch Desk</TableCell>
            <TableCell style={{ color: '#6B7280', fontFamily: 'monospace' }}>BDS-004</TableCell>
            <TableCell style={{ fontWeight: 600, color: '#DC2626' }}>2 units</TableCell>
          </TableRow>
        </TableBody>
      </Table>
    </div>
  );
}
