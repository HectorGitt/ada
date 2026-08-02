/** Ask Ada — streaming coach chat, per the canvas: grounded badge, user
 *  bubbles with accent shadow, Ada monogram replies, mic in the composer. */
import { router, useLocalSearchParams } from "expo-router";
import { useEffect, useRef, useState } from "react";
import {
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  TextInput,
  View,
} from "react-native";
import Svg, { Path } from "react-native-svg";

import { api, streamChat, type ChatMessage } from "@/lib/api";
import { fonts, radius, useTheme } from "@/lib/theme";
import { AdaMark, Sans, Serif } from "@/components/ui";

const SUGGESTIONS = [
  "Review my career trajectory",
  "What roles should I target next?",
  "How do I switch industries without starting over?",
  "Help me plan a salary negotiation",
];

export default function AskScreen() {
  const t = useTheme();
  const { q } = useLocalSearchParams<{ q?: string }>();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [runsCount, setRunsCount] = useState<number | null>(null);
  const abortRef = useRef<(() => void) | null>(null);
  const scrollRef = useRef<ScrollView>(null);

  useEffect(() => {
    api
      .listRuns()
      .then((rs) => setRunsCount(rs.filter((r) => r.status === "complete").length))
      .catch(() => {});
  }, []);

  const send = (text: string) => {
    const content = text.trim();
    if (!content || streaming) return;
    setInput("");
    const history: ChatMessage[] = [...messages, { role: "user", content }];
    setMessages([...history, { role: "assistant", content: "" }]);
    setStreaming(true);
    const { done, abort } = streamChat(history, (delta) =>
      setMessages((prev) => {
        const next = [...prev];
        const last = next.length - 1;
        next[last] = { role: "assistant", content: next[last].content + delta };
        return next;
      }),
    );
    abortRef.current = abort;
    done
      .catch(() =>
        setMessages((prev) => {
          const next = [...prev];
          const last = next.length - 1;
          if (!next[last].content)
            next[last] = { role: "assistant", content: "Something interrupted me — ask that again?" };
          return next;
        }),
      )
      .finally(() => setStreaming(false));
  };

  // A question handed over from Home's "Ask Ada anything" pill.
  const handed = useRef(false);
  useEffect(() => {
    if (q && !handed.current) {
      handed.current = true;
      send(q);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q]);

  useEffect(() => {
    const id = setTimeout(() => scrollRef.current?.scrollToEnd({ animated: true }), 80);
    return () => clearTimeout(id);
  }, [messages]);

  const empty = messages.length === 0;

  return (
    <KeyboardAvoidingView
      style={{ flex: 1, backgroundColor: t.bg }}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
    >
      <View
        style={{
          flexDirection: "row",
          justifyContent: "space-between",
          alignItems: "baseline",
          paddingHorizontal: 20,
          paddingTop: 8,
          paddingBottom: 12,
          borderBottomWidth: 1,
          borderBottomColor: t.line,
        }}
      >
        <Serif size={24}>Ask Ada.</Serif>
        <View style={{ flexDirection: "row", alignItems: "center", gap: 5 }}>
          <View style={{ width: 5, height: 5, borderRadius: 3, backgroundColor: t.success }} />
          <Sans size={10} color={t.muted}>
            {runsCount ? `Grounded in ${runsCount} ${runsCount === 1 ? "run" : "runs"}` : "Grounded in your profile"}
          </Sans>
        </View>
      </View>

      <ScrollView
        ref={scrollRef}
        style={{ flex: 1 }}
        contentContainerStyle={{ padding: 20, gap: 16, flexGrow: 1 }}
        keyboardShouldPersistTaps="handled"
      >
        {empty && (
          <View style={{ flex: 1, alignItems: "center", justifyContent: "center", gap: 8 }}>
            <Serif size={30} style={{ textAlign: "center" }}>
              What&apos;s on your mind?
            </Serif>
            <Sans color={t.muted} style={{ textAlign: "center", maxWidth: 280 }}>
              Career advice grounded in your profile and your runs — not generic tips.
            </Sans>
            <View style={{ flexDirection: "row", flexWrap: "wrap", justifyContent: "center", gap: 8, marginTop: 16 }}>
              {SUGGESTIONS.map((s) => (
                <Pressable
                  key={s}
                  onPress={() => send(s)}
                  style={{
                    borderWidth: 1,
                    borderColor: t.line,
                    backgroundColor: t.surface,
                    borderRadius: radius.pill,
                    paddingHorizontal: 13,
                    paddingVertical: 7,
                  }}
                >
                  <Sans size={11} weight="medium" color={t.accent}>
                    {s}
                  </Sans>
                </Pressable>
              ))}
            </View>
          </View>
        )}
        {messages.map((m, i) =>
          m.role === "user" ? (
            <View key={i} style={{ alignItems: "flex-end" }}>
              <View
                style={{
                  maxWidth: "85%",
                  backgroundColor: t.accent,
                  borderRadius: 18,
                  borderBottomRightRadius: 6,
                  paddingHorizontal: 15,
                  paddingVertical: 10,
                  shadowColor: t.accent,
                  shadowOpacity: 0.2,
                  shadowRadius: 8,
                  shadowOffset: { width: 0, height: 2 },
                  elevation: 3,
                }}
              >
                <Sans size={13} color={t.accentInk}>
                  {m.content}
                </Sans>
              </View>
            </View>
          ) : (
            <View key={i} style={{ flexDirection: "row", gap: 10 }}>
              <AdaMark />
              <View style={{ flex: 1, paddingTop: 2 }}>
                {m.content ? (
                  <Sans size={13}>{m.content}</Sans>
                ) : (
                  <Sans size={13} color={t.muted}>
                    Ada is thinking…
                  </Sans>
                )}
              </View>
            </View>
          ),
        )}
      </ScrollView>

      {/* Composer */}
      <View style={{ paddingHorizontal: 16, paddingBottom: 110, paddingTop: 8 }}>
        <View
          style={{
            flexDirection: "row",
            alignItems: "center",
            gap: 6,
            backgroundColor: t.surface,
            borderWidth: 1,
            borderColor: t.line,
            borderRadius: 26,
            paddingLeft: 16,
            paddingRight: 8,
            paddingVertical: 8,
          }}
        >
          <TextInput
            value={input}
            onChangeText={setInput}
            placeholder="Ask Ada anything…"
            placeholderTextColor={`${t.muted}b0`}
            style={{ flex: 1, fontFamily: fonts.sans, fontSize: 13, color: t.ink, paddingVertical: 2 }}
            onSubmitEditing={() => send(input)}
          />
          <Pressable
            onPress={() => router.push("/voice")}
            accessibilityLabel="Talk to Ada"
            style={{ width: 32, height: 32, alignItems: "center", justifyContent: "center" }}
          >
            <Svg width={16} height={16} viewBox="0 0 24 24" fill="none" stroke={t.muted} strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round">
              <Path d="M12 2a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z" />
              <Path d="M19 10v1a7 7 0 0 1-14 0v-1M12 18v4" />
            </Svg>
          </Pressable>
          <Pressable
            onPress={() => (streaming ? abortRef.current?.() : send(input))}
            style={{
              width: 34,
              height: 34,
              borderRadius: 17,
              backgroundColor: streaming ? t.ink : t.accent,
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            {streaming ? (
              <View style={{ width: 11, height: 11, borderRadius: 2, backgroundColor: t.bg }} />
            ) : (
              <Svg width={15} height={15} viewBox="0 0 24 24" fill="none" stroke={t.accentInk} strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round">
                <Path d="M12 19V5M5 12l7-7 7 7" />
              </Svg>
            )}
          </Pressable>
        </View>
      </View>
    </KeyboardAvoidingView>
  );
}
