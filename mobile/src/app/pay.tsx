/** Paystack inline checkout inside a locked-down WebView.
 *
 *  Hardened per the security audit: navigation carries only the run id; the authoritative
 *  checkout data (key, amount, reference, recipient) is fetched from the backend, so a
 *  spoofed deep link can't inject payment details. The WebView is origin-pinned to Paystack,
 *  and payment success is confirmed by polling the backend run status (driven by the signed
 *  webhook) — never by trusting a WebView postMessage. */
import { router, useLocalSearchParams } from "expo-router";
import { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, Platform, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { api, type CheckoutOut } from "@/lib/api";
import { useTheme } from "@/lib/theme";
import { Button, Sans, Serif } from "@/components/ui";

const CHECKOUT_BASE = "https://checkout.ada.app";
const PAYSTACK_HOSTS = ["paystack.co", "paystack.com"];

export default function PayScreen() {
  const t = useTheme();
  const { runId } = useLocalSearchParams<{ runId: string }>();
  const [checkout, setCheckout] = useState<CheckoutOut | null>(null);
  const [error, setError] = useState("");

  // Authoritative payment status comes from the backend (webhook-driven), not the WebView.
  const poll = useCallback(async () => {
    try {
      const run = await api.getRun(runId);
      if (run.status !== "pending_payment") {
        router.replace(`/run/${runId}`);
      }
    } catch {
      /* transient — try again next tick */
    }
  }, [runId]);

  useEffect(() => {
    const timer = setInterval(poll, 3000);
    return () => clearInterval(timer);
  }, [poll]);

  // Fetch trusted checkout data. A 409 means the run is already paid — the poll moves on.
  useEffect(() => {
    let active = true;
    api
      .getRunCheckout(runId)
      .then((c) => {
        if (!active) return;
        if (c.provider === "stripe" && c.checkout_url) {
          router.replace(`/run/${runId}`); // Stripe is handled before this screen
        } else {
          setCheckout(c);
        }
      })
      .catch(() => active && setError("Couldn't load checkout — head to your run to check status."));
    return () => {
      active = false;
    };
  }, [runId]);

  if (Platform.OS === "web") {
    return (
      <Center t={t}>
        <Serif size={22} style={{ textAlign: "center", marginBottom: 8 }}>
          Paystack checkout
        </Serif>
        <Sans color={t.muted} style={{ textAlign: "center", marginBottom: 16 }}>
          Inline checkout runs in the native app. Continue to the run to watch it once
          payment is confirmed.
        </Sans>
        <Button label="Go to my run" onPress={() => router.replace(`/run/${runId}`)} />
      </Center>
    );
  }

  if (error) {
    return (
      <Center t={t}>
        <Sans color={t.muted} style={{ textAlign: "center", marginBottom: 16 }}>
          {error}
        </Sans>
        <Button label="Go to my run" onPress={() => router.replace(`/run/${runId}`)} />
      </Center>
    );
  }

  if (!checkout || !checkout.public_key) {
    return (
      <Center t={t}>
        <ActivityIndicator color={t.accent} />
      </Center>
    );
  }

  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const { WebView } = require("react-native-webview") as typeof import("react-native-webview");

  const html = `<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1"></head>
<body style="margin:0;background:#faf9f6">
<script src="https://js.paystack.co/v1/inline.js"></script>
<script>
  var handler = PaystackPop.setup({
    key: ${JSON.stringify(checkout.public_key)},
    email: ${JSON.stringify(checkout.email)},
    amount: ${Number(checkout.amount) || 0},
    currency: ${JSON.stringify(checkout.currency)},
    ref: ${JSON.stringify(checkout.reference)},
    onClose: function () { window.ReactNativeWebView.postMessage("closed"); },
    callback: function () { window.ReactNativeWebView.postMessage("paid"); }
  });
  handler.openIframe();
</script>
</body></html>`;

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: t.bg }}>
      <View style={{ flex: 1 }}>
        <WebView
          originWhitelist={[CHECKOUT_BASE, "https://*.paystack.co", "https://*.paystack.com"]}
          source={{ html, baseUrl: CHECKOUT_BASE }}
          // Pin navigation: only our inline page and Paystack may load; block everything else.
          onShouldStartLoadWithRequest={(req) =>
            req.url.startsWith(CHECKOUT_BASE) ||
            req.url.startsWith("about:") ||
            PAYSTACK_HOSTS.some((h) => req.url.includes(h))
          }
          onMessage={(event) => {
            const msg = event.nativeEvent.data;
            // Don't trust "paid" — verify against the backend. "closed" just backs out.
            if (msg === "paid") void poll();
            else if (msg === "closed") router.back();
          }}
        />
      </View>
    </SafeAreaView>
  );
}

function Center({ t, children }: { t: ReturnType<typeof useTheme>; children: React.ReactNode }) {
  return (
    <SafeAreaView
      style={{ flex: 1, backgroundColor: t.bg, alignItems: "center", justifyContent: "center", padding: 24 }}
    >
      {children}
    </SafeAreaView>
  );
}
