import { Table, TableBody, TableCaption, TableCell, TableHead, TableHeader, TableRow } from 'varuflow-ui';

export function Default() {
  return (
    <div style={{ padding: '16px', maxWidth: '480px' }}>
      <Table>
        <TableCaption>A summary of Q2 sales performance</TableCaption>
        <TableHeader>
          <TableRow>
            <TableHead>Region</TableHead>
            <TableHead>Sales</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow>
            <TableCell>Stockholm</TableCell>
            <TableCell>240 000 SEK</TableCell>
          </TableRow>
          <TableRow>
            <TableCell>Göteborg</TableCell>
            <TableCell>185 000 SEK</TableCell>
          </TableRow>
        </TableBody>
      </Table>
    </div>
  );
}
