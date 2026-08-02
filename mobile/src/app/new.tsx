/** New run — the canvas's intake screen: role, CV, provider price cards.
 *  Stripe opens hosted checkout in the system browser; Paystack runs inline
 *  inside a WebView (/pay). */
import { router } from "expo-router";
import * as WebBrowser from "expo-web-browser";
import { useState } from "react";
import { Pressable, ScrollView, TextInput, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { useTheme } from "@/lib/theme";
import { api } from "@/lib/api";
import { fonts, radius } from "@/lib/theme";
import { Button, Card, Sans, Serif } from "@/components/ui";

const PROVIDERS = [
  { value: "paystack", name: "Paystack", price: "₦2,000", detail: "Nigeria · cards, transfer, USSD" },
  { value: "stripe", name: "Card via Stripe", price: "$15", detail: "Everywhere else · all cards" },
] as const;

export default function NewRunScreen() {
  const t = useTheme();
  const [role, setRole] = useState("");
  const [cv, setCv] = useState("");
  const [provider, setProvider] = useState<"paystack" | "stripe">("paystack");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const submit = async () => {
    setBusy(true);
    setError("");
    try {
      const me = await api.me();
      const run = await api.createRun({
        email: me.email,
        target_role: role.trim(),
        cv_text: cv.trim(),
        provider,
      });
      if (run.provider === "stripe" && run.checkout_url) {
        await WebBrowser.openBrowserAsync(run.checkout_url);
        router.replace(`/run/${run.run_id}`);
        return;
      }
      // Pass only the run id — pay.tsx fetches authoritative checkout data from the
      // backend, so a spoofed deep link can't inject amount/reference/recipient.
      router.replace({ pathname: "/pay", params: { runId: run.run_id } });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't start the run.");
      setBusy(false);
    }
  };

  const fieldStyle = {
    borderWidth: 1,
    borderColor: t.line,
    backgroundColor: t.surface,
    borderRadius: radius.field,
    paddingHorizontal: 14,
    paddingVertical: 11,
    fontFamily: fonts.sans,
    fontSize: 13,
    color: t.ink,
  } as const;

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: t.bg }}>
      <ScrollView contentContainerStyle={{ padding: 20, paddingBottom: 40 }} keyboardShouldPersistTaps="handled">
        <Pressable onPress={() => router.back()} style={{ marginBottom: 8 }}>
          <Sans size={13} color={t.muted}>
            ‹ Back
          </Sans>
        </Pressable>
        <Serif size={30}>Start a run.</Serif>
        <Sans size={12} color={t.muted} style={{ marginTop: 8, marginBottom: 20 }}>
          One payment. Ada rewrites your CV, finds your best-fit jobs, and preps your
          interview — in minutes.
        </Sans>

        <Sans size={12} weight="medium" style={{ marginBottom: 6 }}>
          Target role
        </Sans>
        <TextInput
          value={role}
          onChangeText={setRole}
          placeholder="e.g. Sales Manager, Registered Nurse, Accountant"
          placeholderTextColor={`${t.muted}99`}
          style={[fieldStyle, { marginBottom: 16 }]}
        />
        <Sans size={12} weight="medium" style={{ marginBottom: 6 }}>
          Your current CV
        </Sans>
        <TextInput
          value={cv}
          onChangeText={setCv}
          placeholder="Paste your CV — rough is fine, Ada does the polishing."
          placeholderTextColor={`${t.muted}99`}
          multiline
          style={[fieldStyle, { minHeight: 130, textAlignVertical: "top", marginBottom: 16 }]}
        />

        <Sans size={12} weight="medium" style={{ marginBottom: 8 }}>
          Pay with
        </Sans>
        <View style={{ flexDirection: "row", gap: 8, marginBottom: 20 }}>
          {PROVIDERS.map((p) => {
            const selected = provider === p.value;
            return (
              <Pressable
                key={p.value}
                onPress={() => setProvider(p.value)}
                style={{
                  flex: 1,
                  borderWidth: 1,
                  borderColor: selected ? t.accent : t.line,
                  backgroundColor: selected ? t.accentSoft : t.surface,
                  borderRadius: radius.field,
                  padding: 13,
                }}
              >
                <Sans size={12} weight="medium" color={selected ? t.accent : t.ink}>
                  {p.name}
                </Sans>
                <Serif size={20} style={{ marginTop: 3 }}>
                  {p.price}
                </Serif>
                <Sans size={10} color={t.muted} style={{ marginTop: 3 }}>
                  {p.detail}
                </Sans>
              </Pressable>
            );
          })}
        </View>

        {error ? (
          <Sans size={12} color={t.danger} style={{ marginBottom: 12 }}>
            {error}
          </Sans>
        ) : null}
        <Button
          label="Run Ada →"
          loading={busy}
          disabled={role.trim().length < 2 || cv.trim().length < 30}
          onPress={submit}
        />
        <Sans size={10} color={t.muted} style={{ textAlign: "center", marginTop: 8 }}>
          Payment unlocks the run. Failed runs are never charged.
        </Sans>
      </ScrollView>
    </SafeAreaView>
  );
}
