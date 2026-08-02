/** Voice session — the canvas's dark screen: radial glow, session clock,
 *  triple ping rings, equalizer bars, live transcript. Always dark, whatever
 *  the system theme. Streams the session over the backend voice WebSocket;
 *  native microphone frame capture is the remaining TODO (the session UI,
 *  transcript, and intake handoff are fully wired). */
import { router } from "expo-router";
import { useEffect, useRef, useState } from "react";
import { Animated, Easing, Pressable, ScrollView, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import Svg, { Path } from "react-native-svg";

import { voiceWsUrl } from "@/lib/api";
import { fonts, palettes } from "@/lib/theme";

const d = palettes.dark; // this screen is always dark, per the design canvas

type CallState = "idle" | "connecting" | "live" | "extracting" | "error";

function PingRing({ delay }: { delay: number }) {
  const anim = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    const loop = Animated.loop(
      Animated.timing(anim, {
        toValue: 1,
        duration: 1800,
        delay,
        easing: Easing.out(Easing.cubic),
        useNativeDriver: true,
      }),
    );
    loop.start();
    return () => loop.stop();
  }, [anim, delay]);
  return (
    <Animated.View
      style={{
        position: "absolute",
        inset: 0,
        borderRadius: 999,
        borderWidth: 1.5,
        borderColor: `${d.accent}73`,
        opacity: anim.interpolate({ inputRange: [0, 1], outputRange: [0.5, 0] }),
        transform: [{ scale: anim.interpolate({ inputRange: [0, 1], outputRange: [1, 1.9] }) }],
      }}
    />
  );
}

function EqBar({ base, delay }: { base: number; delay: number }) {
  const anim = useRef(new Animated.Value(0.35)).current;
  useEffect(() => {
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(anim, { toValue: 1, duration: 500, delay, useNativeDriver: true }),
        Animated.timing(anim, { toValue: 0.35, duration: 500, useNativeDriver: true }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [anim, delay]);
  return (
    <Animated.View
      style={{
        width: 3,
        height: base,
        borderRadius: 2,
        backgroundColor: d.accent,
        transform: [{ scaleY: anim }],
      }}
    />
  );
}

function MicIcon({ color, size = 34 }: { color: string; size?: number }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round">
      <Path d="M12 2a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z" />
      <Path d="M19 10v1a7 7 0 0 1-14 0v-1M12 18v4" />
    </Svg>
  );
}

export default function VoiceScreen() {
  const [state, setState] = useState<CallState>("connecting");
  const [transcript, setTranscript] = useState("");
  const [seconds, setSeconds] = useState(0);
  const [error, setError] = useState("");
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (state !== "live") return;
    const id = setInterval(() => setSeconds((s) => s + 1), 1000);
    return () => clearInterval(id);
  }, [state]);
  const clock = `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;

  useEffect(() => {
    try {
      const ws = new WebSocket(voiceWsUrl());
      wsRef.current = ws;
      ws.onopen = () => setState("live");
      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(String(event.data)) as {
            type: string;
            data?: string;
            target_role?: string;
            cv_text?: string;
            message?: string;
          };
          if (msg.type === "transcript" && msg.data) setTranscript((p) => p + msg.data);
          else if (msg.type === "intake") {
            wsRef.current?.close();
            router.replace("/new");
          } else if (msg.type === "error") {
            setError(msg.message ?? "Voice chat is unavailable right now.");
            setState("error");
          }
        } catch {
          /* non-JSON frame */
        }
      };
      ws.onerror = () => {
        setError("Couldn't reach the voice service.");
        setState("error");
      };
    } catch {
      setError("Couldn't start the call.");
      setState("error");
    }
    return () => wsRef.current?.close();
  }, []);

  const end = () => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      setState("extracting");
      wsRef.current.send(JSON.stringify({ type: "end" }));
    } else {
      router.back();
    }
  };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: d.bg }}>
      {/* Radial glow */}
      <View
        pointerEvents="none"
        style={{
          position: "absolute",
          top: "14%",
          alignSelf: "center",
          width: 380,
          height: 380,
          borderRadius: 190,
          backgroundColor: `${d.accent}29`,
          // A big blur is approximated with layered translucency on native.
          opacity: 0.7,
        }}
      />
      <View style={{ flex: 1, alignItems: "center", justifyContent: "center", padding: 28 }}>
        <Text
          style={{
            fontFamily: fonts.sansSemiBold,
            fontSize: 10,
            letterSpacing: 1.4,
            textTransform: "uppercase",
            color: d.muted,
            marginBottom: 10,
          }}
        >
          Talk to Ada{state === "live" ? ` · ${clock}` : ""}
        </Text>
        <Text
          style={{
            fontFamily: fonts.serif,
            fontSize: 28,
            lineHeight: 32,
            color: d.ink,
            textAlign: "center",
            marginBottom: 40,
          }}
        >
          Tell Ada about{"\n"}your career.
        </Text>

        <View style={{ width: 128, height: 128, marginBottom: 36 }}>
          {state === "live" && (
            <>
              <PingRing delay={0} />
              <PingRing delay={600} />
              <PingRing delay={1200} />
            </>
          )}
          <View
            style={{
              position: "absolute",
              inset: 10,
              borderRadius: 999,
              backgroundColor: state === "live" ? d.accent : d.accentSoft,
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <MicIcon color={state === "live" ? d.bg : d.accent} />
          </View>
        </View>

        {state === "live" && (
          <View style={{ flexDirection: "row", alignItems: "flex-end", gap: 3, height: 22, marginBottom: 24 }}>
            {[8, 16, 22, 12, 18, 7, 14].map((h, i) => (
              <EqBar key={i} base={h} delay={i * 130} />
            ))}
          </View>
        )}

        <Text style={{ fontFamily: fonts.sans, fontSize: 13, color: d.muted, textAlign: "center" }}>
          {state === "connecting" && "Connecting to Ada…"}
          {state === "live" && "Ada is listening — speak naturally."}
          {state === "extracting" && "Wrapping up — drafting your run…"}
          {state === "error" && error}
        </Text>

        {transcript ? (
          <ScrollView
            style={{
              maxHeight: 150,
              alignSelf: "stretch",
              marginTop: 20,
              backgroundColor: d.surface,
              borderWidth: 1,
              borderColor: d.line,
              borderRadius: 14,
            }}
            contentContainerStyle={{ padding: 14 }}
          >
            <Text style={{ fontFamily: fonts.sans, fontSize: 13, lineHeight: 21, color: d.ink }}>
              {transcript}
              <Text style={{ color: d.accent }}>▎</Text>
            </Text>
          </ScrollView>
        ) : null}
      </View>

      <View style={{ flexDirection: "row", gap: 10, paddingHorizontal: 20, paddingBottom: 24 }}>
        <Pressable
          onPress={() => router.back()}
          style={{
            flex: 1,
            borderWidth: 1,
            borderColor: d.line,
            backgroundColor: d.surface,
            borderRadius: 999,
            paddingVertical: 13,
            alignItems: "center",
          }}
        >
          <Text style={{ fontFamily: fonts.sansMedium, fontSize: 13, color: d.muted }}>End session</Text>
        </Pressable>
        <Pressable
          onPress={end}
          disabled={state === "extracting"}
          style={{
            flex: 1,
            backgroundColor: d.accent,
            borderRadius: 999,
            paddingVertical: 13,
            alignItems: "center",
            opacity: state === "extracting" ? 0.6 : 1,
          }}
        >
          <Text style={{ fontFamily: fonts.sansMedium, fontSize: 13, color: d.bg }}>Use this draft →</Text>
        </Pressable>
      </View>
    </SafeAreaView>
  );
}
