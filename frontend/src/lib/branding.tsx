"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { api } from "@/lib/api-client";

interface Branding {
  app_name: string;
  logo_url: string | null;
  favicon_url: string | null;
  primary_color: string;
  accent_color: string;
}

const DEFAULTS: Branding = {
  app_name: "Varuflow",
  logo_url: null,
  favicon_url: null,
  primary_color: "#4A6CF7",
  accent_color: "#7C3AED",
};

const BrandingContext = createContext<Branding>(DEFAULTS);

export function useBranding() {
  return useContext(BrandingContext);
}

export function BrandingProvider({ children }: { children: React.ReactNode }) {
  const [branding, setBranding] = useState<Branding>(DEFAULTS);

  useEffect(() => {
    api.get<Branding>("/api/branding")
      .then((data) => {
        setBranding(data);
        const root = document.documentElement;
        root.style.setProperty("--vf-brand-primary", data.primary_color);
        root.style.setProperty("--vf-brand-accent", data.accent_color);
        if (data.favicon_url) {
          const link =
            document.querySelector<HTMLLinkElement>('link[rel="icon"]') ??
            document.createElement("link");
          link.rel = "icon";
          link.href = data.favicon_url;
          document.head.appendChild(link);
        }
      })
      .catch(() => {});
  }, []);

  return (
    <BrandingContext.Provider value={branding}>
      {children}
    </BrandingContext.Provider>
  );
}
