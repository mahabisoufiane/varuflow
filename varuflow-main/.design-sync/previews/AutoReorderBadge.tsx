/**
 * AutoReorderBadge uses useTranslations from next-intl which requires a
 * provider context. We render the badge markup directly to show the visual states.
 */
import { Repeat2, AlertTriangle } from 'lucide-react';

function AutoBadge() {
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: '4px',
      borderRadius: '9999px', padding: '2px 8px', fontSize: '10px', fontWeight: 700,
      background: 'rgba(99,102,241,0.1)', color: '#a5b4fc', border: '1px solid rgba(99,102,241,0.3)'
    }}>
      <Repeat2 style={{ width: 12, height: 12 }} />
      Auto
    </span>
  );
}

function NoSupplierBadge() {
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: '4px',
      borderRadius: '9999px', padding: '2px 8px', fontSize: '10px', fontWeight: 700,
      background: 'rgba(245,158,11,0.1)', color: '#fcd34d', border: '1px solid rgba(245,158,11,0.3)'
    }}>
      <AlertTriangle style={{ width: 12, height: 12 }} />
      No supplier
    </span>
  );
}

export function AutoEnabled() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', padding: '16px', fontFamily: 'system-ui, sans-serif', background: '#1a2332', borderRadius: '10px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        <span style={{ fontSize: '13px', color: '#94a3b8', minWidth: '180px' }}>Oatly Havredryck 1L</span>
        <AutoBadge />
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        <span style={{ fontSize: '13px', color: '#94a3b8', minWidth: '180px' }}>Arla Mjölk 3% 1L</span>
        <AutoBadge />
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        <span style={{ fontSize: '13px', color: '#94a3b8', minWidth: '180px' }}>Gevalia Kaffe 500g</span>
        <AutoBadge />
      </div>
    </div>
  );
}

export function NoSupplierWarning() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', padding: '16px', fontFamily: 'system-ui, sans-serif', background: '#1a2332', borderRadius: '10px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        <span style={{ fontSize: '13px', color: '#94a3b8', minWidth: '180px' }}>Marabou Mjölkchoklad</span>
        <NoSupplierBadge />
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        <span style={{ fontSize: '13px', color: '#94a3b8', minWidth: '180px' }}>Felix Ketchup 875g</span>
        <NoSupplierBadge />
      </div>
    </div>
  );
}

export function Disabled() {
  return (
    <div style={{ padding: '16px', fontFamily: 'system-ui, sans-serif', background: '#f9fafb', borderRadius: '10px', border: '1px solid #e5e7eb' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        <span style={{ fontSize: '13px', color: '#374151', minWidth: '180px' }}>Felix Ketchup 875g</span>
        <span style={{ fontSize: '12px', color: '#9ca3af' }}>(no badge — auto-reorder disabled)</span>
      </div>
    </div>
  );
}
