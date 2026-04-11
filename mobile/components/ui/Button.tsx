// File: mobile/components/ui/Button.tsx
// Purpose: Primary button component with gradient, loading, and variant support
// Used by: all screens

import React from "react";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { LinearGradient } from "expo-linear-gradient";

type Variant = "primary" | "secondary" | "ghost" | "danger";

interface ButtonProps {
  label:      string;
  onPress:    () => void;
  variant?:   Variant;
  loading?:   boolean;
  disabled?:  boolean;
  fullWidth?: boolean;
  size?:      "sm" | "md" | "lg";
  icon?:      React.ReactNode;
}

export function Button({
  label,
  onPress,
  variant   = "primary",
  loading   = false,
  disabled  = false,
  fullWidth = true,
  size      = "md",
  icon,
}: ButtonProps) {
  const isDisabled = disabled || loading;
  const heights    = { sm: 40, md: 48, lg: 54 };
  const fontSizes  = { sm: 13, md: 15, lg: 16 };
  const h          = heights[size];
  const fs         = fontSizes[size];

  const content = (
    <View style={[styles.inner, { height: h }]}>
      {loading ? (
        <ActivityIndicator
          color={variant === "primary" ? "#fff" : "#6366F1"}
          size="small"
        />
      ) : (
        <>
          {icon && <View style={styles.icon}>{icon}</View>}
          <Text
            style={[
              styles.label,
              { fontSize: fs },
              variant === "secondary" && styles.labelSecondary,
              variant === "ghost"     && styles.labelGhost,
              variant === "danger"    && styles.labelDanger,
            ]}
          >
            {label}
          </Text>
        </>
      )}
    </View>
  );

  if (variant === "primary") {
    return (
      <Pressable
        onPress={onPress}
        disabled={isDisabled}
        style={[fullWidth && styles.fullWidth, isDisabled && styles.disabled]}
      >
        <LinearGradient
          colors={["#6366F1", "#4F46E5"]}
          start={{ x: 0, y: 0 }}
          end={{ x: 1, y: 0 }}
          style={[styles.base, { borderRadius: 14 }]}
        >
          {content}
        </LinearGradient>
      </Pressable>
    );
  }

  const variantStyle = {
    secondary: styles.secondary,
    ghost:     styles.ghost,
    danger:    styles.danger,
  }[variant as "secondary" | "ghost" | "danger"];

  return (
    <Pressable
      onPress={onPress}
      disabled={isDisabled}
      style={[
        styles.base,
        styles.fullWidth,
        variantStyle,
        !fullWidth && { alignSelf: "flex-start" as const },
        isDisabled && styles.disabled,
      ]}
    >
      {content}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  base:           { borderRadius: 14, overflow: "hidden" },
  fullWidth:      { width: "100%" },
  inner:          { flexDirection: "row", alignItems: "center", justifyContent: "center", paddingHorizontal: 20 },
  icon:           { marginRight: 8 },
  label:          { color: "#fff", fontWeight: "600", letterSpacing: 0.2 },
  labelSecondary: { color: "#6366F1" },
  labelGhost:     { color: "#94A3B8" },
  labelDanger:    { color: "#EF4444" },
  secondary:      { backgroundColor: "rgba(99,102,241,0.12)", borderWidth: 1, borderColor: "rgba(99,102,241,0.3)" },
  ghost:          { backgroundColor: "rgba(255,255,255,0.06)", borderWidth: 1, borderColor: "rgba(255,255,255,0.08)" },
  danger:         { backgroundColor: "rgba(239,68,68,0.10)",  borderWidth: 1, borderColor: "rgba(239,68,68,0.25)" },
  disabled:       { opacity: 0.45 },
});
