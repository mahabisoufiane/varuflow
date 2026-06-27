import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableFooter,
  TableHead,
  TableHeader,
  TableRow,
} from 'varuflow-ui';

const invoices = [
  { id: 'INV-001', customer: 'Acme AB', amount: '12 500 SEK', status: 'Paid', due: '2026-05-15' },
  { id: 'INV-002', customer: 'Björk & Co', amount: '8 200 SEK', status: 'Pending', due: '2026-06-01' },
  { id: 'INV-003', customer: 'Ek Consulting', amount: '34 000 SEK', status: 'Overdue', due: '2026-04-30' },
];

export function InvoiceTable() {
  return (
    <div style={{ padding: '16px', maxWidth: '720px' }}>
      <Table>
        <TableCaption>Recent invoices — last 30 days</TableCaption>
        <TableHeader>
          <TableRow>
            <TableHead>Invoice</TableHead>
            <TableHead>Customer</TableHead>
            <TableHead>Due date</TableHead>
            <TableHead style={{ textAlign: 'right' }}>Amount</TableHead>
            <TableHead>Status</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {invoices.map((inv) => (
            <TableRow key={inv.id}>
              <TableCell style={{ fontWeight: 500 }}>{inv.id}</TableCell>
              <TableCell>{inv.customer}</TableCell>
              <TableCell>{inv.due}</TableCell>
              <TableCell style={{ textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>{inv.amount}</TableCell>
              <TableCell>{inv.status}</TableCell>
            </TableRow>
          ))}
        </TableBody>
        <TableFooter>
          <TableRow>
            <TableCell colSpan={3} style={{ fontWeight: 600 }}>Total</TableCell>
            <TableCell style={{ textAlign: 'right', fontWeight: 600 }}>54 700 SEK</TableCell>
            <TableCell />
          </TableRow>
        </TableFooter>
      </Table>
    </div>
  );
}
