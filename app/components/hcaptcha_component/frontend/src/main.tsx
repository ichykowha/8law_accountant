import React, { useEffect, useRef } from "react";
import ReactDOM from "react-dom/client";
import { Streamlit, withStreamlitConnection } from "streamlit-component-lib";

declare global {
  interface Window {
    hcaptcha?: any;
    onHcaptchaLoad?: () => void;
  }
}

type HcaptchaArgs = {
  siteKey: string;
  theme?: "light" | "dark";
  size?: "normal" | "compact";
};

type Props = {
  args: HcaptchaArgs;
  disabled: boolean;
  width: number;
};

function HcaptchaComponent(props: Props) {
  const { siteKey, theme = "light", size = "normal" } = props.args;
  const widgetIdRef = useRef<string | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    Streamlit.setFrameHeight(140);
    Streamlit.setComponentReady();
  }, []);

  useEffect(() => {
    if (window.hcaptcha) {
      renderHcaptcha();
      return;
    }
    window.onHcaptchaLoad = renderHcaptcha;
    const script = document.createElement("script");
    script.src = "https://js.hcaptcha.com/1/api.js?onload=onHcaptchaLoad&render=explicit";
    script.async = true;
    script.defer = true;
    document.head.appendChild(script);
    return () => {
      if (script.parentNode) script.parentNode.removeChild(script);
    };
    // eslint-disable-next-line
  }, [siteKey, theme, size]);

  function renderHcaptcha() {
    if (!containerRef.current || !window.hcaptcha) return;
    containerRef.current.innerHTML = "";
    widgetIdRef.current = window.hcaptcha.render(containerRef.current, {
      sitekey: siteKey,
      theme,
      size,
      callback: (token: string) => {
        Streamlit.setComponentValue(token);
      },
      "expired-callback": () => {
        Streamlit.setComponentValue(null);
      },
      "error-callback": () => {
        Streamlit.setComponentValue(null);
      },
    });
  }

  return (
    <div style={{ minHeight: 110 }}>
      <div ref={containerRef} />
    </div>
  );
}

const Connected = withStreamlitConnection(HcaptchaComponent);

const rootEl = document.getElementById("root");
if (!rootEl) {
  throw new Error('Missing root element: <div id="root"></div>');
}

ReactDOM.createRoot(rootEl).render(<Connected />);
