import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter, DialogClose } from 'varuflow-ui';

export function ConfirmDelete() {
  return (
    <div style={{ padding: '24px', minHeight: '300px', position: 'relative' }}>
      <Dialog open>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Invoice #INV-2024-087?</DialogTitle>
            <DialogDescription>
              This action cannot be undone. The invoice will be permanently removed from your records and the customer will not be notified.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <DialogClose asChild>
              <button style={{ padding: '8px 16px', borderRadius: '6px', border: '1px solid #e2e8f0', background: 'white', cursor: 'pointer', fontSize: '14px' }}>Cancel</button>
            </DialogClose>
            <button style={{ padding: '8px 16px', borderRadius: '6px', background: '#dc2626', color: 'white', border: 'none', cursor: 'pointer', fontSize: '14px' }}>Delete</button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export function EditCustomer() {
  return (
    <div style={{ padding: '24px', minHeight: '400px', position: 'relative' }}>
      <Dialog open>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit Customer</DialogTitle>
            <DialogDescription>
              Update the customer details below. Changes are saved immediately.
            </DialogDescription>
          </DialogHeader>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', padding: '4px 0' }}>
            <div>
              <label style={{ fontSize: '12px', fontWeight: 600, textTransform: 'uppercase', color: '#64748b', letterSpacing: '0.05em', display: 'block', marginBottom: '4px' }}>Full name</label>
              <input defaultValue="Anna Lindström" style={{ width: '100%', padding: '10px 12px', borderRadius: '8px', border: '1px solid #e2e8f0', fontSize: '14px', boxSizing: 'border-box' }} />
            </div>
            <div>
              <label style={{ fontSize: '12px', fontWeight: 600, textTransform: 'uppercase', color: '#64748b', letterSpacing: '0.05em', display: 'block', marginBottom: '4px' }}>Email</label>
              <input defaultValue="anna@example.se" style={{ width: '100%', padding: '10px 12px', borderRadius: '8px', border: '1px solid #e2e8f0', fontSize: '14px', boxSizing: 'border-box' }} />
            </div>
          </div>
          <DialogFooter>
            <DialogClose asChild>
              <button style={{ padding: '8px 16px', borderRadius: '6px', border: '1px solid #e2e8f0', background: 'white', cursor: 'pointer', fontSize: '14px' }}>Cancel</button>
            </DialogClose>
            <button style={{ padding: '8px 16px', borderRadius: '6px', background: '#2563eb', color: 'white', border: 'none', cursor: 'pointer', fontSize: '14px' }}>Save changes</button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
