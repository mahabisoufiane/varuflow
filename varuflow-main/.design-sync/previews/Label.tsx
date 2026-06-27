import { Label } from 'varuflow-ui';

export function Default() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <Label htmlFor="company">Company name</Label>
      <Label htmlFor="email">Email address</Label>
      <Label htmlFor="vat">VAT number</Label>
    </div>
  );
}

export function WithInput() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6, width: 280 }}>
      <Label htmlFor="org">Organisation</Label>
      <input id="org" placeholder="Nordic SMB AS" style={{ border: '1px solid #ccc', borderRadius: 6, padding: '6px 10px', fontSize: 14 }} />
    </div>
  );
}
