// File: mobile/components/TabletGrid.tsx
// Purpose: Column-count-aware responsive grid used on tablet screens.
// Spec §4: phone = 1, tablet portrait = 2, tablet landscape = 3.
// Implemented on top of `FlatList`'s `numColumns` prop so we get
// virtualization for free — important for inventory screens with
// hundreds of products.

import React from "react";
import { FlatList, View, StyleSheet, type FlatListProps } from "react-native";
import { useDeviceLayout } from "@/lib/useDeviceLayout";

interface TabletGridProps<T> {
  data: readonly T[];
  renderItem: (item: T, index: number) => React.ReactElement;
  keyExtractor?: (item: T, index: number) => string;
  tabletColumns?: number;  // override for specific screens (analytics may want 2)
  phoneColumns?: number;
  contentContainerStyle?: FlatListProps<T>["contentContainerStyle"];
  ListHeaderComponent?: FlatListProps<T>["ListHeaderComponent"];
  ListEmptyComponent?: FlatListProps<T>["ListEmptyComponent"];
  refreshing?: boolean;
  onRefresh?: () => void;
}

export function TabletGrid<T>({
  data,
  renderItem,
  keyExtractor,
  tabletColumns,
  phoneColumns,
  contentContainerStyle,
  ListHeaderComponent,
  ListEmptyComponent,
  refreshing,
  onRefresh,
}: TabletGridProps<T>) {
  const { isPhone, isLandscape, columns } = useDeviceLayout();

  // Resolve the effective column count, honouring caller overrides.
  let cols = columns;
  if (isPhone && phoneColumns != null) cols = phoneColumns;
  if (!isPhone && tabletColumns != null) cols = tabletColumns;
  // Landscape callers who didn't override also get the `columns` default.
  if (!isPhone && tabletColumns == null && isLandscape) cols = 3;

  // `numColumns` cannot change on a mounted FlatList — FlatList throws
  // if we flip it at runtime (orientation change). Key the list on
  // `cols` so React remounts it when the column count changes.
  const safeKeyExtractor = keyExtractor ?? ((_: T, i: number) => String(i));

  return (
    <FlatList
      key={`grid-${cols}`}
      data={data as T[]}
      keyExtractor={safeKeyExtractor}
      numColumns={cols}
      columnWrapperStyle={cols > 1 ? styles.row : undefined}
      contentContainerStyle={[styles.container, contentContainerStyle]}
      ListHeaderComponent={ListHeaderComponent}
      ListEmptyComponent={ListEmptyComponent}
      refreshing={refreshing}
      onRefresh={onRefresh}
      renderItem={({ item, index }) => (
        <View style={cols > 1 ? styles.cell : styles.cellSingle}>
          {renderItem(item, index)}
        </View>
      )}
    />
  );
}

const styles = StyleSheet.create({
  container: { paddingHorizontal: 24, paddingVertical: 16, gap: 12 },
  row:       { gap: 12 },
  cell:      { flex: 1, minHeight: 48 },
  cellSingle:{ minHeight: 48 },
});
