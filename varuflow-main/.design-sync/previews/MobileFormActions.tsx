import { MobileFormActions } from 'varuflow-ui';

export function PrimaryOnly() {
  return (
    <div style={{ position: 'relative', width: 380, height: 80 }}>
      <MobileFormActions primaryLabel="Save changes" primaryType="button" />
    </div>
  );
}

export function WithSecondary() {
  return (
    <div style={{ position: 'relative', width: 380, height: 80 }}>
      <MobileFormActions
        primaryLabel="Save invoice"
        primaryType="button"
        secondaryLabel="Discard"
      />
    </div>
  );
}

export function WithDestructive() {
  return (
    <div style={{ position: 'relative', width: 380, height: 80 }}>
      <MobileFormActions
        primaryLabel="Confirm"
        primaryType="button"
        secondaryLabel="Cancel"
        destructiveLabel="Delete"
      />
    </div>
  );
}

export function LoadingState() {
  return (
    <div style={{ position: 'relative', width: 380, height: 80 }}>
      <MobileFormActions primaryLabel="Saving…" primaryType="button" primaryLoading primaryDisabled />
    </div>
  );
}
