/**
 * PosProductGrid uses usePos() context and api calls. Static reproduction.
 */

const products = [
  { id: 'p1', name: 'Oatly Havredryck 1L', sell_price: '18.90', stock: 24, category: 'Mejeri' },
  { id: 'p2', name: 'Arla Mjölk 3% 1L', sell_price: '14.50', stock: 8, category: 'Mejeri' },
  { id: 'p3', name: 'Marabou Mjölkchoklad 200g', sell_price: '29.90', stock: 3, category: 'Godis' },
  { id: 'p4', name: 'Gevalia Kaffe 500g', sell_price: '69.00', stock: 0, category: 'Kaffe' },
  { id: 'p5', name: 'Felix Ketchup 875g', sell_price: '39.90', stock: 15, category: 'Kryddor' },
  { id: 'p6', name: 'Fazer Pärlsocker 500g', sell_price: '24.50', stock: 11, category: 'Bakning' },
  { id: 'p7', name: 'Pågen Frukostfralla', sell_price: '22.90', stock: 7, category: 'Bröd' },
  { id: 'p8', name: 'Santa Maria Tacosås', sell_price: '34.90', stock: 4, category: 'Kryddor' },
];

function stockTone(stock: number): { background: string; color: string } {
  if (stock <= 0) return { background: '#fee2e2', color: '#b91c1c' };
  if (stock < 5) return { background: '#fef3c7', color: '#92400e' };
  return { background: '#d1fae5', color: '#065f46' };
}

export function ProductGrid() {
  const categories = ['all', 'Mejeri', 'Godis', 'Kaffe', 'Kryddor', 'Bakning', 'Bröd'];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', fontFamily: 'system-ui, sans-serif', maxWidth: '640px', padding: '16px' }}>
      {/* Search */}
      <input
        placeholder="Search products or scan barcode..."
        style={{ width: '100%', height: '48px', borderRadius: '10px', border: '1px solid #d1d5db', padding: '0 16px', fontSize: '16px', background: '#fff', boxSizing: 'border-box' }}
      />

      {/* Category tabs */}
      <div style={{ display: 'flex', gap: '8px', overflowX: 'auto', paddingBottom: '4px' }}>
        {categories.map((c, i) => (
          <button key={c} style={{
            whiteSpace: 'nowrap', borderRadius: '9999px', padding: '6px 16px', fontSize: '14px', fontWeight: 500,
            background: i === 0 ? '#059669' : '#f3f4f6', color: i === 0 ? '#fff' : '#374151',
            border: 'none', cursor: 'pointer'
          }}>{c === 'all' ? 'All' : c}</button>
        ))}
      </div>

      {/* Product grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '12px' }}>
        {products.map((p) => {
          const tone = stockTone(p.stock);
          return (
            <button key={p.id} style={{
              minHeight: '80px', display: 'flex', flexDirection: 'column', alignItems: 'flex-start', justifyContent: 'space-between',
              borderRadius: '12px', border: '1px solid #e5e7eb', background: '#fff', padding: '12px',
              textAlign: 'left', boxShadow: '0 1px 3px rgba(0,0,0,0.05)', cursor: 'pointer'
            }}>
              <div style={{ display: 'flex', width: '100%', alignItems: 'flex-start', justifyContent: 'space-between', gap: '8px' }}>
                <span style={{ fontSize: '13px', fontWeight: 600, color: '#111827', lineHeight: 1.3 }}>{p.name}</span>
                <span style={{ ...tone, borderRadius: '9999px', padding: '2px 8px', fontSize: '11px', flexShrink: 0 }}>{p.stock}</span>
              </div>
              <span style={{ marginTop: '8px', fontSize: '16px', fontWeight: 700, color: '#059669' }}>{Number(p.sell_price).toFixed(2)} SEK</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
