import React from 'react';

// ScrollReveal wraps children with GSAP ScrollTrigger animation. The GSAP
// `from { opacity: 0 }` start-state fires immediately on mount, making content
// invisible in a static screenshot. We replicate the wrapper div and show
// children at full opacity to demonstrate the layout and content.

export function WithSingleBlock() {
  return (
    <div style={{ padding: '24px', background: '#0d1526', borderRadius: '12px' }}>
      {/* Simulates the ScrollReveal wrapper div — children shown at full opacity */}
      <div>
        <div
          style={{
            padding: '24px',
            borderRadius: '12px',
            border: '1px solid rgba(255,255,255,0.1)',
            background: 'rgba(255,255,255,0.05)',
          }}
        >
          <h3 style={{ color: '#f1f5f9', fontSize: '18px', fontWeight: 600, margin: '0 0 8px' }}>
            Scroll reveal section
          </h3>
          <p style={{ color: '#94a3b8', fontSize: '14px', margin: 0 }}>
            This block fades up into view as it enters the viewport. The animation
            respects prefers-reduced-motion and degrades gracefully to no animation.
          </p>
        </div>
      </div>
    </div>
  );
}

export function WithStaggeredChildren() {
  const items = [
    { title: 'Feature one', desc: 'Staggered child, appears first.' },
    { title: 'Feature two', desc: 'Staggered child, appears 80 ms later.' },
    { title: 'Feature three', desc: 'Staggered child, appears 160 ms later.' },
  ];
  return (
    <div style={{ padding: '24px', background: '#0d1526', borderRadius: '12px' }}>
      {/* Simulates the ScrollReveal wrapper with stagger=true — static view */}
      <div>
        {items.map((item, i) => (
          <div
            key={i}
            style={{
              padding: '16px',
              borderRadius: '10px',
              border: '1px solid rgba(255,255,255,0.1)',
              background: 'rgba(255,255,255,0.04)',
              marginBottom: i < items.length - 1 ? '10px' : 0,
            }}
          >
            <p style={{ color: '#e2e8f0', fontSize: '14px', fontWeight: 600, margin: '0 0 4px' }}>{item.title}</p>
            <p style={{ color: '#94a3b8', fontSize: '13px', margin: 0 }}>{item.desc}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
