/**
 * LoyaltyCard fetches API data on mount. We render a static replica
 * of its loaded state to demonstrate the UI chrome.
 */
import { Trophy } from 'lucide-react';

function TierBadge({ tier }: { tier: string }) {
  const styles: Record<string, { bg: string; color: string }> = {
    platinum: { bg: '#334155', color: '#f1f5f9' },
    gold: { bg: '#f59e0b', color: '#451a03' },
    silver: { bg: '#d1d5db', color: '#111827' },
    bronze: { bg: '#b45309', color: '#fef3c7' },
  };
  const s = styles[tier] ?? styles.bronze;
  return (
    <span style={{
      background: s.bg, color: s.color,
      borderRadius: '9999px', padding: '4px 12px',
      fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em'
    }}>
      {tier}
    </span>
  );
}

function LoyaltyCardStatic({ tier, balance, lifetime, toNext, nextTier }: {
  tier: string; balance: number; lifetime: number; toNext?: number; nextTier?: string;
}) {
  return (
    <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: '12px', padding: '20px', maxWidth: '360px', fontFamily: 'system-ui, sans-serif' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
        <Trophy style={{ width: 20, height: 20, color: '#6366f1' }} />
        <span style={{ fontSize: '15px', fontWeight: 500, color: '#111827' }}>Loyalty</span>
        <div style={{ marginLeft: 'auto' }}>
          <TierBadge tier={tier} />
        </div>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', fontSize: '14px' }}>
        <div>
          <div style={{ fontSize: '12px', color: '#9ca3af', marginBottom: '2px' }}>Balance</div>
          <div style={{ fontSize: '28px', fontWeight: 600, color: '#111827', fontVariantNumeric: 'tabular-nums' }}>{balance.toLocaleString()}</div>
        </div>
        <div>
          <div style={{ fontSize: '12px', color: '#9ca3af', marginBottom: '2px' }}>Lifetime</div>
          <div style={{ fontSize: '28px', fontWeight: 600, color: '#111827', fontVariantNumeric: 'tabular-nums' }}>{lifetime.toLocaleString()}</div>
        </div>
      </div>
      {toNext && nextTier && (
        <div style={{ marginTop: '16px', fontSize: '12px', color: '#9ca3af' }}>
          {toNext.toLocaleString()} points to {nextTier}
        </div>
      )}
    </div>
  );
}

export function GoldMember() {
  return (
    <div style={{ padding: '16px' }}>
      <LoyaltyCardStatic tier="gold" balance={3_240} lifetime={12_880} toNext={2_120} nextTier="platinum" />
    </div>
  );
}

export function BronzeMember() {
  return (
    <div style={{ padding: '16px' }}>
      <LoyaltyCardStatic tier="bronze" balance={420} lifetime={840} toNext={660} nextTier="silver" />
    </div>
  );
}

export function PlatinumMember() {
  return (
    <div style={{ padding: '16px' }}>
      <LoyaltyCardStatic tier="platinum" balance={15_200} lifetime={55_400} />
    </div>
  );
}
