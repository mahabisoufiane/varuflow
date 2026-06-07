const POS_STRINGS = {
  search_placeholder: "Search products or scan barcode...",
  category_all: "All",
  payment_cash: "Cash",
  payment_card: "Card",
  payment_swish: "Swish",
  customer_search: "Search customer...",
  cart_empty: "Cart is empty",
  discount: "Discount",
  subtotal: "Subtotal",
  vat: "VAT (25%)",
  total: "Total",
  cash_tendered: "Cash tendered",
  change_due: "Change due",
  complete_sale: "Complete Sale  F2",
  opening_float: "Opening float (SEK)",
  open_session: "Open Session",
  close_session: "Close Session",
  z_report_title: "End of Day — Z-Report",
  z_report_download: "Download PDF",
  confirm_close: "Confirm & Close",
  counted_cash: "Counted cash (SEK)",
  cash_variance: "Variance",
  refund_confirm: "Mark this sale as refunded?",
  refund_success: "Sale refunded",
  refund: "Refund",
  receipt_print: "Print",
  receipt_email: "Email",
  new_sale: "New Sale",
  line_discount: "Line discount",
  quick_buttons_manage: "Manage shortcuts",
  quick_buttons_add_first: "Add shortcut",
  quick_buttons_add: "Add new shortcut",
  quick_buttons_label: "Button label",
  quick_buttons_color: "Color",
  quick_buttons_save: "Save",
  keyboard_shortcuts: "Keyboard shortcuts",
} as const;

export type PosStringKey = keyof typeof POS_STRINGS;

export function usePosT() {
  return (key: PosStringKey) => POS_STRINGS[key];
}
