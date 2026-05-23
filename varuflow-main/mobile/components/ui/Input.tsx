// File: mobile/components/ui/Input.tsx
// Purpose: Styled text input with label, error state, and password toggle
// Used by: login, signup screens

import React, { useState } from "react";
import {
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  TextInputProps,
  View,
} from "react-native";

interface InputProps extends TextInputProps {
  label?:        string;
  error?:        string;
  isPassword?:   boolean;
}

export function Input({ label, error, isPassword, style, ...props }: InputProps) {
  const [showPw, setShowPw] = useState(false);

  return (
    <View style={styles.wrapper}>
      {label && <Text style={styles.label}>{label}</Text>}
      <View style={[styles.inputWrapper, error ? styles.inputError : styles.inputNormal]}>
        <TextInput
          style={[styles.input, style]}
          placeholderTextColor="#475569"
          secureTextEntry={isPassword && !showPw}
          autoCapitalize="none"
          {...props}
        />
        {isPassword && (
          <Pressable onPress={() => setShowPw((v) => !v)} style={styles.eyeBtn} hitSlop={8}>
            <Text style={styles.eyeIcon}>{showPw ? "🙈" : "👁"}</Text>
          </Pressable>
        )}
      </View>
      {error && <Text style={styles.errorText}>{error}</Text>}
    </View>
  );
}

const styles = StyleSheet.create({
  wrapper:      { marginBottom: 4 },
  label:        { fontSize: 12, fontWeight: "500", color: "#94A3B8", marginBottom: 6 },
  inputWrapper: { flexDirection: "row", alignItems: "center", borderRadius: 12, borderWidth: 1 },
  inputNormal:  { backgroundColor: "rgba(255,255,255,0.05)", borderColor: "rgba(255,255,255,0.1)" },
  inputError:   { backgroundColor: "rgba(239,68,68,0.07)",   borderColor: "rgba(239,68,68,0.5)" },
  input:        { flex: 1, height: 48, paddingHorizontal: 14, fontSize: 15, color: "#F8FAFC" },
  eyeBtn:       { paddingHorizontal: 14 },
  eyeIcon:      { fontSize: 16 },
  errorText:    { fontSize: 11, color: "#EF4444", marginTop: 4, marginLeft: 2 },
});
