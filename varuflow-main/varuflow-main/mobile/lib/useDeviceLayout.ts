// File: mobile/lib/useDeviceLayout.ts
// Purpose: Single source of truth for "is this a tablet?" classification
// across the Expo app. Item 13 introduces a tablet-optimised shell
// (sidebar + 3-column grids) so screens and the root layout need a
// cheap, reactive hook that re-renders on orientation changes.
//
// Why no `expo-device`?  The heuristic in the spec collapses to
// `width >= 768` once you OR in the DeviceType.TABLET branch, which
// means on every real iPad / Android tablet we'd still end up taking
// the `true` branch via the width check alone. Skipping the native
// module keeps the bundle lean (spec §14: "Do not add heavy new
// dependencies unless absolutely necessary") and keeps the hook a pure
// function of window dimensions — so split/fold events flip the layout
// without any native callback plumbing.

import { useWindowDimensions } from "react-native";

export interface DeviceLayout {
  isPhone: boolean;
  isTablet: boolean;
  isLandscape: boolean;
  screenWidth: number;
  screenHeight: number;
  /** 1 on phones, 2 on tablet portrait, 3 on tablet landscape. */
  columns: number;
}

/** Width at which the layout flips from phone to tablet (iPad Mini / 10" Android). */
export const TABLET_BREAKPOINT_PX = 768;

export function useDeviceLayout(): DeviceLayout {
  const { width, height } = useWindowDimensions();
  const isLandscape = width > height;
  const isTablet = width >= TABLET_BREAKPOINT_PX;
  const isPhone = !isTablet;
  const columns = isPhone ? 1 : isLandscape ? 3 : 2;
  return {
    isPhone,
    isTablet,
    isLandscape,
    screenWidth: width,
    screenHeight: height,
    columns,
  };
}

/** Pure helper — exported for unit tests. Mirrors the `columns` logic above.
 *  Zero dependencies on React so a node --test can call it directly. */
export function columnsFor(width: number, height: number): number {
  const isTablet = width >= TABLET_BREAKPOINT_PX;
  if (!isTablet) return 1;
  return width > height ? 3 : 2;
}
