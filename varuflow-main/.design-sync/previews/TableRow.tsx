import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from 'varuflow-ui';

export function Default() {
  return (
    <div style={{ padding: '16px', maxWidth: '480px' }}>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Staff</TableHead>
            <TableHead>Shift</TableHead>
            <TableHead>Hours</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow>
            <TableCell>Anna Lindqvist</TableCell>
            <TableCell>Morning</TableCell>
            <TableCell>8h</TableCell>
          </TableRow>
          <TableRow data-state="selected">
            <TableCell>Erik Ström</TableCell>
            <TableCell>Evening</TableCell>
            <TableCell>6h</TableCell>
          </TableRow>
          <TableRow>
            <TableCell>Maja Karlsson</TableCell>
            <TableCell>Night</TableCell>
            <TableCell>10h</TableCell>
          </TableRow>
        </TableBody>
      </Table>
    </div>
  );
}
