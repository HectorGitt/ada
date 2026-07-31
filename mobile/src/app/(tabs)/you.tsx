import { router } from "expo-router";
import { useEffect, useState } from "react";
import { Pressable, ScrollView, TextInput, View } from "react-native";

import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";
import { fonts, radius, useTheme } from "@/lib/theme";
import { Button, Card, Eyebrow, Sans, Serif } from "@/components/ui";

export default function YouScreen() {
  const t = useTheme();
  const { email } = useAuth();
  const [profileText, setProfileText] = useState("");
  const [linkedinUrl, setLinkedinUrl] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    api
      .getProfile()
      .then((p) => {
        if (p) {
          setProfileText(p.profile_text);
          setLinkedinUrl(p.linkedin_url ?? "");
        }
      })
      .catch(() => {});
  }, []);

  const save = async () => {
    setSaving(true);
    try {
      await api.putProfile({ profile_text: profileText, linkedin_url: linkedinUrl || null });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch {
      /* surfaced via button state only */
    } finally {
      setSaving(false);
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
    <ScrollView
      style={{ flex: 1, backgroundColor: t.bg }}
      contentContainerStyle={{ padding: 20, paddingBottom: 140 }}
      keyboardShouldPersistTaps="handled"
    >
      <Serif size={30} style={{ marginBottom: 6 }}>
        Profile.
      </Serif>
      <Sans color={t.muted} style={{ marginBottom: 20 }}>
        The more Ada knows about your background, the sharper her advice, rewrites, and
        matches get.
      </Sans>

      <Card style={{ marginBottom: 14, gap: 12 }}>
        <View>
          <Sans size={12} weight="medium" style={{ marginBottom: 6 }}>
            LinkedIn URL
          </Sans>
          <TextInput
            value={linkedinUrl}
            onChangeText={setLinkedinUrl}
            placeholder="https://linkedin.com/in/you"
            placeholderTextColor={`${t.muted}99`}
            autoCapitalize="none"
            style={fieldStyle}
          />
        </View>
        <View>
          <Sans size={12} weight="medium" style={{ marginBottom: 6 }}>
            Your career background
          </Sans>
          <TextInput
            value={profileText}
            onChangeText={setProfileText}
            placeholder="Paste your LinkedIn profile export, or write your background: roles, achievements, skills, education."
            placeholderTextColor={`${t.muted}99`}
            multiline
            style={[fieldStyle, { minHeight: 160, textAlignVertical: "top" }]}
          />
        </View>
        <Button label={saved ? "Saved ✓" : "Save profile"} loading={saving} onPress={save} />
      </Card>

      <Pressable onPress={() => router.push("/pipeline")}>
        <Card style={{ marginBottom: 14, flexDirection: "row", alignItems: "center", justifyContent: "space-between" }}>
          <View style={{ flexShrink: 1, paddingRight: 10 }}>
            <Sans size={13} weight="medium">
              Your pipeline
            </Sans>
            <Eyebrow style={{ marginTop: 3, textTransform: "none", letterSpacing: 0 }}>
              Track every role from applied to hired
            </Eyebrow>
          </View>
          <Sans size={18} color={t.muted}>
            ›
          </Sans>
        </Card>
      </Pressable>

      <Card style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between" }}>
        <View style={{ flexShrink: 1, paddingRight: 10 }}>
          <Sans size={13} weight="medium" numberOfLines={1}>
            {email}
          </Sans>
          <Eyebrow style={{ marginTop: 3, textTransform: "none", letterSpacing: 0 }}>
            Signed in with email and password
          </Eyebrow>
        </View>
        <Button
          label="Sign out"
          variant="secondary"
          style={{ paddingVertical: 9, paddingHorizontal: 14 }}
          onPress={async () => {
            await api.logout().catch(() => {});
            router.replace("/login");
          }}
        />
      </Card>
    </ScrollView>
  );
}
