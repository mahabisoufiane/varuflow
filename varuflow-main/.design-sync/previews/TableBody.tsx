import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from 'varuflow-ui';

export function Default() {
  return (
    <div style={{ padding: '16px', maxWidth: '480px' }}>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Name</TableHead>
            <TableHead>Value</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow>
            <TableCell>Revenue</TableCell>
            <TableCell>120 000 SEK</TableCell>
          </TableRow>
          <TableRow>
            <TableCell>Expenses</TableCell>
            <TableCell>45 000 SEK</TableCell>
          </TableRow>
          <TableRow>
            <TableCell>Profit</TableCell>
            <TableCell>75 000 SEK</TableCell>
          </TableRow>
        </TableBody>
      </Table>
    </div>
  );
}
