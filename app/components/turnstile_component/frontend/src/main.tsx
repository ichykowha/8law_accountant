import React, { useEffect, useMemo, useRef, useState } from "react";
import ReactDOM from "react-dom/client";
import {
  Streamlit,
  withStreamlitConnection,
  ComponentProps
} from "streamlit-component-lib";

declare global {
  interface Window {
    turnstile?: any;
  }
}

type Props = ComponentProps & {
  args: {
    siteKey: string;
    theme?: "auto" | "light" | "dark";
    size?: "normal" | "compact";
  };
};

function TurnstileComponent(props: Props) {
  const { siteKey, theme = "auto", size = "normal" } = props.args;

 const containerId = useMemo(() => `ts_${props.args.siteKey}_${props.width}_${props.height}`.replace(/[^a-zA-Z0-9_]/g, "_"), [
  props.args.siteKey,
  props.width,
  props.height
]);

  const [status, setStatus] = useState<"idle" | "ready" | "solved" | "error">("idle");

  // Ensure iframe is tall enough
  useEffect(() => {
    Streamlit.setFrameHeight(120);
  }, []);

  // Load Turnstile script once
  useEffect(() => {
    if (window.turnstile) {
      setStatus("ready");
      return;
    }

    const existing = document.querySelector('script[data-turnstile="1"]');
    if (existing) return;

    const script = document.createElement("script");
    script.src = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";
    script.async = true;
    script.defer = true;
    script.dataset.turnstile = "1";
    script.onload = () => setStatus("ready");
    script.onerror = () => setStatus("error");
    document.head.appendChild(script);
  }, []);

  // Render widget once script is ready
  useEffect(() => {
    if (status !== "ready") return;
    if (!window.turnstile) return;
    if (renderedRef.current) return;

    const el = document.getElementById(containerId);
    if (!el) return;

    renderedRef.current = true;

    try {
      window.turnstile.render(el, {
        sitekey: siteKey,
        theme,
        size,
        callback: (token: string) => {
          setStatus("solved");
          Streamlit.setComponentValue(token);
        },
        "expired-callback": () => {
          setStatus("ready");
          Streamlit.setComponentValue(null);
        },
        "error-callback": () => {
          setStatus("error");
          Streamlit.setComponentValue(null);
        }
      });
    } catch {
      setStatus("error");
      Streamlit.setComponentValue(null);
    }
  }, [status, siteKey, theme, size, containerId]);

  // Tell Streamlit we’re ready
  useEffect(() => {
    Streamlit.setComponentReady();
  }, []);

  return (
    <div style={{ minHeight: 90 }}>
      <div id={containerId} />
      {status === "error" ? (
        <div style={{ marginTop: 8, fontSize: 12 }}>
          Turnstile failed to load. Check hostname allow-list and browser tracking prevention.
        </div>
      ) : null}
    </div>
  );
}

const Connected = withStreamlitConnection(TurnstileComponent);
ReactDOM.createRoot(document.getElementById("root")!).render(<Connected />);

