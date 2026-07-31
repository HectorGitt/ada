import { router, useFocusEffect } from "expo-router";
import { useCallback, useState } from "react";
import { Pressable, ScrollView, TextInput, View } from "react-native";

import { Button, Card, Eyebrow, Sans, Serif, Skeleton, StatusBadge } from "@/components/ui";
import { api, type Outcome, type OutcomeStage, type Pipeline } from "@/lib/api";
import { fonts, radius, useTheme } from "@/lib/theme";

const STAGES: { key: OutcomeStage; label: string; short: string }[] = [
  { key: "applied", label: "Applied", short: "Applied" },
  { key: "interviewing", label: "Interviewing", short: "Interview" },
  { key: "offer", label: "Offer", short: "Offer" },
  { key: "hired", label: "Hired", short: "Hired" },
  { key: "rejected", label: "Rejected", short: "Rejected" },
];

const TONE: Record<OutcomeStage, "neutral" | "accent" | "warn" | "success" | "danger"> = {
  applied: "neutral",
  interviewing: "accent",
  offer: "warn",
  hired: "success",
  rejected: "danger",
};
const LABEL: Record<OutcomeStage, string> = {
  applied: "Applied",
  interviewing: "Interviewing",
  offer: "Offer",
  hired: "Hired",
  rejected: "Rejected",
};

export default function PipelineScreen() {
  const t = useTheme();
  const [data, setData] = useState<Pipeline | null>(null);
  const [adding, setAdding] = useState(false);
  const [company, setCompany] = useState("");
  const [role, setRole] = useState("");

  const load = useCallback(() => {
    api.getPipeline().then(setData).catch(() => setData({ outcomes: [], funnel: {} }));
  }, []);
  useFocusEffect(load);

  const advance = async (o: Outcome, stage: OutcomeStage) => {
    if (!data || stage === o.stage) return;
    const prev = data;
    setData({ ...data, outcomes: data.outcomes.map((x) => (x.id === o.id ? { ...x, stage } : x)) });
    try {
      await api.advanceOutcome(o.id, stage);
      setData(await api.getPipeline());
    } catch {
      setData(prev);
    }
  };

  const add = async () => {
    if (!company.trim() || !role.trim()) return;
    await api.addOutcome(company.trim(), role.trim(), "applied").catch(() => {});
    setCompany("");
    setRole("");
    setAdding(false);
    load();
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

  const funnel = data?.funnel ?? {};
  const hired = funnel.hired ?? 0;

  return (
    <ScrollView
      style={{ flex: 1, backgroundColor: t.bg }}
      contentContainerStyle={{ padding: 20, paddingBottom: 140 }}
      keyboardShouldPersistTaps="handled"
    >
      <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
        <Serif size={30}>Pipeline.</Serif>
        <Button
          label={adding ? "Close" : "＋ Add"}
          variant="secondary"
          style={{ paddingVertical: 9, paddingHorizontal: 14 }}
          onPress={() => setAdding((v) => !v)}
        />
      </View>
      <Sans color={t.muted} style={{ marginBottom: 18 }}>
        Every role you&apos;re chasing, and where it stands. Ada logs each apply; you move it
        forward.
      </Sans>

      {/* Funnel summary */}
      <Card style={{ flexDirection: "row", gap: 8, marginBottom: 14 }} pad={12}>
        {STAGES.slice(0, 4).map((s) => (
          <View
            key={s.key}
            style={{ flex: 1, backgroundColor: t.surface2, borderRadius: 12, paddingVertical: 10, alignItems: "center" }}
          >
            <Serif size={22}>{funnel[s.key] ?? 0}</Serif>
            <Eyebrow style={{ marginTop: 2, fontSize: 8.5 }}>{s.short}</Eyebrow>
          </View>
        ))}
      </Card>

      {adding && (
        <Card style={{ marginBottom: 14, gap: 10 }}>
          <TextInput
            value={company}
            onChangeText={setCompany}
            placeholder="Company"
            placeholderTextColor={`${t.muted}99`}
            style={fieldStyle}
          />
          <TextInput
            value={role}
            onChangeText={setRole}
            placeholder="Role"
            placeholderTextColor={`${t.muted}99`}
            style={fieldStyle}
          />
          <Button label="Track it" onPress={add} />
        </Card>
      )}

      {data === null ? (
        <View style={{ gap: 10 }}>
          {[0, 1].map((i) => (
            <Card key={i}>
              <Skeleton width="60%" height={16} />
              <Skeleton width={100} height={12} style={{ marginTop: 8 }} />
            </Card>
          ))}
        </View>
      ) : data.outcomes.length === 0 ? (
        <Card style={{ alignItems: "center", paddingVertical: 36 }}>
          <Serif size={20}>Nothing tracked yet</Serif>
          <Sans color={t.muted} style={{ marginTop: 6, textAlign: "center" }}>
            When Ada applies for you it shows up here — or add a role you&apos;re chasing
            elsewhere.
          </Sans>
        </Card>
      ) : (
        <View style={{ gap: 10 }}>
          {data.outcomes.map((o) => (
            <Card key={o.id} style={{ gap: 10 }}>
              <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "flex-start", gap: 10 }}>
                <View style={{ flexShrink: 1 }}>
                  <Sans size={14} weight="medium" numberOfLines={1}>
                    {o.role_title}
                  </Sans>
                  <Sans size={12} color={t.muted} numberOfLines={1} style={{ marginTop: 2 }}>
                    {o.company}
                  </Sans>
                </View>
                <StatusBadge tone={TONE[o.stage]} label={LABEL[o.stage]} />
              </View>
              <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 6 }}>
                {STAGES.map((s) => {
                  const active = s.key === o.stage;
                  return (
                    <Pressable
                      key={s.key}
                      onPress={() => advance(o, s.key)}
                      style={{
                        paddingHorizontal: 10,
                        paddingVertical: 6,
                        borderRadius: radius.pill,
                        borderWidth: 1,
                        borderColor: active ? t.accent : t.line,
                        backgroundColor: active ? t.accent : "transparent",
                      }}
                    >
                      <Sans size={11} weight="medium" color={active ? t.accentInk : t.muted}>
                        {s.short}
                      </Sans>
                    </Pressable>
                  );
                })}
              </View>
            </Card>
          ))}
        </View>
      )}

      {hired > 0 && (
        <Sans color={t.success} weight="medium" style={{ marginTop: 16, textAlign: "center" }}>
          🎉 {hired} hire{hired > 1 ? "s" : ""} tracked. That&apos;s the whole point.
        </Sans>
      )}

      <Pressable onPress={() => router.back()} style={{ marginTop: 20, alignItems: "center" }}>
        <Sans color={t.muted}>← Back</Sans>
      </Pressable>
    </ScrollView>
  );
}
