"use client";

import { useEffect } from "react";

/**
 * CrispChat — injects the Crisp live chat widget.
 * NEXT_PUBLIC_CRISP_WEBSITE_ID is already baked into the build by next.config.mjs.
 * This component is client-only and renders nothing visible — Crisp injects its
 * own widget into the DOM via script.
 */
declare global {
  interface Window {
    $crisp?: unknown[];
    CRISP_WEBSITE_ID?: string;
  }
}

export default function CrispChat() {
  useEffect(() => {
    const id = process.env.NEXT_PUBLIC_CRISP_WEBSITE_ID;
    if (!id || typeof window === "undefined") return;
    if (document.getElementById("crisp-sdk")) return; // already loaded

    window.$crisp = [];
    window.CRISP_WEBSITE_ID = id;

    const script = document.createElement("script");
    script.id = "crisp-sdk";
    script.src = "https://client.crisp.chat/l.js";
    script.async = true;
    document.head.appendChild(script);

    return () => {
      // Cleanup on unmount (SPA navigation away from marketing)
      const el = document.getElementById("crisp-sdk");
      if (el) el.remove();
    };
  }, []);

  return null;
}
