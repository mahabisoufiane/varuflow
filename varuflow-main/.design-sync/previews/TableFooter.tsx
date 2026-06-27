import { Table, TableBody, TableCell, TableFooter, TableHead, TableHeader, TableRow } from 'varuflow-ui';

export function Default() {
  return (
    <div style={{ padding: '16px', maxWidth: '480px' }}>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Item</TableHead>
            <TableHead style={{ textAlign: 'right' }}>Amount</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow>
            <TableCell>Consulting — 8h</TableCell>
            <TableCell style={{ textAlign: 'right' }}>6 400 SEK</TableCell>
          </TableRow>
          <TableRow>
            <TableCell>Design review</TableCell>
            <TableCell style={{ textAlign: 'right' }}>2 000 SEK</TableCell>
          </TableRow>
        </TableBody>
        <TableFooter>
          <TableRow>
            <TableCell>Total (excl. VAT)</TableCell>
            <TableCell style={{ textAlign: 'right' }}>8 400 SEK</TableCell>
          </TableRow>
        </TableFooter>
      </Table>
    </div>
  );
}
