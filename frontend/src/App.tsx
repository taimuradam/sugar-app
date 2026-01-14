import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  LogOut,
  Building2,
  Receipt,
  LineChart,
  Loader2,
  Download,
  Users,
  Trash2,
  Plus,
  ClipboardList,
  ChevronDown,
  User,
} from "lucide-react";
import * as api from "./api";
import { Banner, Button, Card, CardBody, CardHeader, Input, Label, Select, Table, Td, Th, cx, useConfirm, useToast, Progress } from "./ui";

type Tab = "ledger" | "transactions" | "loans" | "users" | "audit";

const KARACHI_TZ = "Asia/Karachi";

function karachiTodayParts(base: Date = new Date()) {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: KARACHI_TZ,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(base);

  const get = (t: string) => parts.find((p) => p.type === t)?.value ?? "";
  return { yyyy: get("year"), mm: get("month"), dd: get("day") };
}

function karachiTodayISO(base: Date = new Date()) {
  const { yyyy, mm, dd } = karachiTodayParts(base);
  return `${yyyy}-${mm}-${dd}`;
}

function karachiMonthStartISO(base: Date = new Date()) {
  const { yyyy, mm } = karachiTodayParts(base);
  return `${yyyy}-${mm}-01`;
}

function shiftISODate(iso: string, deltaDays: number) {
  const [y, m, d] = iso.split("-").map((x) => Number(x));
  const t = Date.UTC(y, m - 1, d) + deltaDays * 24 * 60 * 60 * 1000;
  const dt = new Date(t);
  const yyyy = dt.getUTCFullYear();
  const mm = String(dt.getUTCMonth() + 1).padStart(2, "0");
  const dd = String(dt.getUTCDate()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}`;
}

function isoToUTCDate(iso: string) {
  const [y, m, d] = iso.split("-").map((x) => Number(x));
  return new Date(Date.UTC(y, m - 1, d));
}

function fmtMoney(n: number) {
  if (Number.isNaN(n)) return "-";
  return new Intl.NumberFormat(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(n);
}

function fmtRate(n: number | null | undefined) {
  if (n === null || n === undefined || Number.isNaN(n)) return "-";
  return new Intl.NumberFormat(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(n);
}

function fmtScopeRange(start: string, end: string) {
  const a = isoToUTCDate(start);
  const b = isoToUTCDate(end);
  if (Number.isNaN(a.getTime()) || Number.isNaN(b.getTime())) return `${start}–${end}`;

  const sameYear =
    new Intl.DateTimeFormat("en-CA", { timeZone: KARACHI_TZ, year: "numeric" }).format(a) ===
    new Intl.DateTimeFormat("en-CA", { timeZone: KARACHI_TZ, year: "numeric" }).format(b);

  const left = new Intl.DateTimeFormat(undefined, {
    timeZone: KARACHI_TZ,
    month: "short",
    day: "numeric",
    ...(sameYear ? {} : { year: "numeric" }),
  }).format(a);

  const right = new Intl.DateTimeFormat(undefined, {
    timeZone: KARACHI_TZ,
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(b);

  return `${left}–${right}`;
}

function readStoredDateRange(key: string): { start: string; end: string } | null {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return null;
    const j = JSON.parse(raw);
    const s = typeof j?.start === "string" ? j.start : "";
    const e = typeof j?.end === "string" ? j.end : "";
    if (s.length !== 10 || e.length !== 10) return null;
    return { start: s, end: e };
  } catch {
    return null;
  }
}

function writeStoredDateRange(key: string, start: string, end: string) {
  try {
    localStorage.setItem(key, JSON.stringify({ start, end }));
  } catch {}
}

function readStoredDate(key: string): string | null {
  try {
    const v = localStorage.getItem(key);
    if (!v || v.length !== 10) return null;
    return v;
  } catch {
    return null;
  }
}

function writeStoredDate(key: string, value: string) {
  try {
    localStorage.setItem(key, value);
  } catch {}
}

function BankTypeBadge({
  bankType,
  size = "md",
  className,
}: {
  bankType: string | undefined | null;
  size?: "sm" | "md";
  className?: string;
}) {
  const t = (bankType || "").trim().toLowerCase();
  const label = t === "islamic" ? "Islamic" : "Conventional";

  const sizeCls = size === "sm" ? "px-2 py-0.5 text-[11px]" : "px-2.5 py-1 text-xs";

  const cls =
    t === "islamic"
      ? cx(
          "inline-flex items-center rounded-full border border-emerald-200 bg-emerald-50 font-semibold text-emerald-700",
          sizeCls,
          className
        )
      : cx(
          "inline-flex items-center rounded-full border border-indigo-200 bg-indigo-50 font-semibold text-indigo-700",
          sizeCls,
          className
        );

  return <span className={cls}>{label}</span>;
}

function Pill(props: { kind?: "neutral" | "info" | "warning" | "danger"; title?: string; children: React.ReactNode }) {
  const kind = props.kind ?? "neutral";
  const cls =
    kind === "danger"
      ? "border-rose-200 bg-rose-50 text-rose-800"
      : kind === "warning"
      ? "border-amber-200 bg-amber-50 text-amber-900"
      : kind === "info"
      ? "border-sky-200 bg-sky-50 text-sky-900"
      : "border-slate-200 bg-slate-50 text-slate-700";
  return (
    <span
      title={props.title}
      className={cx("inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-semibold", cls)}
    >
      {props.children}
    </span>
  );
}

export default function App() {
  const [role, setRole] = useState(() => api.getRole());
  const [error, setError] = useState<string>("");

  const [tokenReady, setTokenReady] = useState(() => !!localStorage.getItem("token"));
  const [tab, setTab] = useState<Tab>("ledger");

  const [banks, setBanks] = useState<api.BankOut[]>([]);
  const [selectedBankId, setSelectedBankId] = useState<number>(0);
  const [loans, setLoans] = useState<api.LoanOut[]>([]);
  const [selectedLoanId, setSelectedLoanId] = useState<number>(0);

  const [ratesByBank, setRatesByBank] = useState<Record<number, api.RateOut[]>>({});
  const [ratesLoadError, setRatesLoadError] = useState<string>("");

  const [scopeBackfillStatus, setScopeBackfillStatus] = useState<api.BackfillStatus | null>(null);

  // Show a temporary "Fetching KIBOR..." pill while a new principal debit transaction triggers a KIBOR scrape.
  const [kiborTxScrapeRunning, setKiborTxScrapeRunning] = useState(false);
  const kiborTxScrapeStartedAtRef = useRef<number>(0);
  const kiborTxScrapeHideTimerRef = useRef<number | null>(null);

  const setKiborTxScrapeBusy = (busy: boolean) => {
    if (busy) {
      if (kiborTxScrapeHideTimerRef.current != null) {
        window.clearTimeout(kiborTxScrapeHideTimerRef.current);
        kiborTxScrapeHideTimerRef.current = null;
      }
      kiborTxScrapeStartedAtRef.current = Date.now();
      setKiborTxScrapeRunning(true);
      return;
    }

    const elapsed = Date.now() - (kiborTxScrapeStartedAtRef.current || Date.now());
    const minMs = 800; // avoids a distracting “flash” if it returns instantly
    const delay = Math.max(0, minMs - elapsed);

    if (kiborTxScrapeHideTimerRef.current != null) {
      window.clearTimeout(kiborTxScrapeHideTimerRef.current);
      kiborTxScrapeHideTimerRef.current = null;
    }

    if (delay === 0) {
      setKiborTxScrapeRunning(false);
      return;
    }

    kiborTxScrapeHideTimerRef.current = window.setTimeout(() => {
      setKiborTxScrapeRunning(false);
      kiborTxScrapeHideTimerRef.current = null;
    }, delay);
  };

  const defaultScopeEnd = karachiTodayISO();
  const defaultScopeStart = karachiMonthStartISO();
  const { yyyy } = karachiTodayParts();

  const scopeKey = `filters:scope:global`;
  const [scopeStart, setScopeStart] = useState(() => readStoredDateRange(scopeKey)?.start ?? defaultScopeStart);
  const [scopeEnd, setScopeEnd] = useState(() => readStoredDateRange(scopeKey)?.end ?? defaultScopeEnd);

  const [draftScopeStart, setDraftScopeStart] = useState(() => readStoredDateRange(scopeKey)?.start ?? defaultScopeStart);
  const [draftScopeEnd, setDraftScopeEnd] = useState(() => readStoredDateRange(scopeKey)?.end ?? defaultScopeEnd);

  useEffect(() => {
    setDraftScopeStart(scopeStart);
    setDraftScopeEnd(scopeEnd);
  }, [scopeStart, scopeEnd]);

  const scopeInvalid = !!draftScopeStart && !!draftScopeEnd && draftScopeStart > draftScopeEnd;
  const scopeHasPending = draftScopeStart !== scopeStart || draftScopeEnd !== scopeEnd;

  useEffect(() => {
    writeStoredDateRange(scopeKey, scopeStart, scopeEnd);
  }, [scopeKey, scopeStart, scopeEnd]);

  useEffect(() => {
    if (!scopeHasPending) return;
    if (scopeInvalid) return;
    const t = window.setTimeout(() => {
      setScopeStart(draftScopeStart);
      setScopeEnd(draftScopeEnd);
    }, 300);
    return () => window.clearTimeout(t);
  }, [draftScopeStart, draftScopeEnd, scopeHasPending, scopeInvalid]);

  const [refreshTick, setRefreshTick] = useState(0);
  const [pendingScrollToAddTx, setPendingScrollToAddTx] = useState(false);

  const [exportingReport, setExportingReport] = useState(false);
  const [exportBackfillStatus, setExportBackfillStatus] = useState<api.BackfillStatus | null>(null);
  const exportPendingRef = React.useRef(false);

  useEffect(() => {
    if (tab !== "transactions") return;
    if (!pendingScrollToAddTx) return;
    setPendingScrollToAddTx(false);
    requestAnimationFrame(() => {
      document.getElementById("add-transaction")?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }, [tab, pendingScrollToAddTx]);

  const [transactionsVersion, setTransactionsVersion] = useState(0);
  const bumpTransactionsVersion = () => setTransactionsVersion((v) => v + 1);
  const [loadingLoans, setLoadingLoans] = useState(false);
  const [loadingBanks, setLoadingBanks] = useState(false);

  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const userMenuRef = React.useRef<HTMLDivElement | null>(null);

  const [presetsOpen, setPresetsOpen] = useState(false);
  const presetsRef = React.useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    function onDocMouseDown(e: MouseEvent) {
      if (!userMenuOpen) return;
      const el = userMenuRef.current;
      if (!el) return;
      if (e.target instanceof Node && !el.contains(e.target)) setUserMenuOpen(false);
    }

    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") setUserMenuOpen(false);
    }

    document.addEventListener("mousedown", onDocMouseDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onDocMouseDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [userMenuOpen]);

  useEffect(() => {
    function onDocMouseDown(e: MouseEvent) {
      if (!presetsOpen) return;
      const el = presetsRef.current;
      if (!el) return;
      if (e.target instanceof Node && !el.contains(e.target)) setPresetsOpen(false);
    }

    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") setPresetsOpen(false);
    }

    document.addEventListener("mousedown", onDocMouseDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onDocMouseDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [presetsOpen]);

  const isAdmin = role === "admin";

  const toast = useToast();
  const confirm = useConfirm();

  async function refreshBanks(pickFirst = false) {
    setLoadingBanks(true);
    try {
      const list = await api.listBanks();
      setBanks(list);
      if (pickFirst && list.length) setSelectedBankId(list[0].id);
      if (!selectedBankId && list.length) setSelectedBankId(list[0].id);
    } catch (e: any) {
      setError(e?.message || "failed_to_load_banks");
    } finally {
      setLoadingBanks(false);
    }
  }

  async function refreshLoans(bankId: number, pickFirst = false) {
    if (!bankId) {
      setLoans([]);
      setSelectedLoanId(0);
      return;
    }
    setLoadingLoans(true);
    try {
      const list = (await api.listLoans(bankId)) as api.LoanOut[];
      setLoans(list);

      if (pickFirst) {
        setSelectedLoanId(list.length ? list[0].id : 0);
      } else if (selectedLoanId && !list.some((l) => l.id === selectedLoanId)) {
        setSelectedLoanId(list.length ? list[0].id : 0);
      }
    } catch (e: any) {
      toast.error(e?.message || "Failed to load loans");
      setLoans([]);
      setSelectedLoanId(0);
    } finally {
      setLoadingLoans(false);
    }
  }

  async function refreshScope() {
    setRefreshTick((t) => t + 1);
    if (selectedBankId) {
      await refreshBanks(false);
      await refreshLoans(selectedBankId, false);
    }
  }

  const exportBackfillPct =
    exportBackfillStatus && exportBackfillStatus.status === "running" && exportBackfillStatus.total_days > 0
      ? Math.min(100, Math.round((exportBackfillStatus.processed_days / exportBackfillStatus.total_days) * 100))
      : 0;

  async function exportReport() {
    if (!selectedBankId || !selectedLoanId) return;
    if (scopeInvalid) return;

    setError("");
    setExportingReport(true);
    try {
      exportPendingRef.current = false;
      setExportBackfillStatus(null);

      const safePart = (v: string) =>
        (v || "")
          .trim()
          .replace(/\s+/g, "_")
          .replace(/[^A-Za-z0-9._-]+/g, "_")
          .replace(/_+/g, "_")
          .replace(/^_+|_+$/g, "")
          .slice(0, 40) || "unknown";

      const bankName = banks.find((b) => b.id === selectedBankId)?.name || `bank_${selectedBankId}`;
      const loanName = loans.find((l) => l.id === selectedLoanId)?.name || `loan_${selectedLoanId}`;
      const filename = `${safePart(bankName)}_${safePart(loanName)}_${scopeStart}_to_${scopeEnd}.xlsx`;

      await api.downloadReport(selectedBankId, selectedLoanId, scopeStart, scopeEnd, filename);
      toast.success("Report downloaded");
    } catch (e: any) {
      if (e?.name === "BackfillRunningError") {
        exportPendingRef.current = true;
        setExportBackfillStatus(e.status);
        toast.info("Preparing report… backfilling KIBOR rates first.");
      } else {
        setError(e?.message || "failed_to_download_report");
      }
    } finally {
      setExportingReport(false);
    }
  }

  useEffect(() => {
    if (!exportBackfillStatus || exportBackfillStatus.status !== "running") return;

    let cancelled = false;
    const id = window.setInterval(async () => {
      try {
        const st = await api.getBackfillStatus(selectedBankId, selectedLoanId);
        if (cancelled) return;
        setExportBackfillStatus(st);

        if (st.status !== "running") {
          window.clearInterval(id);
          if (!cancelled && exportPendingRef.current && (st.status === "done" || st.status === "idle")) {
            exportPendingRef.current = false;
            void exportReport();
          }
        }
      } catch {
        // ignore
      }
    }, 1000);

    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [exportBackfillStatus?.status, selectedBankId, selectedLoanId, scopeStart, scopeEnd]);

  function toISODate(d: Date) {
    const yyyy = d.getFullYear();
    const mm = String(d.getMonth() + 1).padStart(2, "0");
    const dd = String(d.getDate()).padStart(2, "0");
    return `${yyyy}-${mm}-${dd}`;
  }

  function presetRange(start: string, end: string) {
    setDraftScopeStart(start);
    setDraftScopeEnd(end);
    setScopeStart(start);
    setScopeEnd(end);
  }

  async function presetAllTime() {
    if (!selectedBankId || !selectedLoanId) {
      presetRange(defaultScopeStart, defaultScopeEnd);
      return;
    }
    try {
      const b = await api.loanDateBounds(selectedBankId, selectedLoanId);
      const start = b?.min_date || defaultScopeStart;
      const end = defaultScopeEnd;
      presetRange(start, end);
    } catch {
      presetRange(defaultScopeStart, defaultScopeEnd);
    }
  }

  useEffect(() => {
    if (!tokenReady) return;
    refreshBanks(true);
    const t = window.setInterval(() => {
      refreshBanks(false);
    }, 60 * 60 * 1000);
    return () => window.clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tokenReady]);

  useEffect(() => {
    if (!tokenReady) return;
    refreshLoans(selectedBankId, true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tokenReady, selectedBankId]);

  useEffect(() => {
    let cancelled = false;

    async function loadRates() {
      if (!tokenReady || !selectedBankId) return;
      setRatesLoadError("");
      try {
        const rs = await api.listRates(selectedBankId);
        if (cancelled) return;
        setRatesByBank((prev) => ({ ...prev, [selectedBankId]: rs }));
      } catch {
        if (cancelled) return;
        setRatesLoadError("Failed to load KIBOR rates.");
      }
    }

    void loadRates();
    return () => {
      cancelled = true;
    };
  }, [tokenReady, selectedBankId]);

  useEffect(() => {
    let cancelled = false;
    let id: number | null = null;

    async function tick() {
      if (!tokenReady || !selectedBankId || !selectedLoanId) {
        setScopeBackfillStatus(null);
        return;
      }
      try {
        const st = await api.getBackfillStatus(selectedBankId, selectedLoanId);
        if (cancelled) return;
        setScopeBackfillStatus(st);
      } catch {
        if (cancelled) return;
        setScopeBackfillStatus(null);
      }
    }

    void tick();
    if (tokenReady && selectedBankId && selectedLoanId) {
      id = window.setInterval(tick, 5000);
    }

    return () => {
      cancelled = true;
      if (id) window.clearInterval(id);
    };
  }, [tokenReady, selectedBankId, selectedLoanId]);

  const selectedBank = useMemo(() => banks.find((b) => b.id === selectedBankId) || null, [banks, selectedBankId]);
  const selectedLoan = useMemo(() => loans.find((l) => l.id === selectedLoanId) || null, [loans, selectedLoanId]);

    const [loanUsedPrincipal, setLoanUsedPrincipal] = useState<number | null>(null);
    const [loanUsedLoading, setLoanUsedLoading] = useState(false);

    useEffect(() => {
      let cancelled = false;

      async function loadUsedPrincipal() {
        if (!tokenReady || !selectedBankId || !selectedLoanId) {
          setLoanUsedPrincipal(null);
          return;
        }

        setLoanUsedLoading(true);

        try {
          const bal = await api.loanBalance(selectedBankId, selectedLoanId);
          if (!cancelled) setLoanUsedPrincipal(bal.principal_balance ?? 0);
        } catch {
          if (!cancelled) setLoanUsedPrincipal(null);
        } finally {
          if (!cancelled) setLoanUsedLoading(false);
        }
      }

      loadUsedPrincipal();
      return () => {
        cancelled = true;
      };
    }, [tokenReady, selectedBankId, selectedLoanId, transactionsVersion]);

    const loanLimit = selectedLoan?.max_loan_amount ?? null;
    const loanRemaining =
      loanLimit != null && loanUsedPrincipal != null ? Math.max(0, loanLimit - loanUsedPrincipal) : null;

    const loanUtilPct =
      loanLimit != null && loanUsedPrincipal != null && loanLimit > 0
        ? Math.min(100, Math.round((loanUsedPrincipal / loanLimit) * 100))
        : 0;


    const utilAlertKind: "info" | "warning" | "danger" | null =
      loanLimit != null && loanUsedPrincipal != null && loanLimit > 0
        ? loanUtilPct >= 95
          ? "danger"
          : loanUtilPct >= 85
          ? "warning"
          : loanUtilPct >= 70
          ? "info"
          : null
        : null;

    const utilAlertTitle =
      loanLimit != null && loanUsedPrincipal != null ? `Used ${fmtMoney(loanUsedPrincipal)} of ${fmtMoney(loanLimit)}` : undefined;

    const ratesForBank = selectedBankId ? ratesByBank[selectedBankId] ?? null : null;
    const ratesForTenor =
      ratesForBank && selectedLoan
        ? ratesForBank
            .filter((r) => Number(r.tenor_months) === Number(selectedLoan.kibor_tenor_months))
            .slice()
            .sort((a, b) => a.effective_date.localeCompare(b.effective_date))
        : null;

    const placeholderRate = selectedLoan ? Number(selectedLoan.kibor_placeholder_rate_percent ?? 0) : 0;

    const kiborAlert: { kind: "warning" | "danger"; text: string; title?: string } | null = (() => {
      if (!selectedLoanId || !selectedLoan) return null;
      if (!ratesForTenor) return null;

      if (!ratesForTenor.length) {
        return {
          kind: "danger",
          text: "No KIBOR — using placeholder",
          title: `No rates found for ${selectedLoan.kibor_tenor_months}M. Placeholder: ${fmtRate(placeholderRate)}%`,
        };
      }

      const first = ratesForTenor[0];
      if (first && first.effective_date > scopeStart) {
        return {
          kind: "warning",
          text: "Placeholder rate in range",
          title: `Using placeholder (${fmtRate(placeholderRate)}%) until ${first.effective_date}.`,
        };
      }

      return null;
    })();

    const backfillAlert: { kind: "info" | "danger"; text: string; title?: string } | null = (() => {
      if (!scopeBackfillStatus) return null;
      if (scopeBackfillStatus.status === "running") {
        const pct =
          scopeBackfillStatus.total_days > 0
            ? Math.min(100, Math.round((scopeBackfillStatus.processed_days / scopeBackfillStatus.total_days) * 100))
            : 0;
        return {
          kind: "info",
          text: `Backfill running · ${pct}%`,
          title: `${scopeBackfillStatus.processed_days}/${scopeBackfillStatus.total_days} days processed`,
        };
      }
      if (scopeBackfillStatus.status === "error") {
        return { kind: "danger", text: "Backfill error", title: scopeBackfillStatus.message ?? undefined };
      }
      return null;
    })();

    const hasScopeAlerts = !!utilAlertKind || !!kiborAlert || !!backfillAlert || !!ratesLoadError || kiborTxScrapeRunning;

  if (!tokenReady) {
    return (
      <div className="min-h-screen bg-slate-50">
        <div className="mx-auto max-w-5xl px-4 py-14">
          <div className="grid w-full grid-cols-1 gap-6 md:grid-cols-2">
            <div className="flex flex-col justify-center">
              <div className="text-sm font-semibold text-slate-500">Sugar App</div>
              <div className="mt-2 text-4xl font-semibold tracking-tight text-slate-900">Finance dashboard</div>
              <div className="mt-3 text-slate-600">Login to test: banks, rates, transactions, ledger, and Excel exports.</div>
              <div className="mt-6 rounded-2xl border border-slate-200 bg-white p-4 text-sm text-slate-700">
                Backend should be at <span className="font-mono">http://127.0.0.1:8000</span> (Swagger:{" "}
                <span className="font-mono">/docs</span>)
              </div>
            </div>

            <LoginCard
              error={error}
              onError={setError}
              onLogin={(r) => {
                setRole(r);
                setTokenReady(true);
              }}
            />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <div className="top-0 z-40 border-b border-slate-200/70 bg-slate-50/80 backdrop-blur supports-[backdrop-filter]:bg-slate-50/70">
        <div className="mx-auto max-w-6xl px-4 py-3">
          <div className="rounded-3xl border border-slate-200 bg-white shadow-sm shadow-slate-200/40">
            <div className="px-4 py-3">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  <div className="rounded-2xl border border-slate-200 bg-white p-3">
                    <Building2 className="h-5 w-5 text-slate-700" />
                  </div>
                  <div className="leading-tight">
                    <div className="text-sm font-semibold text-slate-900">Finance dashboard</div>
                  </div>
                </div>

                <div className="flex shrink-0 items-center gap-2">
                  <div className="relative" ref={userMenuRef}>
                    <button
                      type="button"
                      onClick={() => setUserMenuOpen((v) => !v)}
                      className="inline-flex items-center gap-2 rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-800 hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-slate-200"
                      aria-haspopup="menu"
                      aria-expanded={userMenuOpen}
                    >
                      <span className="inline-flex h-8 w-8 items-center justify-center rounded-2xl bg-slate-900 text-white">
                        <User className="h-4 w-4" />
                      </span>
                      <div className="flex flex-col items-start leading-tight">
                        <span className="font-mono text-xs">{role === "user" ? "viewer" : role}</span>
                      </div>
                      <ChevronDown className={cx("h-4 w-4 text-slate-500 transition", userMenuOpen && "rotate-180")} />
                    </button>

                    {userMenuOpen ? (
                      <div
                        role="menu"
                        className="absolute right-0 z-50 mt-2 w-56 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-lg shadow-slate-200/60"
                      >
                        <div className="px-4 py-3">
                          <div className="text-xs font-semibold text-slate-900">Account</div>
                          <div className="mt-1 text-xs text-slate-500">
                            Role: <span className="font-mono">{role === "user" ? "viewer" : role}</span>
                          </div>
                        </div>
                        <div className="h-px bg-slate-100" />
                        <button
                          role="menuitem"
                          className="flex w-full items-center gap-2 px-4 py-3 text-left text-sm font-semibold text-rose-700 hover:bg-rose-50"
                          onClick={() => {
                            setUserMenuOpen(false);
                            api.clearToken();
                            setTokenReady(false);
                            setRole("");
                          }}
                        >
                          <LogOut className="h-4 w-4" />
                          Logout
                        </button>
                      </div>
                    ) : null}
                  </div>
                </div>
              </div>

              <div className="mt-3 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1.1fr_1.1fr_1.6fr_auto] lg:items-center">
                  {/* Bank */}
                  <div className="min-w-0">
                    <Label className="mb-0.5">Bank</Label>
                    <Select
                      value={selectedBankId ? String(selectedBankId) : ""}
                      onChange={(e) => setSelectedBankId(Number(e.target.value))}
                      disabled={loadingBanks || !banks.length}
                    >
                      {!banks.length ? <option value="">No banks</option> : null}
                      {banks.map((b) => (
                        <option key={b.id} value={String(b.id)}>
                          {b.name}
                        </option>
                      ))}
                    </Select>
                  </div>

                  {/* Loan */}
                  <div className="min-w-0">
                    <Label className="mb-0.5">Loan</Label>
                    <Select
                      value={selectedLoanId ? String(selectedLoanId) : ""}
                      onChange={(e) => setSelectedLoanId(Number(e.target.value))}
                      disabled={loadingLoans || !loans.length || !selectedBankId}
                    >
                      {!selectedBankId ? <option value="">Select a bank first</option> : null}
                      {selectedBankId && !loans.length ? <option value="">No loans</option> : null}
                      {loans.map((l) => (
                        <option key={l.id} value={String(l.id)}>
                          {l.name}
                        </option>
                      ))}
                    </Select>
                  </div>

                  {/* Date range */}
                  <div className="min-w-0 items-center">
                    <div className="flex items-end justify-between gap-3">
                      <Label className="mb-1">Date range</Label>
                      {scopeHasPending && !scopeInvalid ? <span className="text-[11px] text-slate-500">Updating…</span> : null}
                    </div>

                    <div className="grid grid-cols-1 gap-2 sm:grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] sm:items-center">
                      <Input
                        className="tabular-nums"
                        type="date"
                        value={draftScopeStart}
                        onChange={(e) => setDraftScopeStart(e.target.value)}
                        error={scopeInvalid ? " " : undefined}
                      />

                      <div className="hidden select-none items-center justify-center text-xs text-slate-400 sm:flex">→</div>

                      <Input
                        className="tabular-nums"
                        type="date"
                        value={draftScopeEnd}
                        onChange={(e) => setDraftScopeEnd(e.target.value)}
                        error={scopeInvalid ? "Start must be ≤ end" : undefined}
                      />
                    </div>

                    {/* Presets */}
                    <div className="mt-2 flex w-full flex-wrap items-center justify-center gap-2">
                      <div className="inline-flex overflow-hidden rounded-2xl border border-slate-200 bg-white">
                        <button
                          type="button"
                          className="px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
                          onClick={() => presetRange(defaultScopeStart, defaultScopeEnd)}
                        >
                          This month
                        </button>

                        <div className="w-px bg-slate-200" />

                        <button
                          type="button"
                          className="px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
                          onClick={() => {
                            presetRange(shiftISODate(defaultScopeEnd, -29), defaultScopeEnd);
                          }}
                        >
                          Last 30 days
                        </button>

                        <div className="w-px bg-slate-200" />

                        <button
                          type="button"
                          className="px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
                          onClick={() => presetRange(`${yyyy}-01-01`, defaultScopeEnd)}
                        >
                          YTD
                        </button>

                        <div className="w-px bg-slate-200" />

                        <button
                          type="button"
                          className={cx(
                            "px-3 py-2 text-xs font-semibold hover:bg-slate-50",
                            !selectedLoanId ? "cursor-not-allowed text-slate-400" : "text-slate-700"
                          )}
                          disabled={!selectedLoanId}
                          onClick={() => void presetAllTime()}
                        >
                          All time
                        </button>
                      </div>

                      {scopeInvalid ? (
                        <span className="text-xs font-medium text-rose-600">Fix the date range to refresh.</span>
                      ) : null}
                    </div>
                  </div>
                  
                  {hasScopeAlerts ? (
                    <div className="mt-2 flex w-full flex-wrap items-start justify-center gap-2">
                      {utilAlertKind ? (
                        <div className="flex flex-col items-center gap-2">
                          <Pill kind={utilAlertKind} title={utilAlertTitle}>
                            Utilization {loanUtilPct}%
                          </Pill>

                          {kiborTxScrapeRunning ? (
                            <Pill kind="info" title="Fetching KIBOR rate for the new transaction…">
                              <Loader2 className="h-3.5 w-3.5 animate-spin" />
                              Fetching rates…
                            </Pill>
                          ) : null}
                        </div>
                      ) : kiborTxScrapeRunning ? (
                        <Pill kind="info" title="Fetching KIBOR rate for the new transaction…">
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                          Fetching KIBOR…
                        </Pill>
                      ) : null}

                      {kiborAlert ? (
                        <Pill kind={kiborAlert.kind} title={kiborAlert.title}>
                          {kiborAlert.text}
                        </Pill>
                      ) : null}

                      {backfillAlert ? (
                        <Pill kind={backfillAlert.kind} title={backfillAlert.title}>
                          {backfillAlert.text}
                        </Pill>
                      ) : null}

                      {ratesLoadError ? (
                        <Pill kind="warning" title={ratesLoadError}>
                          KIBOR status unavailable
                        </Pill>
                      ) : null}
                    </div>
                  ) : null}

                  {/* Actions */}
                  <div className="flex items-center justify-start gap-2 lg:justify-end">
                    <Button
                      size="sm"
                      kind="secondary"
                      type="button"
                      onClick={() => void exportReport()}
                      disabled={!selectedLoanId || scopeInvalid || exportingReport || exportBackfillStatus?.status === "running"}
                      title={!selectedLoanId ? "Select a loan to export" : "Download XLSX for the current scope"}
                    >
                      <Download className="h-4 w-4" />
                      {exportBackfillStatus?.status === "running"
                        ? `Backfilling… ${exportBackfillPct}%`
                        : exportingReport
                        ? "Preparing..."
                        : "Download XLSX"}
                    </Button>

                    <Button
                      size="sm"
                      kind="secondary"
                      type="button"
                      onClick={refreshScope}
                      disabled={scopeInvalid || scopeHasPending}
                    >
                      Refresh
                    </Button>
                  </div>
                </div>
              </div>

              <div
                className="mt-3 flex min-w-0 items-center gap-2 rounded-2xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700"
                title={
                  selectedBank && selectedLoan
                    ? `Viewing: ${selectedBank.name} (${selectedBank.bank_type}) → Loan: ${selectedLoan.name} → ${fmtScopeRange(scopeStart, scopeEnd)}`
                    : "Viewing: —"
                }
              >
                <span className="text-slate-500">Viewing:</span>
                {selectedBank && selectedLoan ? (
                  <span className="min-w-0 truncate">
                    <span className="font-semibold text-slate-900">{selectedBank.name}</span>
                    <span className="ml-2 inline-flex align-middle">
                      <BankTypeBadge bankType={selectedBank.bank_type} size="sm" />
                    </span>
                    <span className="text-slate-400"> → </span>
                    <span className="font-semibold text-slate-900">Loan: {selectedLoan.name}</span>
                    <span className="text-slate-400"> → </span>
                    <span className="font-semibold text-slate-900">{fmtScopeRange(scopeStart, scopeEnd)}</span>
                  </span>
                ) : (
                  <span className="text-slate-500">—</span>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-6xl px-4 py-6">

        <div className="mt-6">{error ? <Banner kind="error" text={error} onClose={() => setError("")} /> : null}</div>

        <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-[260px_1fr]">
          <div className="space-y-3">
            <NavButton active={tab === "ledger"} onClick={() => setTab("ledger")} icon={<LineChart className="h-4 w-4" />} text="Ledger" />
            <NavButton active={tab === "transactions"} onClick={() => setTab("transactions")} icon={<Receipt className="h-4 w-4" />} text="Transactions" />
            <NavButton active={tab === "loans"} onClick={() => setTab("loans")} icon={<ClipboardList className="h-4 w-4" />} text="Loans" />
            {isAdmin ? <NavButton active={tab === "users"} onClick={() => setTab("users")} icon={<Users className="h-4 w-4" />} text="Users" /> : null}
            {isAdmin ? (
              <NavButton
                active={tab === "audit"}
                onClick={() => setTab("audit")}
                icon={<ClipboardList className="h-4 w-4" />}
                text="Audit log"
              />
            ) : null}

            <Card>
              <CardBody>
                {!selectedBank ? (
                  <div className="text-sm text-slate-600">No bank selected.</div>
                ) : (
                  <div className="space-y-3 text-sm">
                    {/* Bank name + badge + loan count + actions */}
                    <div className="group flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <div className="truncate text-lg font-semibold text-slate-900">{selectedBank.name}</div>

                          {/* Actions (subtle) */}
                          {isAdmin ? (
                            <button
                              type="button"
                              title="Delete bank"
                              className="ml-1 inline-flex h-9 w-9 items-center justify-center rounded-xl border border-transparent text-slate-400 opacity-40 transition hover:border-rose-200 hover:bg-rose-50 hover:text-rose-600 focus:opacity-100 focus:outline-none focus:ring-2 focus:ring-rose-200 group-hover:opacity-100"
                              onClick={async () => {
                                const ok = await confirm({
                                  title: "Delete bank?",
                                  body: `This will permanently delete “${selectedBank.name}” and all its loans, transactions, and rates.`,
                                  confirmText: "Delete bank",
                                  danger: true,
                                });
                                if (!ok) return;

                                try {
                                  await api.deleteBank(selectedBank.id);
                                  setSelectedLoanId(0);
                                  setLoans([]);
                                  await refreshBanks(true);
                                  toast.success("Bank deleted");
                                } catch (e: any) {
                                  toast.error(e?.message || "Failed to delete bank");
                                }
                              }}
                            >
                              <span className="sr-only">Delete bank</span>
                              <Trash2 className="h-4 w-4" />
                            </button>
                          ) : null}
                        </div>

                        <div className="mt-2 flex items-center gap-2">
                          <BankTypeBadge bankType={selectedBank.bank_type} />
                          <span className="text-xs text-slate-500">
                            {(loans?.length ?? 0)} loan{(loans?.length ?? 0) === 1 ? "" : "s"}
                          </span>
                        </div>
                      </div>
                    </div>

                    <div className="mt-3 pt-3 border-t border-slate-100">
                      <div className="mb-2 flex items-center gap-2">
                        <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Selected loan</div>
                        <div className="h-px flex-1 bg-slate-100" />
                      </div>

                      {!selectedLoan ? (
                        <div className="text-sm text-slate-600">No loan selected.</div>
                      ) : (
                        <div className="space-y-2">
                          <div className="flex justify-between">
                            <div className="text-slate-600">Name</div>
                            <div className="font-mono">{selectedLoan.name}</div>
                          </div>

                          <div className="flex justify-between">
                            <div className="text-slate-600">KIBOR tenor</div>
                            <div className="font-mono">{selectedLoan.kibor_tenor_months === 12 ? "1y" : `${selectedLoan.kibor_tenor_months}m`}</div>
                          </div>

                          <div className="flex justify-between">
                            <div className="text-slate-600">Spread</div>
                            <div className="font-mono">{selectedLoan.additional_rate ?? 0}</div>
                          </div>

                          <div className="flex justify-between">
                            <div className="text-slate-600">Max loan</div>
                            <div className="font-mono">
                              {selectedLoan.max_loan_amount == null ? "—" : fmtMoney(selectedLoan.max_loan_amount)}
                            </div>
                          </div>
                            <div className="mt-3 pt-3 border-t border-slate-100 space-y-2">
                              <div className="flex justify-between">
                                <div className="text-slate-600">Used</div>
                                <div className="font-mono">
                                  {loanUsedLoading ? "…" : loanUsedPrincipal == null ? "—" : fmtMoney(loanUsedPrincipal)}
                                </div>
                              </div>

                              <div className="flex justify-between">
                                <div className="text-slate-600">Remaining</div>
                                <div className="font-mono">
                                  {loanLimit == null || loanUsedPrincipal == null ? "—" : fmtMoney(loanRemaining ?? 0)}
                                </div>
                              </div>

                              {loanLimit == null ? null : (
                                <div className="pt-1">
                                  {scopeBackfillStatus?.status === "running" ? (
                                    <div className="mb-2 text-xs text-slate-500">Backfill running — numbers may change as rates load.</div>
                                  ) : null}

                                  <Progress value={loanUtilPct}/>
                                </div>
                              )}
                            </div>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </CardBody>
            </Card>

              {isAdmin ? (
                <CreateBankCard
                  onCreated={async (b) => {
                    setSelectedBankId(b.id);
                    setTab("loans");
                    await refreshBanks(false);
                    await refreshLoans(b.id, true);
                  }}
                  onError={setError}
                />
              ) : null}
          </div>

          <div>
            {!banks.length ? (
              <Card>
                <CardHeader title="No banks yet" subtitle="Create your first bank to begin testing." />
                <CardBody>
                  <div className="text-sm text-slate-600">
                    Use the “Create bank” card on the left (admin only).
                  </div>
                </CardBody>
              </Card>
            ) : !selectedBankId ? (
              <Card>
                <CardHeader title="No bank selected" subtitle="Pick a bank from the dropdown." />
                <CardBody />
              </Card>
            ) : tab === "ledger" ? (
              !selectedLoanId ? (
                <Card>
                  <CardHeader title="Select a loan" subtitle="Ledger is calculated per-loan." />
                  <CardBody />
                </Card>
              ) : (
                <Ledger
                  bankId={selectedBankId}
                  loanId={selectedLoanId}
                  start={scopeStart}
                  end={scopeEnd}
                  refreshTick={refreshTick}
                  onError={setError}
                />
              )
            ) : tab === "transactions" ? (
              !selectedLoanId ? (
                <Card>
                  <CardHeader title="Select a loan" subtitle="Transactions are recorded per-loan." />
                  <CardBody />
                </Card>
              ) : (
                <Transactions
                  bankId={selectedBankId}
                  loanId={selectedLoanId}
                  start={scopeStart}
                  end={scopeEnd}
                  refreshTick={refreshTick}
                  role={role}
                  onError={setError}
                  onKiborScrapeBusy={setKiborTxScrapeBusy}
                  onTransactionsChanged={async () => {
                    await refreshBanks(false);
                    await refreshLoans(selectedBankId, false);
                    bumpTransactionsVersion();
                  }}
                />
              )
            ) : tab === "loans" ? (
              <LoansTab bankId={selectedBankId} role={role} onError={setError} onLoansChanged={() => refreshLoans(selectedBankId, true)} />
            ) : tab === "users" ? (
              <UsersTab role={role} onError={setError} />
            ) : (
              <AuditLogTab role={role} onError={setError} />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function NavButton(props: { active: boolean; onClick: () => void; icon: React.ReactNode; text: string }) {
  return (
    <button
      onClick={props.onClick}
      className={cx(
        "group relative flex w-full items-center gap-2 rounded-2xl border px-4 py-3 pl-5 text-left text-sm font-medium transition focus:outline-none focus:ring-2 focus:ring-slate-200",
        props.active
          ? "border-slate-300 bg-white text-slate-900 shadow-sm"
          : "border-slate-200 bg-slate-50 text-slate-700 hover:bg-white"
      )}
    >
      {props.icon}
      {props.text}
    </button>
  );
}

function LoginCard(props: { error: string; onError: (e: string) => void; onLogin: (role: string) => void }) {
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("admin");
  const [loading, setLoading] = useState(false);

  return (
    <Card className="self-center">
      <CardHeader title="Login" subtitle="Local dev default: admin/admin (after reseeding)." />
      <CardBody>
        {props.error ? <Banner kind="error" text={props.error} onClose={() => props.onError("")} /> : null}
        <div className="mt-4 space-y-3">
          <div>
            <Label>Username</Label>
            <Input value={username} onChange={(e) => setUsername(e.target.value)} />
          </div>
          <div>
            <Label>Password</Label>
            <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
          </div>
          <Button
            onClick={async () => {
              props.onError("");
              setLoading(true);
              try {
                const out = await api.login(username, password);
                props.onLogin(out.role);
              } catch (e: any) {
                props.onError(e?.message || "login_failed");
              } finally {
                setLoading(false);
              }
            }}
            disabled={loading}
          >
            {loading ? "Logging in..." : "Login"}
          </Button>
        </div>
      </CardBody>
    </Card>
  );
}

function CreateBankCard(props: { onCreated: (b: api.BankOut) => void; onError: (e: string) => void }) {
  const [name, setName] = useState("");
  const [bankType, setBankType] = useState("conventional");
  const [loading, setLoading] = useState(false);
  const toast = useToast();

  async function create() {
    setLoading(true);
    try {
      const b = await api.createBank({ name, bank_type: bankType });
      setName("");
      setBankType("conventional");
      props.onCreated(b);
      toast.success("Bank created");
    } catch (e: any) {
      props.onError(e?.message || "Failed to create bank");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card>
      <CardHeader title="Create bank" subtitle="Add one or more loans under the Loans tab." />
      <CardBody>
        <div className="grid gap-3">
          <div className="space-y-1">
            <Label>Bank name</Label>
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g., HBL" />
          </div>

          <div className="space-y-1">
            <Label>Type</Label>
            <Select value={bankType} onChange={(e) => setBankType(e.target.value)}>
              <option value="conventional">Conventional</option>
              <option value="islamic">Islamic</option>
            </Select>
          </div>
        </div>

        <div className="mt-4 flex justify-end">
          <Button onClick={create} disabled={loading || !name.trim()}>
            <Plus className="h-4 w-4" />
            {loading ? "Creating..." : "Create"}
          </Button>
        </div>
      </CardBody>
    </Card>
  );
}

function Ledger(props: { bankId: number; loanId: number; start: string; end: string; refreshTick: number; onError: (e: string) => void }) {
  const defaultEnd = karachiTodayISO();
  const defaultStart = karachiMonthStartISO();

  const rangeKey = `filters:ledger:global`;
  const [start, setStart] = useState(() => readStoredDateRange(rangeKey)?.start ?? defaultStart);
  const [end, setEnd] = useState(() => readStoredDateRange(rangeKey)?.end ?? defaultEnd);

  useEffect(() => {
    const st = readStoredDateRange(rangeKey);
    setStart(st?.start ?? defaultStart);
    setEnd(st?.end ?? defaultEnd);
  }, [rangeKey]);

  useEffect(() => {
    writeStoredDateRange(rangeKey, start, end);
  }, [rangeKey, start, end]);

  const [rows, setRows] = useState<api.LedgerRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [backfillStatus, setBackfillStatus] = useState<api.BackfillStatus | null>(null);

  const [loan, setLoan] = useState<api.LoanOut | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadLoan() {
      if (!props.loanId) {
        setLoan(null);
        return;
      }
      try {
        const list = await api.listLoans(props.bankId);
        if (!cancelled)
          setLoan(list.find((l: api.LoanOut) => l.id === props.loanId) ?? null);
      } catch {
        if (!cancelled) setLoan(null);
      }
    }

    loadLoan();
    return () => {
      cancelled = true;
    };
  }, [props.bankId, props.loanId]);

  const kpi = useMemo(() => {
    const startRow = rows.length ? rows[0] : null;
    const endRow = rows.length ? rows[rows.length - 1] : null;

    const usedPrincipal = endRow ? endRow.principal_balance : null;
    const maxLoan = loan?.max_loan_amount ?? null;

    const remainingLimit =
      usedPrincipal !== null && maxLoan !== null ? maxLoan - usedPrincipal : null;

    const utilizationPct =
      usedPrincipal !== null && maxLoan !== null && maxLoan > 0
        ? (usedPrincipal / maxLoan) * 100
        : null;

    const accruedMarkupInRange =
      startRow && endRow ? endRow.accrued_markup - startRow.accrued_markup : null;

    const currentRatePct = endRow ? endRow.rate_percent : null;

    const utilClamped =
      utilizationPct === null ? 0 : Math.max(0, Math.min(100, utilizationPct));

    return {
      usedPrincipal,
      remainingLimit,
      utilizationPct,
      utilClamped,
      accruedMarkupInRange,
      currentRatePct,
      maxLoan,
      hasRows: rows.length > 0,
    };
  }, [rows, loan]);

  const backfillPct =
    backfillStatus && backfillStatus.status === "running" && backfillStatus.total_days > 0
      ? Math.min(100, Math.round((backfillStatus.processed_days / backfillStatus.total_days) * 100))
      : 0;

  async function refresh() {
    props.onError("");
    setLoading(true);
    try {
      setBackfillStatus(null);
      const out = await api.ledger(props.bankId, props.loanId, props.start, props.end);
      setRows(out);
    } catch (e: any) {
      if (e?.name === "BackfillRunningError") {
        setRows([]);
        setBackfillStatus(e.status);
      } else {
        props.onError(e?.message || "failed_to_load_ledger");
      }
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!props.bankId || !props.loanId) {
      setRows([]);
      setBackfillStatus(null);
      return;
    }
    refresh();
  }, [props.bankId, props.loanId, props.start, props.end, props.refreshTick]);

  useEffect(() => {
    if (!backfillStatus || backfillStatus.status !== "running") return;

    let cancelled = false;
    const id = window.setInterval(async () => {
      try {
        const st = await api.getBackfillStatus(props.bankId, props.loanId);
        if (cancelled) return;
        setBackfillStatus(st);

        if (st.status !== "running") {
          window.clearInterval(id);
          if (st.status === "done" || st.status === "idle") {
            refresh();
          }
        }
      } catch {
        // ignore
      }
    }, 1000);

    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [backfillStatus?.status, props.loanId, start, end]);

  function fmtCompactMoney(v: number) {
    const sign = v < 0 ? "-" : "";
    const n = Math.abs(v);

    if (n >= 1_000_000_000_000) return `${sign}${(n / 1_000_000_000_000).toFixed(2)}T`;
    if (n >= 1_000_000_000) return `${sign}${(n / 1_000_000_000).toFixed(2)}B`;
    if (n >= 1_000_000) return `${sign}${(n / 1_000_000).toFixed(2)}M`;
    if (n >= 1_000) return `${sign}${(n / 1_000).toFixed(2)}K`;
    return `${sign}${n.toFixed(2)}`;
  }

  function moneyKpi(v: number | null) {
    if (v === null) return "-";
    return fmtCompactMoney(v);
  }

  return (
    <div className="space-y-5">
      {backfillStatus && backfillStatus.status === "running" ? (
        <div className="mt-4 rounded-2xl border border-slate-200 bg-white p-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <div className="text-sm font-semibold text-slate-900">Backfilling KIBOR rates…</div>
              <div className="mt-1 text-xs text-slate-600">
                This can take 1–2 minutes for older backdated debits. You can keep using the app while it runs.
              </div>
              <div className="mt-2 text-xs tabular-nums text-slate-600">
                {backfillStatus.processed_days} / {backfillStatus.total_days} business days
              </div>
            </div>
            <div className="w-56">
              <Progress value={backfillPct} />
            </div>
          </div>
        </div>
      ) : null}

      <div className="rounded-2xl border border-slate-200 bg-white p-3">
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <div className="text-sm font-semibold text-slate-900">Summary</div>
        </div>

        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
          <div className="min-w-0 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
            <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
              Outstanding
            </div>
            <div
              className="mt-1 min-w-0 overflow-hidden text-ellipsis whitespace-nowrap text-base font-semibold text-slate-900 tabular-nums leading-tight"
              title={kpi.usedPrincipal === null ? "" : fmtMoney(kpi.usedPrincipal)}
            >
              {moneyKpi(kpi.usedPrincipal)}
            </div>
            <div className="mt-0.5 text-[11px] text-slate-500">As of end date</div>
          </div>

          <div className="min-w-0 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
            <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
              Remaining limit
            </div>
            <div
              className="mt-1 min-w-0 overflow-hidden text-ellipsis whitespace-nowrap text-base font-semibold text-slate-900 tabular-nums leading-tight"
              title={kpi.remainingLimit === null ? "" : fmtMoney(kpi.remainingLimit)}
            >
              {moneyKpi(kpi.remainingLimit)}
            </div>
            <div className="mt-0.5 min-w-0 truncate text-[11px] text-slate-500 tabular-nums">
              <span title={kpi.maxLoan === null ? "" : fmtMoney(kpi.maxLoan)}>
                Max: {moneyKpi(kpi.maxLoan)}
              </span>
            </div>
          </div>

          <div className="min-w-0 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
            <div className="flex items-center justify-between gap-2">
              <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                Utilization
              </div>
              <div className="text-[11px] text-slate-500 tabular-nums">
                {kpi.utilizationPct === null ? "-" : `${Number(kpi.utilizationPct).toFixed(2)}%`}
              </div>
            </div>

            <div className="mt-2">
              <Progress value={kpi.utilizationPct === null ? 0 : Math.round(kpi.utilClamped)} />
            </div>

            <div className="mt-1 min-w-0 truncate text-[11px] text-slate-500 tabular-nums">
              {kpi.usedPrincipal === null || kpi.maxLoan === null
                ? ""
                : `${moneyKpi(kpi.usedPrincipal)} / ${moneyKpi(kpi.maxLoan)}`}
            </div>
          </div>

          <div className="min-w-0 overflow-hidden rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
            <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
              Markup (range)
            </div>
            <div
              className="mt-1 min-w-0 overflow-hidden text-ellipsis whitespace-nowrap text-base font-semibold text-slate-900 tabular-nums leading-tight"
              title={kpi.accruedMarkupInRange === null ? "" : fmtMoney(kpi.accruedMarkupInRange)}
            >
              {moneyKpi(kpi.accruedMarkupInRange)}
            </div>
            <div className="mt-0.5 text-[11px] text-slate-500">End − start accrued</div>
          </div>

          <div className="min-w-0 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
            <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
              Current rate
            </div>
            <div className="mt-1 min-w-0 truncate text-lg font-semibold text-slate-900 tabular-nums leading-tight">
              {kpi.currentRatePct === null ? "-" : `${fmtRate(kpi.currentRatePct)}%`}
            </div>
            <div className="mt-0.5 text-[11px] text-slate-500">Most recent in range</div>
          </div>
        </div>
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white p-4">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <div className="text-sm font-semibold text-slate-900">Ledger rows</div>

          <div className="flex items-center gap-2 text-xs text-slate-500">
            <span className="rounded-full border border-slate-200 bg-white px-2 py-0.5 font-semibold">
              PKR
            </span>
            <span className="hidden sm:inline">Amounts are in PKR • Rates in %</span>
          </div>
        </div>

        <Table className="tabular-nums">
          <thead>
            <tr>
              <Th className="w-[180px]">Date</Th>
              <Th className="text-right">Principal</Th>
              <Th className="text-right">Daily markup</Th>
              <Th className="text-right">Accrued markup</Th>
              <Th className="text-right">Rate %</Th>
            </tr>
          </thead>

          <tbody className="text-sm">
            {rows.length === 0 ? (
              <tr>
                <Td colSpan={5} className="text-slate-600">
                  No rows. Add rates + transactions and refresh.
                </Td>
              </tr>
            ) : (
              rows.map((r, i) => {

              const rowClass = cx(
                "transition-colors hover:bg-slate-50",
                i % 2 === 1 ? "bg-slate-50/40" : "bg-white"
              );

                return (
                  <tr key={i} className={rowClass}>
                    <Td className="whitespace-nowrap">
                      <span className="text-slate-900">{r.date}</span>
                    </Td>

                    <Td className="text-right font-mono">{fmtMoney(r.principal_balance)}</Td>
                    <Td className="text-right font-mono">{fmtMoney(r.daily_markup)}</Td>
                    <Td className="text-right font-mono">{fmtMoney(r.accrued_markup)}</Td>
                    <Td className="text-right font-mono">{fmtRate(r.rate_percent)}%</Td>
                  </tr>
                );
              })
            )}
          </tbody>
        </Table>
      </div>
    </div>
  );
}

function Transactions(props: {
  bankId: number;
  loanId: number;
  start: string;
  end: string;
  refreshTick: number;
  role: string;
  onError: (e: string) => void;
  onTransactionsChanged?: () => void;
  onKiborScrapeBusy?: (busy: boolean) => void;
}) {
  const toast = useToast();
  const confirm = useConfirm();

  const defaultEnd = karachiTodayISO();
  const defaultStart = karachiMonthStartISO();

  const rangeKey = `filters:tx:global`;
  const [start, setStart] = useState(() => readStoredDateRange(rangeKey)?.start ?? defaultStart);
  const [end, setEnd] = useState(() => readStoredDateRange(rangeKey)?.end ?? defaultEnd);

  useEffect(() => {
    const st = readStoredDateRange(rangeKey);
    setStart(st?.start ?? defaultStart);
    setEnd(st?.end ?? defaultEnd);
  }, [rangeKey]);

  useEffect(() => {
    writeStoredDateRange(rangeKey, start, end);
  }, [rangeKey, start, end]);

  useEffect(() => {
    refresh();
  }, [props.bankId, props.loanId, props.start, props.end, props.refreshTick]);

  const [rows, setRows] = useState<api.TxOut[]>([]);
  const [loading, setLoading] = useState(false);
  const [backfillStatus, setBackfillStatus] = useState<api.BackfillStatus | null>(null);


  const addDateKey = `filters:txAddDate:global`;
  const [date, setDate] = useState(() => readStoredDate(addDateKey) ?? defaultEnd);

  useEffect(() => {
    const d = readStoredDate(addDateKey);
    setDate(d ?? defaultEnd);
  }, [addDateKey]);

  useEffect(() => {
    writeStoredDate(addDateKey, date);
  }, [addDateKey, date]);

  const [category, setCategory] = useState<"principal" | "markup">("principal");
  const [direction, setDirection] = useState<"debit" | "credit">("debit");
  const [amount, setAmount] = useState<string>("");
  const [note, setNote] = useState<string>("");

  const isAdmin = props.role === "admin";
  const [addingTx, setAddingTx] = useState(false);

  async function refresh() {
    props.onError("");
    setLoading(true);
    try {
      const out = await api.listTxs(props.bankId, props.loanId, props.start, props.end);
      setRows(out);
    } catch (e: any) {
      props.onError(e?.message || "failed_to_load_transactions");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, [props.bankId, props.loanId]);

  useEffect(() => {
    if (!backfillStatus || backfillStatus.status !== "running") return;

    let cancelled = false;
    const id = window.setInterval(async () => {
      try {
        const st = await api.getBackfillStatus(props.bankId, props.loanId);
        if (cancelled) return;
        setBackfillStatus(st);

        if (st.status !== "running") {
          window.clearInterval(id);
          if (st.status === "done" || st.status === "idle") {
            refresh();
          }
        }
      } catch {
        // ignore
      }
    }, 1000);

    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [backfillStatus?.status, props.bankId, props.loanId, start, end]);


  return (
    <div className="space-y-5">
      {isAdmin ? (
      <div id="add-transaction" className="rounded-2xl border border-slate-200 bg-white p-4">
        <div className="mb-3 text-sm font-semibold text-slate-900">Add transaction</div>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-5">
          <div>
            <Label>Date</Label>
            <Input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
          </div>
          <div>
            <Label>Category</Label>
            <Select value={category} onChange={(e) => setCategory(e.target.value as any)}>
              <option value="principal">principal</option>
              <option value="markup">markup</option>
            </Select>
          </div>
          <div>
            <Label>Debit/Credit</Label>
            <Select value={direction} onChange={(e) => setDirection(e.target.value as any)}>
              <option value="debit">debit (+)</option>
              <option value="credit">credit (-)</option>
            </Select>
          </div>
          <div>
            <Label>Amount</Label>
            <Input value={amount} onChange={(e) => setAmount(e.target.value)} placeholder="1000" inputMode="decimal" />
          </div>
          <div>
            <Label>Note</Label>
            <Input value={note} onChange={(e) => setNote(e.target.value)} placeholder="optional" />
          </div>
        </div>
        <div className="mt-3">
          <Button
            disabled={addingTx}
            onClick={async () => {
              props.onError("");
              if (addingTx) return;

              let willScrapeKibor = false;

              try {
                setAddingTx(true);

                const parsed = Number(amount);
                if (!Number.isFinite(parsed) || Math.abs(parsed) < 1e-12) throw new Error("amount_invalid");
                const signed = direction === "credit" ? -Math.abs(parsed) : Math.abs(parsed);

                // Backend scrapes KIBOR on principal debits (amount > 0)
                willScrapeKibor = category === "principal" && signed > 0;
                if (willScrapeKibor) props.onKiborScrapeBusy?.(true);

                await api.addTx(props.bankId, props.loanId, {
                  date,
                  category,
                  amount: signed,
                  note: note.trim() ? note.trim() : null,
                });

                toast.success("Transaction added.");
                setAmount("");
                setNote("");
                await refresh();
                props.onTransactionsChanged?.();
              } catch (e: any) {
                props.onError(e?.message || "failed_to_add_tx");
              } finally {
                if (willScrapeKibor) props.onKiborScrapeBusy?.(false);
                setAddingTx(false);
              }
            }}
          >
            {addingTx ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Adding…
              </>
            ) : (
              "Add"
            )}
          </Button>
        </div>
      </div>      ) : (
        <div className="rounded-2xl border border-slate-200 bg-white p-4">
          <div className="text-sm text-slate-600">You have view-only access.</div>
        </div>
      )}

      

      <div className="rounded-2xl border border-slate-200 bg-white p-4">
        <div className="mb-3 text-sm font-semibold text-slate-900">Transactions</div>
        <Table className="tabular-nums">
          <thead>
            <tr>
              <Th>Date</Th>
              <Th className="text-right">KIBOR %</Th>
              <Th>Category</Th>
              <Th>Direction</Th>
              <Th className="text-right">Amount</Th>
              <Th>Note</Th>
              {isAdmin ? <Th /> : null}
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <Td colSpan={isAdmin ? 7 : 6} className="text-slate-600">
                  No transactions in range.
                </Td>
              </tr>
            ) : (
              rows.map((t, i) => {
                const dir = t.amount < 0 ? "credit" : "debit";
                const abs = Math.abs(t.amount);
                return (
                  <tr
                    key={t.id}
                    className={cx(
                      "transition-colors hover:bg-slate-50",
                      i % 2 === 1 ? "bg-slate-50/40" : "bg-white"
                    )}
                  >
                    <Td className="whitespace-nowrap">{t.date}</Td>
                    <Td className="text-right font-mono">{fmtRate(t.kibor_rate_percent)}</Td>
                    <Td className="font-mono">{t.category}</Td>
                    <Td className="font-mono">{dir}</Td>
                    <Td className="text-right font-mono">{fmtMoney(abs)}</Td>
                    <Td className="max-w-[420px] truncate whitespace-nowrap">{t.note || ""}</Td>
                    {isAdmin ? (
                      <Td className="text-right">
                        <Button
                          kind="danger"
                          size="sm"
                          onClick={async () => {
                            props.onError("");
                            const ok = await confirm({
                              title: "Delete transaction?",
                              body: "This will permanently remove the transaction from the ledger.",
                              confirmText: "Delete",
                              danger: true,
                            });
                            if (!ok) return;

                            try {
                              await api.deleteTx(props.bankId, props.loanId, t.id);
                              toast.success("Transaction deleted.");
                              await refresh();
                              props.onTransactionsChanged?.();
                            } catch (e: any) {
                              props.onError(e?.message || "failed_to_delete_tx");
                              toast.error(e?.message || "Failed to delete transaction.");
                            }
                          }}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </Td>
                    ) : null}
                  </tr>
                );
              })
            )}
          </tbody>
        </Table>
      </div>
    </div>
  );
}

function LoansTab(props: { bankId: number; role: string; onError: (e: string) => void; onLoansChanged: () => void }) {
  const isAdmin = props.role === "admin";
  const toast = useToast();
  const confirm = useConfirm();

  const [name, setName] = useState("");
  const [tenor, setTenor] = useState<"1" | "3" | "6" | "9" | "12">("1");
  const [additionalRate, setAdditionalRate] = useState<string>("0");
  const [maxLoanAmount, setMaxLoanAmount] = useState<string>("");
  const [placeholderRate, setKIBORRate] = useState<string>("0");

  const [items, setItems] = useState<api.LoanOut[]>([]);
  const [loading, setLoading] = useState(false);

  async function refresh() {
    if (!props.bankId) return;
    setLoading(true);
    try {
      const list = await api.listLoans(props.bankId);
      setItems(list);
    } catch (e: any) {
      props.onError(e?.message || "Failed to load loans");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!props.bankId) return;
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [props.bankId]);

  async function create() {
    try {
      await api.createLoan(props.bankId, {
        name,
        kibor_tenor_months: Number(tenor) as 1 | 3 | 6,
        additional_rate: additionalRate.trim() ? Number(additionalRate) : 0,
        kibor_placeholder_rate_percent: placeholderRate.trim() ? Number(placeholderRate) : 0,
        max_loan_amount: maxLoanAmount.trim() ? Number(maxLoanAmount) : null,
      });
      setName("");
      setTenor("1");
      setAdditionalRate("0");
      setMaxLoanAmount("");
      setKIBORRate("0");
      toast.success("Loan created");
      await refresh();
      props.onLoansChanged();
    } catch (e: any) {
      props.onError(e?.message || "Failed to create loan");
    }
  }

  async function remove(loan: api.LoanOut) {
    const ok = await confirm({
      title: "Delete loan?",
      body: `This will remove the loan "${loan.name}".`,
      confirmText: "Delete",
      danger: true,
    });

    if (!ok) return;

    try {
      await api.deleteLoan(props.bankId, loan.id);
      toast.success("Loan deleted");
      await refresh();
      props.onLoansChanged();
    } catch (e: any) {
      props.onError(e?.message || "Failed to delete loan");
    }
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader title="Loans" subtitle="Each bank can have multiple loans." />
        <CardBody>
          {!props.bankId ? (
            <div className="text-sm text-slate-600">Select a bank first.</div>
          ) : (
            <>
              <div className="mt-4 overflow-x-auto">
                <Table className="tabular-nums">
                  <thead>
                    <tr>
                      <Th>Name</Th>
                      <Th className="text-right">Tenor</Th>
                      <Th className="text-right">Spread %</Th>
                      <Th className="text-right">Max loan</Th>
                      {isAdmin ? <Th /> : null}
                    </tr>
                  </thead>
                  <tbody>
                    {items.map((l, i) => (
                      <tr
                        key={l.id}
                        className={cx(
                          "transition-colors hover:bg-slate-50",
                          i % 2 === 1 ? "bg-slate-50/40" : "bg-white"
                        )}
                      >
                        <Td className="font-medium">{l.name}</Td>
                        <Td className="text-right font-mono">{l.kibor_tenor_months === 12 ? "1y" : `${l.kibor_tenor_months}m`}</Td>
                        <Td className="text-right font-mono">{fmtRate(l.additional_rate ?? 0)}%</Td>
                        <Td className="text-right font-mono">{l.max_loan_amount == null ? "—" : fmtMoney(l.max_loan_amount)}</Td>
                        {isAdmin ? (
                          <Td className="text-right">
                            <Button kind="danger" onClick={() => remove(l)}>
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </Td>
                        ) : null}
                      </tr>
                    ))}
                    {!items.length ? (
                      <tr>
                        <Td colSpan={isAdmin ? 6 : 5} className="text-slate-600">
                          No loans yet.
                        </Td>
                      </tr>
                    ) : null}
                  </tbody>
                </Table>
              </div>
            </>
          )}
        </CardBody>
      </Card>

      {isAdmin ? (
        <Card>
          <CardHeader title="Add a loan" subtitle="Create a loan for the selected bank." />
          <CardBody>
            {!props.bankId ? (
              <div className="text-sm text-slate-600">Select a bank first.</div>
            ) : (
              <>
                <div className="grid gap-3 md:grid-cols-2">
                  <div className="space-y-1">
                    <Label>Loan name</Label>
                    <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g., Working Capital 2026" />
                  </div>

                  <div className="space-y-1">
                    <Label>Tenor</Label>
                    <Select value={tenor} onChange={(e) => setTenor(e.target.value as any)}>
                      <option value="1">1 month</option>
                      <option value="3">3 months</option>
                      <option value="6">6 months</option>
                      <option value="9">9 months</option>
                      <option value="12">1 year</option>
                    </Select>
                  </div>

                  <div className="space-y-1">
                    <Label>Spread %</Label>
                    <Input value={additionalRate} onChange={(e) => setAdditionalRate(e.target.value)} inputMode="decimal" />
                  </div>

                  <div className="space-y-1">
                    <Label>Max loan amount</Label>
                    <Input value={maxLoanAmount} onChange={(e) => setMaxLoanAmount(e.target.value)} inputMode="decimal" placeholder="Optional" />
                  </div>
                </div>

                <div className="mt-4 flex justify-end">
                  <Button onClick={create} disabled={!name.trim()}>
                    <Plus className="h-4 w-4" />
                    Create loan
                  </Button>
                </div>
              </>
            )}
          </CardBody>
        </Card>
      ) : null}
    </div>
  );
}

function UsersTab(props: { role: string; onError: (e: string) => void }) {
  const toast = useToast();
  const confirm = useConfirm();
  const isAdmin = props.role === "admin";
  const [rows, setRows] = useState<api.UserOut[]>([]);
  const [loading, setLoading] = useState(false);

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<"admin" | "viewer">("viewer");

  async function refresh() {
    props.onError("");
    setLoading(true);
    try {
      const out = await api.listUsers();
      setRows(out);
    } catch (e: any) {
      props.onError(e?.message || "failed_to_load_users");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (isAdmin) refresh();
  }, []);

  if (!isAdmin) {
    return (
      <Card>
        <CardHeader title="Users" subtitle="Admin only." />
        <CardBody />
      </Card>
    );
  }

  return (
    <div className="space-y-5">
      <div className="rounded-2xl border border-slate-200 bg-white p-4">
        <div className="mb-3 text-sm font-semibold text-slate-900">Create user</div>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
          <div>
            <Label>Username</Label>
            <Input value={username} onChange={(e) => setUsername(e.target.value)} placeholder="newuser" />
          </div>
          <div>
            <Label>Password</Label>
            <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="min 6 chars" />
          </div>
          <div>
            <Label>Role</Label>
            <Select value={role} onChange={(e) => setRole(e.target.value as any)}>
              <option value="viewer">viewer</option>
              <option value="admin">admin</option>
            </Select>
          </div>
          <div className="flex items-end">
            <Button
              onClick={async () => {
                props.onError("");
                try {
                  await api.createUser({ username, password, role });
                  toast.success("User created.");
                  setUsername("");
                  setPassword("");
                  setRole("viewer");
                  await refresh();
                } catch (e: any) {
                  props.onError(e?.message || "failed_to_create_user");
                }
              }}
            >
              Create
            </Button>
          </div>
        </div>
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white p-4">
        <div className="mb-3 text-sm font-semibold text-slate-900">Users</div>
        <div className="mt-3">
          <Table className="tabular-nums">
            <thead>
              <tr>
                <Th>Username</Th>
                <Th>Role</Th>
                <Th />
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 ? (
                <tr>
                  <Td colSpan={3} className="text-slate-600">
                    No users.
                  </Td>
                </tr>
              ) : (
                rows.map((u, i) => (
                  <tr
                    key={u.id}
                    className={cx(
                      "transition-colors hover:bg-slate-50",
                      i % 2 === 1 ? "bg-slate-50/40" : "bg-white"
                    )}
                  >
                    <Td className="font-mono">{u.username}</Td>
                    <Td className="font-mono">{u.role}</Td>
                    <Td className="text-right">
                      <Button
                        kind="danger"
                        size="sm"
                        onClick={async () => {
                          props.onError("");
                          const ok = await confirm({
                            title: `Delete user "${u.username}"?`,
                            body: "This will permanently remove the user account.",
                            confirmText: "Delete",
                            danger: true,
                          });
                          if (!ok) return;

                          try {
                            await api.deleteUser(u.id);
                            toast.success("User deleted.");
                            await refresh();
                          } catch (e: any) {
                            props.onError(e?.message || "failed_to_delete_user");
                            toast.error(e?.message || "Failed to delete user.");
                          }
                        }}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </Td>
                  </tr>
                ))
              )}
            </tbody>
          </Table>
        </div>
      </div>
    </div>
  );
}

function AuditLogTab(props: { role: string; onError: (msg: string) => void }) {
  const isAdmin = props.role === "admin";

  const [rows, setRows] = useState<api.AuditOut[]>([]);
  const [loading, setLoading] = useState(false);

  const [username, setUsername] = useState("");
  const [entityType, setEntityType] = useState("");
  const [action, setAction] = useState("");
  const [limit, setLimit] = useState(200);
  const [limitInput, setLimitInput] = useState("200");

  function commitLimit(raw: string) {
    const trimmed = raw.trim();
    if (!trimmed) {
      setLimit(200);
      setLimitInput("200");
      return;
    }
    const n = Number.parseInt(trimmed, 10);
    if (!Number.isFinite(n)) {
      setLimitInput(String(limit));
      return;
    }
    const clamped = Math.max(1, Math.min(1000, n));
    setLimit(clamped);
    setLimitInput(String(clamped));
  }

  async function load() {
    if (!isAdmin) return;
    setLoading(true);
    try {
      const out = await api.listAudit({
        username: username.trim() || undefined,
        entity_type: entityType.trim() || undefined,
        action: action.trim() || undefined,
        limit,
      });
      setRows(out);
    } catch (e: any) {
      props.onError(e?.message || "Failed to load audit log");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  useEffect(() => {
    load();
  }, [limit]);

  useEffect(() => {
    setLimitInput(String(limit));
  }, [limit]);

  if (!isAdmin) {
    return (
      <Card>
        <CardHeader title="Audit log" subtitle="Admins only." />
        <CardBody>
          <div className="text-sm text-slate-600">You don’t have permission to view audit logs.</div>
        </CardBody>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader title="Audit log" subtitle="Tracks who did what and when (admin only)." />
      <CardBody>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
          <div>
            <Label>Username</Label>
            <Input value={username} onChange={(e) => setUsername(e.target.value)} placeholder="e.g., admin" />
          </div>
          <div>
            <Label>Entity type</Label>
            <Input value={entityType} onChange={(e) => setEntityType(e.target.value)} placeholder='e.g., "transaction"' />
          </div>
          <div>
            <Label>Action</Label>
            <Input value={action} onChange={(e) => setAction(e.target.value)} placeholder='e.g., "transaction.create"' />
          </div>
          <div>
            <Label>Limit</Label>
            <Input
              type="number"
              value={limitInput}
              onChange={(e) => setLimitInput(e.target.value)}
              onBlur={(e) => commitLimit(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  commitLimit((e.target as HTMLInputElement).value);
                }
              }}
            />
          </div>
        </div>

        <div className="mt-3 flex items-center gap-2">
          <div className="text-xs text-slate-500">Showing newest first. Use filters to narrow results.</div>
        </div>

        <div className="mt-4 overflow-x-auto">
          <Table className="tabular-nums">
            <thead>
              <tr>
                <Th>Time</Th>
                <Th>User</Th>
                <Th>Action</Th>
                <Th>Entity</Th>
                <Th className="text-right">ID</Th>
                <Th>Details</Th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr
                  key={r.id}
                  className={cx(
                    "align-top transition-colors hover:bg-slate-50",
                    i % 2 === 1 ? "bg-slate-50/40" : "bg-white"
                  )}
                >
                  <Td className="whitespace-nowrap font-mono">{new Date(r.created_at).toLocaleString()}</Td>
                  <Td className="whitespace-nowrap">{r.username}</Td>
                  <Td className="whitespace-nowrap font-mono">{r.action}</Td>
                  <Td className="whitespace-nowrap font-mono">{r.entity_type}</Td>
                  <Td className="whitespace-nowrap text-right font-mono">{r.entity_id ?? "-"}</Td>
                  <Td className="min-w-[380px]">
                    <pre className="whitespace-pre-wrap rounded-xl bg-slate-50 p-2 text-xs text-slate-700">
                      {r.details ? JSON.stringify(r.details, null, 2) : "{}"}
                    </pre>
                  </Td>
                </tr>
              ))}
              {!rows.length ? (
                <tr>
                  <Td colSpan={6} className="text-slate-600">
                    No audit rows.
                  </Td>
                </tr>
              ) : null}
            </tbody>
          </Table>
        </div>
      </CardBody>
    </Card>
  );
}