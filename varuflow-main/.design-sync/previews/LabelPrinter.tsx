/**
 * LabelPrinter uses next-intl useTranslations and api.get on mount.
 * We render a faithful static reproduction of its UI to demonstrate the layout
 * without the live hooks firing.
 */
import { Barcode, QrCode, Printer, Search } from 'lucide-react';

const products = [
  { id: 'p1', name: 'Oatly Havredryck 1L', sku: 'OAT-1L', barcode: '7394376615841', sell_price: 18.9 },
  { id: 'p2', name: 'Arla Mjölk 3% 1L', sku: 'ARL-3PCT', barcode: '7310865085313', sell_price: 14.5 },
  { id: 'p3', name: 'Marabou Mjölkchoklad 200g', sku: 'MAR-200', barcode: '7622201148767', sell_price: 29.9 },
  { id: 'p4', name: 'Gevalia Kaffe 500g', sku: 'GEV-500', barcode: '7310511040500', sell_price: 69.0 },
];

const selected = new Set(['p1', 'p3']);

export function PrinterUI() {
  return (
    <div style={{ fontFamily: 'system-ui, sans-serif', maxWidth: '760px', padding: '16px' }}>
      {/* Options panel */}
      <div style={{ background: '#f9fafb', border: '1px solid #e5e7eb', borderRadius: '14px', padding: '20px', marginBottom: '20px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '12px', marginBottom: '16px' }}>
          {/* Size */}
          <div>
            <label style={{ display: 'block', fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: '#6b7280', marginBottom: '8px' }}>Size</label>
            <select style={{ width: '100%', height: '36px', borderRadius: '8px', border: '1px solid #d1d5db', padding: '0 8px', fontSize: '12px' }}>
              <option>50x30 (50×30mm)</option>
              <option>38x25 (38×25mm)</option>
              <option>a4 (A4 sheet, 24/sheet)</option>
            </select>
          </div>
          {/* Format */}
          <div>
            <label style={{ display: 'block', fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: '#6b7280', marginBottom: '8px' }}>Format</label>
            <div style={{ display: 'flex', gap: '8px' }}>
              <button style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px', borderRadius: '10px', padding: '8px', fontSize: '12px', fontWeight: 600, background: '#6366f1', color: '#fff', border: 'none', cursor: 'pointer' }}>
                <Barcode style={{ width: 14, height: 14 }} /> Code128
              </button>
              <button style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px', borderRadius: '10px', padding: '8px', fontSize: '12px', fontWeight: 600, background: '#f3f4f6', color: '#374151', border: '1px solid #e5e7eb', cursor: 'pointer' }}>
                <QrCode style={{ width: 14, height: 14 }} /> QR
              </button>
            </div>
          </div>
          {/* Copies */}
          <div>
            <label style={{ display: 'block', fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: '#6b7280', marginBottom: '8px' }}>Copies</label>
            <input type="number" defaultValue={1} style={{ width: '100%', height: '36px', borderRadius: '8px', border: '1px solid #d1d5db', padding: '0 8px', fontSize: '12px' }} />
          </div>
          {/* Show price */}
          <div style={{ display: 'flex', alignItems: 'flex-end' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', fontSize: '12px', fontWeight: 600, color: '#374151' }}>
              <input type="checkbox" defaultChecked style={{ width: 16, height: 16, borderRadius: '4px' }} />
              Show price
            </label>
          </div>
        </div>
        {/* Summary + CTA */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingTop: '12px', borderTop: '1px solid #e5e7eb' }}>
          <div style={{ fontSize: '12px', color: '#6b7280' }}>
            2 products selected · 2 labels · 1 sheet
          </div>
          <button style={{ display: 'flex', alignItems: 'center', gap: '6px', background: '#1a2332', color: '#fff', border: 'none', borderRadius: '10px', padding: '8px 16px', fontSize: '12px', fontWeight: 600, cursor: 'pointer', minWidth: '140px', justifyContent: 'center' }}>
            <Printer style={{ width: 14, height: 14 }} /> Print labels
          </button>
        </div>
      </div>

      {/* Product picker */}
      <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: '14px', overflow: 'hidden' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 20px', borderBottom: '1px solid #e5e7eb' }}>
          <h2 style={{ fontSize: '13px', fontWeight: 600, color: '#111827', margin: 0 }}>Select products</h2>
          <div style={{ position: 'relative' }}>
            <Search style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', width: 14, height: 14, color: '#9ca3af' }} />
            <input placeholder="Search products…" style={{ height: '34px', borderRadius: '8px', border: '1px solid #d1d5db', paddingLeft: '30px', paddingRight: '8px', fontSize: '12px', width: '200px' }} />
          </div>
        </div>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
          <thead>
            <tr style={{ background: '#f9fafb', borderBottom: '1px solid #e5e7eb' }}>
              <th style={{ padding: '10px 20px', textAlign: 'left', width: '40px' }}>
                <input type="checkbox" style={{ width: 16, height: 16 }} />
              </th>
              <th style={{ padding: '10px 20px', textAlign: 'left', fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: '#6b7280' }}>Product</th>
              <th style={{ padding: '10px 20px', textAlign: 'left', fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: '#6b7280' }}>SKU</th>
              <th style={{ padding: '10px 20px', textAlign: 'left', fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: '#6b7280' }}>Barcode</th>
              <th style={{ padding: '10px 20px', textAlign: 'right', fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: '#6b7280' }}>Price</th>
            </tr>
          </thead>
          <tbody>
            {products.map((p) => (
              <tr key={p.id} style={{ borderBottom: '1px solid #f3f4f6', cursor: 'pointer', background: selected.has(p.id) ? '#f0fdf4' : '#fff' }}>
                <td style={{ padding: '14px 20px' }}>
                  <input type="checkbox" checked={selected.has(p.id)} readOnly style={{ width: 16, height: 16 }} />
                </td>
                <td style={{ padding: '14px 20px', fontWeight: 500, color: '#111827' }}>{p.name}</td>
                <td style={{ padding: '14px 20px', fontFamily: 'monospace', fontSize: '12px', color: '#6b7280' }}>{p.sku}</td>
                <td style={{ padding: '14px 20px', fontFamily: 'monospace', fontSize: '12px', color: '#9ca3af' }}>{p.barcode}</td>
                <td style={{ padding: '14px 20px', textAlign: 'right', color: '#374151', fontVariantNumeric: 'tabular-nums' }}>{p.sell_price.toFixed(2)} kr</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
