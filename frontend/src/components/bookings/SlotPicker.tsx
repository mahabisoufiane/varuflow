"use client";

/**
 * SlotPicker — tiny preview of the available-slots endpoint.
 *
 * Renders as a placeholder until staff + service are chosen. A later
 * item will add the dropdowns and the fetch call; for now this lets
 * the page compile and the layout lock in.
 */
export default function SlotPicker() {
  return (
    <div className="text-sm text-gray-500">
      Select a service and staff member to see available slots.
    </div>
  );
}
