import { VFSelect } from 'varuflow-ui';

export function Basic() {
  return (
    <div style={{ padding: '16px', maxWidth: '320px' }}>
      <VFSelect defaultValue="">
        <option value="" disabled>Select country…</option>
        <option value="se">Sweden</option>
        <option value="no">Norway</option>
        <option value="dk">Denmark</option>
        <option value="fi">Finland</option>
      </VFSelect>
    </div>
  );
}

export function WithValue() {
  return (
    <div style={{ padding: '16px', maxWidth: '320px' }}>
      <VFSelect defaultValue="no">
        <option value="se">Sweden</option>
        <option value="no">Norway</option>
        <option value="dk">Denmark</option>
        <option value="fi">Finland</option>
      </VFSelect>
    </div>
  );
}

export function Disabled() {
  return (
    <div style={{ padding: '16px', maxWidth: '320px' }}>
      <VFSelect disabled defaultValue="se">
        <option value="se">Sweden</option>
        <option value="no">Norway</option>
      </VFSelect>
    </div>
  );
}
