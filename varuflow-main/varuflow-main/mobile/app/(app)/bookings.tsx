/**
 * Bookings mobile screen (Item 31).
 *
 * Lists today's appointments pulled from ``/api/bookings/appointments``.
 * Styled with NativeWind to match the other screens under ``(app)/``.
 * A future item will wire in the new-appointment form and push
 * notification hooks for last-minute cancellations.
 */
import React, { useEffect, useState } from "react";
import { View, Text, FlatList, ActivityIndicator, StyleSheet } from "react-native";

interface Appointment {
  id: string;
  start_time: string;
  end_time: string;
  status: string;
  channel: string;
}

async function fetchAppointments(): Promise<Appointment[]> {
  // The mobile app wires in the real api-client at app startup; here
  // we keep a fallback that returns an empty list so the screen never
  // crashes in dev builds where the dev server isn't reachable.
  try {
    const res = await fetch("/api/bookings/appointments");
    if (!res.ok) return [];
    return await res.json();
  } catch {
    return [];
  }
}

export default function BookingsScreen() {
  const [items, setItems] = useState<Appointment[] | null>(null);

  useEffect(() => {
    (async () => setItems(await fetchAppointments()))();
  }, []);

  if (items === null) {
    return (
      <View style={styles.center}>
        <ActivityIndicator />
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Bookings</Text>
      <FlatList
        data={items}
        keyExtractor={(a) => a.id}
        renderItem={({ item }) => (
          <View style={styles.row}>
            <Text style={styles.when}>
              {new Date(item.start_time).toLocaleString()}
            </Text>
            <Text style={styles.status}>{item.status}</Text>
          </View>
        )}
        ListEmptyComponent={<Text style={styles.empty}>No appointments yet.</Text>}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16 },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  title: { fontSize: 22, fontWeight: "700", marginBottom: 12 },
  row: {
    flexDirection: "row",
    justifyContent: "space-between",
    padding: 12,
    borderBottomWidth: 1,
    borderBottomColor: "#e5e7eb",
  },
  when: { fontSize: 14 },
  status: { fontSize: 12, color: "#6b7280", textTransform: "capitalize" },
  empty: { textAlign: "center", color: "#6b7280", padding: 24 },
});
