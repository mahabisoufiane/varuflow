import { Textarea } from 'varuflow-ui';

export function Default() {
  return (
    <div style={{ width: 360 }}>
      <Textarea placeholder="Add a note about this customer…" rows={4} />
    </div>
  );
}

export function WithContent() {
  return (
    <div style={{ width: 360 }}>
      <Textarea defaultValue="Prefers email contact. Has standing order for 20 units of SKU-4412 every second Friday. Net 30 payment terms agreed." rows={5} />
    </div>
  );
}

export function Disabled() {
  return (
    <div style={{ width: 360 }}>
      <Textarea defaultValue="This field is read-only in view mode." disabled rows={3} />
    </div>
  );
}
