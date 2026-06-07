"use client";

import { useTranslations } from "next-intl";
import { ExternalLink, BookOpen, Code2, Zap, Shield } from "lucide-react";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

export default function ApiDocsPage() {
  const t = useTranslations();

  const sections = [
    {
      icon: <BookOpen className="h-5 w-5 text-indigo-400" />,
      color: "bg-indigo-500/10",
      title: t("interactiveDocs"),
      desc: t("interactiveDocsDesc"),
      href: `${BASE}/api/docs`,
      label: t("openSwaggerUi"),
    },
    {
      icon: <Code2 className="h-5 w-5 text-violet-400" />,
      color: "bg-violet-500/10",
      title: t("openApiSchema"),
      desc: t("openApiSchemaDesc"),
      href: `${BASE}/api/openapi.json`,
      label: t("downloadSchema"),
    },
    {
      icon: <Zap className="h-5 w-5 text-amber-400" />,
      color: "bg-amber-500/10",
      title: t("redocDocs"),
      desc: t("redocDocsDesc"),
      href: `${BASE}/api/redoc`,
      label: t("openRedoc"),
    },
    {
      icon: <Shield className="h-5 w-5 text-emerald-400" />,
      color: "bg-emerald-500/10",
      title: t("authentication"),
      desc: t("authenticationDesc"),
      href: "#auth",
      label: t("viewGuide"),
    },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold tracking-tight vf-text-1">{t("apiDocs")}</h1>
        <p className="text-xs vf-text-m mt-0.5">{t("apiDocsDesc")}</p>
      </div>

      {/* Quick links */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {sections.map(s => (
          <a
            key={s.href}
            href={s.href}
            target={s.href.startsWith("http") ? "_blank" : undefined}
            rel="noopener noreferrer"
            className="group vf-section p-5 flex items-start gap-4 hover:shadow-card transition-all"
            
            onMouseEnter={e => (e.currentTarget.style.background = "var(--vf-bg-elevated)")}
            onMouseLeave={e => (e.currentTarget.style.background = "var(--vf-bg-surface)")}
          >
            <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ${s.color}`}>
              {s.icon}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-[13px] font-semibold vf-text-1">{s.title}</p>
              <p className="text-xs vf-text-m mt-0.5">{s.desc}</p>
              <p className="mt-2 text-xs font-medium text-indigo-400 flex items-center gap-1 group-hover:underline">
                {s.label}
                <ExternalLink className="h-3 w-3" />
              </p>
            </div>
          </a>
        ))}
      </div>

      {/* Embedded Swagger UI */}
      <div className="vf-section overflow-hidden" >
        <div className="vf-section-header">
          <h2 className="text-[13px] font-semibold vf-text-1">{t("interactiveDocs")}</h2>
          <a
            href={`${BASE}/api/docs`}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1.5 text-xs font-medium text-indigo-400 hover:underline"
          >
            <ExternalLink className="h-3.5 w-3.5" />
            {t("openInNewTab")}
          </a>
        </div>
        <iframe
          src={`${BASE}/api/docs`}
          title="Varuflow API Documentation"
          className="w-full border-0"
          style={{ height: "70vh", minHeight: 500 }}
          sandbox="allow-scripts allow-same-origin allow-forms allow-popups"
        />
      </div>

      {/* Auth guide */}
      <div id="auth" className="vf-section p-5 space-y-3">
        <h2 className="text-[13px] font-semibold vf-text-1">{t("authentication")}</h2>
        <p className="text-xs vf-text-m">{t("authGuideDesc")}</p>
        <div className="rounded-xl p-4 font-mono text-xs bg-[var(--vf-bg-elevated)] border border-[var(--vf-border)]">
          <p className="text-indigo-400">{"// Include in every request:"}</p>
          <p className="vf-text-1 mt-1">{"Authorization: Bearer <your-api-key>"}</p>
        </div>
        <p className="text-xs vf-text-m">{t("authGuideApiKeys")}</p>
      </div>
    </div>
  );
}
