"use client";

import { createClient, isSupabaseConfigured } from "@/lib/supabase/client";
import { api } from "@/lib/api-client";
import { cn } from "@/lib/utils";
import { Link, usePathname, useRouter } from "@/i18n/navigation";
import { useLocale, useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import {
  BarChart3, BookOpen, Bot, Building2, FileText, LayoutDashboard, LogOut,
  Package, PiggyBank, RefreshCw, Search, Settings, ShoppingBag, ShoppingCart, Store, Users, Zap,
  Menu, X, Home, Landmark, ReceiptText, Wallet, Target, TrendingUp, Mail, Link2, Calendar,
  Users2, CalendarOff, Timer, ClipboardList, GitFork, GitBranch, FileSignature,
  FileCheck2, Calculator, CreditCard,
  Factory, BookCopy, CalendarCheck2, ClipboardCheck, Package2,
  FolderKanban, Clock, BarChart2, Repeat2,
  Plug, Navigation, Mic, Wifi, PenLine, Bell,
  Network, ArrowLeftRight, Receipt,
  DollarSign, FileBarChart2, FlaskConical, TrendingDown, ShieldCheck,
  CalendarDays, GraduationCap, CheckSquare,
  Megaphone, Wrench, Ticket,
  Banknote, FileSpreadsheet, Activity,
  MessageCircle, HelpCircle, List,
  Leaf, Award, CalendarClock, Eye, EyeOff, Fingerprint,
  PieChart, FolderLock, Radio, Star,
  Smartphone, UserPlus,
  Video, Camera, MapPin, AlertCircle,
  Gift, Flame, Heart, Globe,
  Shield, FileSearch,
} from "lucide-react";
import Script from "next/script";
import dynamic from "next/dynamic";
import ThemeToggle from "@/components/ui/ThemeToggle";

const AiChat              = dynamic(() => import("@/components/app/AiChat"),              { ssr: false });
const CommandPalette      = dynamic(() => import("@/components/app/CommandPalette"),      { ssr: false });
const PwaInstallBanner    = dynamic(() => import("@/components/app/PwaInstallBanner"),    { ssr: false });
const SessionTimeoutModal = dynamic(() => import("@/components/app/SessionTimeoutModal"), { ssr: false });
const MaintenanceBanner   = dynamic(() => import("@/components/app/MaintenanceBanner").then(m => m.MaintenanceBanner), { ssr: false });

/* ── Nav groups ─────────────────────────────────────────────────────────────── */
const NAV_GROUPS = [
  {
    label: "Overview",
    items: [
      { href: "/dashboard", icon: LayoutDashboard, key: "dashboard" },
      { href: "/analytics", icon: BarChart3,        key: "analytics" },
    ],
  },
  {
    label: "Operations",
    items: [
      { href: "/inventory", icon: Package,      key: "inventory"    },
      { href: "/invoices",  icon: FileText,      key: "invoices"     },
      { href: "/quotes",           icon: FileSignature,  key: "quotes"          },
      { href: "/payment-options",  icon: CreditCard,     key: "paymentOptions"  },
      { href: "/local-payments",   icon: Globe,          key: "localPayments"   },
      { href: "/deposits",         icon: Banknote,       key: "deposits"        },
      { href: "/after-sales",      icon: ReceiptText,    key: "afterSales"      },
      { href: "/recurring",        icon: RefreshCw,      key: "recurring"       },
      { href: "/merchant-subscriptions", icon: RefreshCw, key: "merchantSubs"  },
      { href: "/reconciliation",   icon: BarChart2,      key: "reconciliation"  },
      { href: "/pos",       icon: ShoppingCart, key: "cashRegister" },
      { href: "/customers", icon: Users,        key: "customers"    },
      { href: "/email-templates", icon: Mail,           key: "emailTemplates" },
      { href: "/sms-outbox",      icon: MessageCircle,  key: "smsOutbox"      },
    ],
  },
  {
    label: "Intelligence",
    items: [
      { href: "/ai",               icon: Bot,           key: "aiAdvisor"    },
      { href: "/ai/automation",    icon: TrendingUp,    key: "aiAutomation" },
      { href: "/ai/workflows",     icon: GitBranch,     key: "aiWorkflows"  },
      { href: "/ai/contracts",     icon: FileSignature, key: "aiContracts"  },
    ],
  },
  {
    label: "CEO & Finance",
    items: [
      { href: "/ceo",               icon: TrendingUp,     key: "ceoDashboard"  },
      { href: "/ceo/cash-forecast",         icon: DollarSign,     key: "ceoCashFlow"        },
      { href: "/cashflow-prediction",        icon: TrendingUp,     key: "cashflowPrediction" },
      { href: "/anomaly-detection",          icon: ShieldCheck,    key: "anomalyDetection"   },
      { href: "/ceo/kpi-goals",     icon: Target,         key: "ceoKpiGoals"   },
      { href: "/ceo/okr",           icon: GitBranch,      key: "okrGoals"      },
      { href: "/budget",            icon: PiggyBank,      key: "budgetWorkflow"},
      { href: "/ceo/board-report",  icon: FileBarChart2,  key: "ceoBoardReport"},
      { href: "/ceo/scenarios",     icon: GitBranch,      key: "ceoScenarios"  },
    ],
  },
  {
    label: "Growth",
    items: [
      { href: "/growth",              icon: TrendingUp,    key: "growthHub"       },
      { href: "/growth/partners",     icon: Users,         key: "growthPartners"  },
      { href: "/growth/experiments",  icon: FlaskConical,  key: "growthExp"       },
      { href: "/growth/expansion",    icon: Globe,         key: "growthExpansion" },
      { href: "/growth/churn",        icon: TrendingDown,  key: "growthChurn"     },
    ],
  },
  {
    label: "Business Intelligence",
    items: [
      { href: "/analytics/dashboard",  icon: LayoutDashboard, key: "biDashboards"  },
      { href: "/analytics/reports",    icon: ClipboardList,   key: "biReports"     },
      { href: "/analytics/scheduled",  icon: Clock,           key: "biScheduled"   },
      { href: "/analytics/benchmarks", icon: BarChart2,       key: "biBenchmarks"  },
      { href: "/analytics/cohorts",    icon: Users2,          key: "biCohorts"        },
      { href: "/cohort-analysis",       icon: BarChart3,       key: "cohortAnalysis"   },
      { href: "/dashboard-builder",     icon: LayoutDashboard, key: "dashboardBuilder" },
      { href: "/report-builder",        icon: FileBarChart2,   key: "reportBuilder"   },
    ],
  },
  {
    label: "CRM & Sales",
    items: [
      { href: "/crm",           icon: Target,     key: "crmPipeline"  },
      { href: "/crm/list",      icon: List,       key: "crmList"      },
      { href: "/crm/analytics", icon: BarChart2,  key: "crmAnalytics" },
      { href: "/crm/forecast",  icon: TrendingUp, key: "crmForecast"  },
      { href: "/crm/sequences", icon: Mail,       key: "crmSequences" },
      { href: "/crm/leads",        icon: Users,      key: "crmLeads"     },
      { href: "/crm/leads/forms",  icon: Link2,      key: "crmLeadForms" },
      { href: "/crm/meetings",  icon: Calendar,   key: "crmMeetings"  },
    ],
  },
  {
    label: "HR & People",
    items: [
      { href: "/hr",            icon: Users2,       key: "hrEmployees" },
      { href: "/hr/leave",          icon: CalendarOff,  key: "hrLeave"         },
      { href: "/hr/leave/calendar", icon: CalendarDays, key: "hrLeaveCalendar" },
      { href: "/hr/shifts",         icon: CalendarDays, key: "hrShifts"        },
      { href: "/hr/timesheets",     icon: ClipboardCheck, key: "hrTimesheets"  },
      { href: "/hr/onboarding",     icon: CheckSquare,  key: "hrOnboarding"    },
      { href: "/hr/training",       icon: GraduationCap, key: "hrTraining"     },
      { href: "/hr/time",           icon: Timer,        key: "hrTime"          },
      { href: "/hr/reviews",        icon: ClipboardList, key: "hrReviews"      },
      { href: "/hr/org-chart",      icon: GitFork,      key: "hrOrgChart"      },
    ],
  },
  {
    label: "Manufacturing",
    items: [
      { href: "/manufacturing",          icon: Factory,        key: "mfgOrders"   },
      { href: "/manufacturing/bom",      icon: BookCopy,       key: "mfgBom"      },
      { href: "/manufacturing/planning", icon: CalendarCheck2, key: "mfgPlanning" },
      { href: "/manufacturing/qc",       icon: ClipboardCheck, key: "mfgQc"       },
      { href: "/manufacturing/kits",     icon: Package2,       key: "mfgKits"     },
      { href: "/kitting",                icon: Package,        key: "kitting"     },
      { href: "/landed-costs",           icon: DollarSign,     key: "landedCosts" },
      { href: "/vendor-ratings",         icon: Activity,       key: "vendorRatings" },
    ],
  },
  {
    label: "Projects",
    items: [
      { href: "/projects",            icon: FolderKanban, key: "pmProjects"   },
      { href: "/time-tracking",       icon: Clock,        key: "pmTime"       },
      { href: "/projects/pl",         icon: BarChart2,    key: "pmPl"         },
      { href: "/projects/retainers",  icon: Repeat2,      key: "pmRetainers"  },
    ],
  },
  {
    label: "Work Management",
    items: [
      { href: "/work",               icon: ClipboardList,  key: "wmTasks"        },
      { href: "/work/announcements", icon: Megaphone,      key: "wmAnnouncements" },
      { href: "/work/messages",      icon: MessageCircle,  key: "wmMessages"      },
      { href: "/work/meeting-notes", icon: BookOpen,       key: "wmMeetingNotes"  },
      { href: "/work/orders",        icon: Wrench,         key: "wmWorkOrders"   },
      { href: "/work/tickets",       icon: Ticket,         key: "wmTickets"      },
      { href: "/job-cards",          icon: Wrench,         key: "wmJobCards"     },
    ],
  },
  {
    label: "Scheduling",
    items: [
      { href: "/scheduling",          icon: CalendarDays,    key: "schRoster"   },
      { href: "/scheduling/swaps",    icon: ArrowLeftRight,  key: "schSwaps"    },
      { href: "/scheduling/overtime", icon: Clock,           key: "schOvertime" },
    ],
  },
  {
    label: "Finance",
    items: [
      { href: "/purchase-requests", icon: FileSpreadsheet, key: "finPurchaseRequests" },
      { href: "/petty-cash",        icon: Banknote,        key: "finPettyCash" },
    ],
  },
  {
    label: "Reports",
    items: [
      { href: "/reports/dashboard",    icon: BarChart3,  key: "rptDashboard" },
      { href: "/reports/productivity", icon: Activity,   key: "rptProductivity" },
      { href: "/reports/attendance",   icon: CalendarCheck2, key: "rptAttendance" },
      { href: "/reports/pnl",          icon: BarChart3,  key: "rptPnl" },
      { href: "/reports/cashflow",     icon: TrendingUp, key: "rptCashflow" },
      { href: "/reports/balance-sheet", icon: Landmark,   key: "rptBalanceSheet" },
    ],
  },
  {
    label: "Client Portal",
    items: [
      { href: "/portal-admin/chat",      icon: MessageCircle, key: "portalChat" },
      { href: "/portal-admin/tickets",   icon: HelpCircle,    key: "portalTickets" },
      { href: "/portal-admin/reminders", icon: Bell,          key: "portalReminders" },
    ],
  },
  {
    label: "MENA Compliance",
    items: [
      { href: "/mena/zatca",    icon: FileCheck2,  key: "menaZatca"    },
      { href: "/mena/uae-vat",  icon: ReceiptText, key: "menaUaeVat"   },
      { href: "/mena/zakat",    icon: Calculator,  key: "menaZakat"    },
      { href: "/mena/payments", icon: CreditCard,  key: "menaPayments" },
    ],
  },
  {
    label: "Integrations",
    items: [
      { href: "/integrations",               icon: Plug,        key: "intgHub"           },
      { href: "/integrations/shopify",        icon: ShoppingBag, key: "intgShopify"       },
      { href: "/integrations/crm",            icon: Users,       key: "intgCrm"           },
      { href: "/integrations/notifications",  icon: Bell,        key: "intgNotifications" },
      { href: "/integrations/accounting",     icon: BookOpen,    key: "intgAccounting"    },
      { href: "/integrations/banking",        icon: Building2,   key: "intgBanking"       },
      { href: "/integrations/zapier",         icon: Zap,         key: "intgZapier"        },
    ],
  },
  {
    label: "Mobile & Field",
    items: [
      { href: "/mobile",             icon: Navigation, key: "mobileHub"        },
      { href: "/mobile/routes",      icon: Navigation, key: "mobileRoutes"     },
      { href: "/mobile/signatures",  icon: PenLine,    key: "mobileSignatures" },
      { href: "/mobile/terminal",    icon: Wifi,       key: "mobileTerminal"   },
      { href: "/mobile/invoices",    icon: FileText,   key: "mobileInvoices"   },
      { href: "/mobile/voice-notes", icon: Mic,        key: "mobileVoiceNotes" },
    ],
  },
  {
    label: "Multi-Entity",
    items: [
      { href: "/multi-entity",               icon: Network,          key: "multiEntityHub"         },
      { href: "/multi-entity/subsidiaries",   icon: Building2,        key: "subsidiaries"            },
      { href: "/multi-entity/consolidated",   icon: BarChart3,        key: "consolidatedReports"     },
      { href: "/multi-entity/intercompany",   icon: ArrowLeftRight,   key: "intercompanyTransfers"   },
      { href: "/multi-entity/permissions",    icon: Shield,           key: "entityPermissions"       },
    ],
  },
  {
    label: "Franchise",
    items: [
      { href: "/franchise",              icon: GitBranch, key: "franchiseHub"         },
      { href: "/franchise/onboarding",   icon: Users,     key: "franchiseeOnboarding" },
      { href: "/franchise/royalties",    icon: Receipt,   key: "royaltyBilling"       },
      { href: "/franchise/catalog",      icon: Package,   key: "franchiseCatalog"     },
    ],
  },
  {
    label: "Compliance",
    items: [
      { href: "/settings/security/audit-chain",   icon: Shield,        key: "auditChain"      },
      { href: "/settings/security/field-masking",  icon: EyeOff,        key: "fieldMasking"    },
      { href: "/settings/security/data-residency", icon: Globe,         key: "dataResidency"   },
      { href: "/settings/security/pentest",        icon: FileSearch,    key: "pentestReports"  },
      { href: "/contract-signing",                 icon: FileSignature, key: "contractSigning" },
      { href: "/gdpr",                             icon: Shield,        key: "gdprConsent"     },
      { href: "/compliance/risk",                  icon: Fingerprint,   key: "riskRegister"    },
      { href: "/compliance/insurance",             icon: Building2,     key: "insurancePolicies"},
      { href: "/compliance/regulatory",            icon: CalendarClock, key: "regulatoryCalendar"},
      { href: "/compliance/whistleblower",         icon: Eye,           key: "whistleblower"   },
      { href: "/compliance/conflicts",             icon: Users2,        key: "conflictRegister" },
    ],
  },
  {
    label: "Sustainability",
    items: [
      { href: "/sustainability/carbon",            icon: Leaf,          key: "carbonFootprint" },
      { href: "/sustainability/esg",               icon: BarChart3,     key: "esgReports"      },
      { href: "/sustainability/suppliers",         icon: Award,         key: "supplierSustainability" },
    ],
  },
  {
    label: "Customer App",
    items: [
      { href: "/customer-app",                icon: Smartphone,  key: "customerApp"          },
      { href: "/customer-app/wallet",         icon: CreditCard,  key: "walletPasses"         },
      { href: "/customer-app/family",         icon: Users,       key: "familyAccounts"       },
      { href: "/customer-app/subscriptions",  icon: Repeat2,     key: "bookingSubscriptions" },
      { href: "/customer-app/group-bookings", icon: UserPlus,    key: "groupBookings"        },
      { href: "/customer-app/waitlist",       icon: Clock,       key: "bookingWaitlist"      },
      { href: "/customer-app/chat",            icon: MessageCircle, key: "customerChat"       },
      { href: "/customer-app/video",           icon: Video,         key: "videoConsultations" },
      { href: "/customer-app/voice-notes",     icon: Mic,           key: "voiceNotes"         },
      { href: "/customer-app/reminder-prefs",  icon: Bell,          key: "reminderPrefs"        },
      { href: "/customer-app/status-alerts",   icon: AlertCircle,   key: "liveStatusAlerts"     },
      { href: "/customer-app/timelines",       icon: List,          key: "serviceTimelines"     },
      { href: "/customer-app/tracking",        icon: MapPin,        key: "liveTracking"         },
      { href: "/customer-app/photos",          icon: Camera,        key: "photoUpdates"         },
      { href: "/customer-app/history",         icon: Clock,         key: "customerHistory"      },
    ],
  },
  {
    label: "Personalization",
    items: [
      { href: "/customer-app/preferences",     icon: Settings,      key: "customerPreferences"  },
      { href: "/customer-app/recommendations", icon: Zap,           key: "aiRecommendations"    },
      { href: "/customer-app/important-dates", icon: CalendarClock, key: "importantDates"       },
      { href: "/customer-app/payment-methods", icon: CreditCard,    key: "savedPaymentMethods"  },
      { href: "/customer-app/staff-notes",     icon: PenLine,       key: "staffNotes"           },
    ],
  },
  {
    label: "Loyalty & Rewards",
    items: [
      { href: "/customer-app/membership-tiers",  icon: Shield,    key: "membershipTiers"   },
      { href: "/customer-app/achievements",       icon: Award,     key: "achievements"      },
      { href: "/customer-app/birthday-vouchers",  icon: Gift,      key: "birthdayVouchers"  },
      { href: "/customer-app/referrals",          icon: UserPlus,  key: "referralTracking"  },
      { href: "/customer-app/streaks",            icon: Flame,     key: "loyaltyStreaks"    },
    ],
  },
  {
    label: "Convenience",
    items: [
      { href: "/customer-app/wallet-payments",      icon: CreditCard,   key: "walletPayments"        },
      { href: "/customer-app/addresses",            icon: Home,         key: "addressBook"           },
      { href: "/customer-app/calendar-sync",        icon: Calendar,     key: "calendarSync"          },
      { href: "/customer-app/accountant-forwarding",icon: Mail,         key: "accountantForwarding"  },
      { href: "/customer-app/receipt-exports",      icon: Receipt,      key: "receiptExports"        },
    ],
  },
  {
    label: "B2B Buyers",
    items: [
      { href: "/b2b",                       icon: Building2,    key: "b2bHub"              },
      { href: "/b2b/buyer-pos",             icon: FileText,     key: "buyerPurchaseOrders" },
      { href: "/b2b/org-members",           icon: Users2,       key: "buyerOrgMembers"     },
      { href: "/b2b/negotiated-pricing",    icon: DollarSign,   key: "negotiatedPricing"   },
      { href: "/b2b/quote-comparisons",     icon: BarChart2,    key: "quoteComparisons"    },
    ],
  },
  {
    label: "Trust & Verification",
    items: [
      { href: "/trust/reviews",     icon: Star,        key: "verifiedReviews"      },
      { href: "/trust/credentials", icon: FileCheck2,  key: "staffCredentials"     },
      { href: "/trust/capacity",    icon: Activity,    key: "bookingCapacity"      },
      { href: "/trust/portfolio",   icon: Camera,      key: "portfolioGallery"     },
    ],
  },
  {
    label: "Customer Service",
    items: [
      { href: "/customer-service/live-chat",       icon: MessageCircle, key: "liveChatWidget"   },
      { href: "/customer-service/chatbot",         icon: Bot,           key: "chatbotAssistant" },
      { href: "/customer-service/knowledge-base",  icon: BookOpen,      key: "knowledgeBase"    },
      { href: "/customer-service/return-pickups",  icon: Package,       key: "returnPickups"    },
    ],
  },
  {
    label: "Trust & Safety",
    items: [
      { href: "/trust-safety/identity-verification", icon: Fingerprint,  key: "identityVerification" },
      { href: "/trust-safety/background-checks",     icon: ShieldCheck,  key: "backgroundChecks"     },
      { href: "/trust-safety/insurance",             icon: Shield,       key: "insuranceAddons"       },
      { href: "/trust-safety/disputes",              icon: HelpCircle,   key: "disputeResolution"     },
      { href: "/trust-safety/merchant-reviews",      icon: Star,         key: "merchantReviews"       },
    ],
  },
  {
    label: "Inbox",
    items: [
      { href: "/inbox",                icon: MessageCircle, key: "unifiedInbox"         },
      { href: "/inbox/translation",    icon: Globe,         key: "autoTranslation"      },
      { href: "/inbox/smart-replies",  icon: Zap,           key: "smartReplies"         },
      { href: "/inbox/sentiment",      icon: Activity,      key: "sentimentAnalysis"    },
    ],
  },
  {
    label: "Reporting",
    items: [
      { href: "/reporting/statements",       icon: FileText,     key: "customerStatements"   },
      { href: "/reporting/mobile-dashboard", icon: Smartphone,   key: "mobileDashboard"      },
      { href: "/reporting/voice-reports",    icon: Mic,          key: "voiceReports"         },
      { href: "/reporting/anomalies",        icon: Bell,         key: "anomalyAlerts"        },
    ],
  },
  {
    label: "AI Tools",
    items: [
      { href: "/ai-tools/product-descriptions", icon: Bot,        key: "aiProductDesc"        },
      { href: "/ai-tools/email-drafts",         icon: Mail,       key: "aiEmailDrafts"        },
      { href: "/ai-tools/photo-tags",           icon: Camera,     key: "aiPhotoTags"          },
      { href: "/ai-tools/pricing",              icon: DollarSign, key: "aiPricing"            },
      { href: "/ai-tools/personas",             icon: Users,      key: "aiPersonas"           },
    ],
  },
  {
    label: "Developer & API",
    items: [
      { href: "/integrations/calendar",  icon: Calendar,     key: "calendarSync"        },
      { href: "/integrations/zapier",    icon: Zap,          key: "zapierConnector"     },
      { href: "/integrations/webhooks",  icon: Link2,        key: "customerWebhooks"    },
      { href: "/integrations/api-keys",  icon: Fingerprint,  key: "apiKeys"             },
      { href: "/integrations/api-docs",  icon: BookCopy,     key: "apiDocs"             },
    ],
  },
  {
    label: "Quality of Life",
    items: [
      { href: "/settings/search",               icon: Search,   key: "fastSearch"          },
      { href: "/settings/notification-bundles", icon: Bell,     key: "notificationBundles" },
      { href: "/settings/timezones",            icon: Clock,    key: "timezoneSettings"    },
    ],
  },
  {
    label: "Mobile",
    items: [
      { href: "/mobile/widgets",   icon: Smartphone, key: "homeScreenWidgets" },
      { href: "/mobile/watch",     icon: Clock,      key: "watchApp"          },
      { href: "/mobile/shortcuts", icon: Mic,        key: "voiceShortcuts"    },
      { href: "/mobile/alerts",    icon: Bell,       key: "lockScreenAlerts"  },
    ],
  },
  {
    label: "Operational Excellence",
    items: [
      { href: "/ops/sop",        icon: BookOpen,      key: "sopLibrary"         },
      { href: "/ops/checklists", icon: CheckSquare,   key: "checklists"         },
      { href: "/ops/reminders",  icon: Bell,          key: "recurringReminders" },
      { href: "/ops/decisions",  icon: ClipboardList, key: "decisionLog"        },
    ],
  },
  {
    label: "Investor & Board",
    items: [
      { href: "/investor/updates",    icon: TrendingUp,    key: "investorUpdates"  },
      { href: "/investor/cap-table",  icon: PieChart,      key: "capTable"         },
      { href: "/investor/board-packs",icon: FileText,      key: "boardPacks"       },
      { href: "/investor/data-room",  icon: FolderLock,    key: "dataRoom"         },
    ],
  },
  {
    label: "Marketing",
    items: [
      { href: "/marketing/attribution",    icon: Target,        key: "marketingAttribution" },
      { href: "/marketing/ab-testing",     icon: GitBranch,     key: "abTesting"            },
      { href: "/marketing/landing-pages",  icon: LayoutDashboard, key: "landingPages"       },
      { href: "/marketing/broadcasts",     icon: Radio,         key: "marketingBroadcasts"  },
      { href: "/marketing/surveys",        icon: Star,          key: "npsSurveys"           },
    ],
  },
  {
    label: "Governance",
    items: [
      { href: "/governance",               icon: ShieldCheck,    key: "govHub"         },
      { href: "/governance/approvals",     icon: ClipboardCheck, key: "govApprovals"   },
      { href: "/governance/policies",      icon: BookOpen,       key: "govPolicies"    },
      { href: "/governance/sign-contract", icon: FileSignature,  key: "govSign"        },
    ],
  },
  {
    label: "Accounting",
    items: [
      { href: "/accounting",           icon: BookOpen,     key: "ledger"     },
      { href: "/accounting/reports",   icon: BarChart3,    key: "reports"    },
      { href: "/accounting/vat",       icon: ReceiptText,  key: "vatReturn"  },
      { href: "/accounting/assets",    icon: Landmark,     key: "assets"     },
      { href: "/accounting/payroll",   icon: Wallet,       key: "payroll"    },
      { href: "/accounting/budget",    icon: PiggyBank,    key: "budget"     },
      { href: "/accounting/bank-feed",           icon: Building2,   key: "bankFeed"   },
      { href: "/accounting/bank-reconciliation", icon: CheckSquare, key: "bankRecon"  },
    ],
  },
  {
    label: "E-commerce",
    items: [
      { href: "/shop/orders", icon: ShoppingBag, key: "shopOrders" },
      { href: "/shop/config", icon: Store,       key: "shopConfig" },
    ],
  },
  {
    label: "Settings",
    items: [
      { href: "/settings",               icon: Settings,       key: "settings"    },
      { href: "/settings/setup-health",  icon: Activity,       key: "setupHealth" },
      { href: "/settings/data-import",   icon: FileSpreadsheet, key: "dataImport" },
      { href: "/settings/sandbox",       icon: FlaskConical,   key: "sandbox"     },
    ],
  },
] as const;

/* Mobile bottom nav */
const MOBILE_NAV = [
  { href: "/dashboard", icon: Home,      label: "Home"      },
  { href: "/inventory", icon: Package,   label: "Inventory" },
  { href: "/invoices",  icon: FileText,  label: "Invoices"  },
  { href: "/ai",        icon: Bot,       label: "AI"        },
  { href: "/settings",  icon: Settings,  label: "More"      },
] as const;

const LOCALES = [
  { code: "sv", label: "SV" },
  { code: "en", label: "EN" },
] as const;

const PAGE_TITLE_MAP: Record<string, string> = {
  "/dashboard": "Dashboard",
  "/inventory": "Inventory",
  "/invoices":  "Invoices",
  "/recurring": "Recurring",
  "/pos":       "Cash Register",
  "/customers": "Customers",
  "/analytics": "Analytics",
  "/ai":        "AI Advisor",
  "/settings":  "Settings",
};

function getPageTitle(pathname: string): string {
  for (const [path, title] of Object.entries(PAGE_TITLE_MAP)) {
    if (pathname === path || pathname.startsWith(path + "/")) return title;
  }
  return "Varuflow";
}

/* ── Component ──────────────────────────────────────────────────────────────── */
export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router   = useRouter();
  const locale   = useLocale();
  const t        = useTranslations("nav");
  const supabase = createClient();

  const [isClient,         setIsClient]         = useState(false);
  const [email,            setEmail]            = useState<string | null>(null);
  const [fortnoxConnected, setFortnoxConnected] = useState(false);
  const [openaiConnected,  setOpenaiConnected]  = useState(false);
  const [sidebarOpen,      setSidebarOpen]      = useState(false);

  useEffect(() => {
    setIsClient(true);
    if (isSupabaseConfigured) {
      supabase.auth.getUser().then(({ data }) => {
        const userEmail = data.user?.email ?? null;
        setEmail(userEmail);
        if (userEmail && process.env.NEXT_PUBLIC_CRISP_WEBSITE_ID && typeof window !== "undefined") {
          const w = window as unknown as Record<string, unknown>;
          if (w.$crisp) (w.$crisp as unknown[][]).push(["set", "user:email", userEmail]);
        }
      });
    }
    api.get<{ connected: boolean }>("/api/integrations/fortnox/status")
      .then((s) => setFortnoxConnected(s.connected))
      .catch(() => {});
    api.get<{ openai_configured: boolean }>("/api/integrations/config")
      .then((s) => setOpenaiConnected(s.openai_configured))
      .catch(() => {});
  }, []);

  function isActive(href: string) {
    if (!isClient) return false;
    if (href === "/dashboard") return pathname === "/dashboard";
    return pathname === href || pathname.startsWith(href + "/");
  }

  async function handleSignOut() {
    await supabase.auth.signOut();
    toast.success("Signed out");
    router.push("/auth/login");
  }

  function openSearch() {
    document.dispatchEvent(
      new KeyboardEvent("keydown", { key: "k", metaKey: true, bubbles: true })
    );
  }

  const avatarLetter = isClient && email ? email[0].toUpperCase() : "?";

  /* ── Sidebar content ────────────────────────────────────────────────────── */
  const SidebarContent = () => (
    <>
      {/* Logo */}
      <div className="flex h-[57px] shrink-0 items-center gap-3 px-5"
        style={{ borderBottom: "1px solid var(--vf-border)" }}>
        <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 shadow-glow shrink-0">
          <Zap className="h-3.5 w-3.5 text-white" />
        </div>
        <span className="bg-gradient-to-r from-indigo-500 to-violet-500 bg-clip-text text-transparent text-[15px] font-bold tracking-tight flex-1 min-w-0">
          Varuflow
        </span>
        {isClient && fortnoxConnected && (
          <span className="shrink-0 rounded-full bg-emerald-500/15 border border-emerald-500/25 px-1.5 py-0.5 text-[9px] font-bold text-emerald-500 tracking-wide">
            FX
          </span>
        )}
        <button
          className="lg:hidden ml-1 vf-text-m hover:vf-text-1 transition-colors"
          onClick={() => setSidebarOpen(false)}
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Nav groups */}
      <nav className="flex flex-1 flex-col gap-1 overflow-y-auto px-2 py-3">
        {NAV_GROUPS.map((group, gi) => (
          <div key={group.label} className={cn(gi > 0 && "mt-3")}>
            <p className="mb-1 px-3 text-[10px] font-semibold vf-text-m uppercase tracking-[0.08em] select-none">
              {group.label}
            </p>
            <div className="flex flex-col gap-[1px]">
              {group.items.map(({ href, icon: Icon, key }) => {
                const active = isActive(href);
                return (
                  <Link
                    key={href}
                    href={href}
                    onClick={() => setSidebarOpen(false)}
                    className={cn(
                      "group relative flex items-center gap-2.5 rounded-xl px-3 py-[7px] text-[13px] font-medium transition-all duration-100",
                      active
                        ? "bg-indigo-500/[0.12] text-indigo-500"
                        : "vf-text-m hover:vf-text-2 hover:bg-[var(--vf-hover)]"
                    )}
                  >
                    {active && (
                      <span className="absolute left-0 top-1/2 -translate-y-1/2 h-5 w-[3px] rounded-r-full bg-indigo-500" />
                    )}
                    <Icon className={cn(
                      "h-[18px] w-[18px] shrink-0 transition-colors",
                      active ? "text-indigo-500" : "vf-text-m group-hover:vf-text-2"
                    )} />
                    {t(key as Parameters<typeof t>[0])}
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      {/* Bottom: theme + locale + account */}
      <div className="shrink-0 px-2 py-3 space-y-1" style={{ borderTop: "1px solid var(--vf-border)" }}>
        {/* Theme toggle */}
        <div className="flex justify-end px-1 pb-1">
          <ThemeToggle />
        </div>

        {/* AI indicator */}
        {isClient && (
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg">
            <span className={cn(
              "h-1.5 w-1.5 rounded-full shrink-0",
              openaiConnected ? "bg-emerald-500 animate-pulse-dot" : "bg-[var(--vf-text-muted)]/30"
            )} />
            <span className="text-[11px] vf-text-m">
              AI {openaiConnected ? "connected" : "not configured"}
            </span>
          </div>
        )}

        {/* Locale switcher */}
        <div className="flex gap-[2px] px-1">
          {LOCALES.map(({ code, label }) => (
            <button
              key={code}
              onClick={() => router.replace(pathname, { locale: code })}
              className={cn(
                "flex-1 rounded-md py-1.5 text-[10px] font-bold tracking-wider transition-colors",
                isClient && locale === code
                  ? "vf-text-2 bg-[var(--vf-bg-elevated)]"
                  : "vf-text-m hover:vf-text-m"
              )}
            >
              {label}
            </button>
          ))}
        </div>

        {/* Account row */}
        <button
          onClick={handleSignOut}
          className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 transition-colors vf-row group"
        >
          <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-indigo-600 to-violet-700 text-[11px] font-bold text-white select-none">
            {avatarLetter}
          </div>
          <div className="flex-1 min-w-0 text-left">
            <p className="truncate text-[12px] font-medium vf-text-2 transition-colors">
              {isClient ? (email ?? "Account") : "Account"}
            </p>
            <p className="text-[10px] vf-text-m">Free plan</p>
          </div>
          <LogOut className="h-3.5 w-3.5 shrink-0 vf-text-m transition-colors" />
        </button>
      </div>
    </>
  );

  /* ── Layout ─────────────────────────────────────────────────────────────── */
  return (
    <>
      <MaintenanceBanner />
      {process.env.NEXT_PUBLIC_CRISP_WEBSITE_ID && /^[A-Za-z0-9-]{1,64}$/.test(process.env.NEXT_PUBLIC_CRISP_WEBSITE_ID) && (
        <Script
          id="crisp-chat"
          strategy="afterInteractive"
          dangerouslySetInnerHTML={{
            __html: `
              window.$crisp=[];window.CRISP_WEBSITE_ID="${process.env.NEXT_PUBLIC_CRISP_WEBSITE_ID}";
              (function(){var d=document;var s=d.createElement("script");
              s.src="https://client.crisp.chat/l.js";s.async=1;d.getElementsByTagName("head")[0].appendChild(s);})();
            `,
          }}
        />
      )}

      <div className="flex min-h-screen" style={{ background: "var(--vf-bg-primary)" }}>

        {/* Mobile overlay */}
        {sidebarOpen && (
          <div
            className="fixed inset-0 z-30 bg-black/50 backdrop-blur-sm lg:hidden"
            onClick={() => setSidebarOpen(false)}
          />
        )}

        {/* Sidebar */}
        <aside className={cn(
          "fixed inset-y-0 left-0 z-40 flex w-[220px] shrink-0 flex-col transition-transform duration-200 lg:static lg:translate-x-0",
          sidebarOpen ? "translate-x-0" : "-translate-x-full"
        )} style={{ background: "var(--vf-bg-primary)", borderRight: "1px solid var(--vf-border)" }}>
          <SidebarContent />
        </aside>

        {/* Main column */}
        <div className="flex flex-1 min-w-0 flex-col">

          {/* Mobile top bar */}
          <header className="flex h-14 shrink-0 items-center gap-3 px-4 lg:hidden"
            style={{ borderBottom: "1px solid var(--vf-border)" }}>
            <button
              onClick={() => setSidebarOpen(true)}
              className="vf-text-m hover:vf-text-1 transition-colors"
            >
              <Menu className="h-5 w-5" />
            </button>
            <span className="bg-gradient-to-r from-indigo-500 to-violet-500 bg-clip-text text-transparent text-[15px] font-bold tracking-tight">
              Varuflow
            </span>
          </header>

          {/* Desktop topbar */}
          <header className="hidden lg:flex h-[57px] shrink-0 items-center justify-between gap-4 px-6"
            style={{ borderBottom: "1px solid var(--vf-border)" }}>
            <h1 className="text-[13px] font-semibold tracking-tight vf-text-1">
              {getPageTitle(pathname)}
            </h1>
            <div className="flex items-center gap-2">
              <button
                onClick={openSearch}
                className="flex items-center gap-2 rounded-xl px-3 py-2 text-xs vf-text-m transition-all vf-btn-ghost h-9"
              >
                <Search className="h-3.5 w-3.5" />
                <span className="hidden xl:inline">Search</span>
                <kbd className="hidden xl:inline-block rounded-md px-1.5 py-0.5 text-[10px] vf-text-m font-mono"
                  style={{ background: "var(--vf-bg-elevated)", border: "1px solid var(--vf-border)" }}>
                  ⌘K
                </kbd>
              </button>
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-indigo-600 to-violet-700 text-[11px] font-bold text-white select-none">
                {avatarLetter}
              </div>
            </div>
          </header>

          {/* Page content */}
          <main className="flex-1 min-w-0 overflow-auto">
            <div
              className="mx-auto max-w-6xl px-4 sm:px-6 py-6 page-enter"
              style={{ paddingBottom: "calc(var(--bottom-nav-height, 0px) + 24px)" }}
            >
              {children}
            </div>
          </main>

          {/* Mobile bottom nav is now provided by
              `<MobileBottomNav />` (Item 12) — mounted inside the app
              layout so it can live alongside the FAB + quick-action sheet. */}
        </div>
      </div>

      <CommandPalette />
      <AiChat />
      <PwaInstallBanner />
      <SessionTimeoutModal />
    </>
  );
}
