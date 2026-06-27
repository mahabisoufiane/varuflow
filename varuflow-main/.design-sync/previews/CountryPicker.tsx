import { CountryPicker } from 'varuflow-ui';

export function Default() {
  return (
    <div style={{ padding: '24px', background: '#fff' }}>
      <CountryPicker apiBase="https://varuflow-production.up.railway.app" />
    </div>
  );
}
