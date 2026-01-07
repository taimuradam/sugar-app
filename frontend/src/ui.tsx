import React, { createContext, useContext, useMemo, useRef, useState } from "react";

export function cx(...classes: Array<string | false | null | undefined>) {
  return classes.filter(Boolean).join(" ");
}

export function Card(props: React.HTMLAttributes<HTMLDivElement>) {
  const { className, ...rest } = props;
  return (
    <div
      {...rest}
      className={cx(
        "rounded-3xl border border-slate-200 bg-white shadow-sm shadow-slate-200/40",
        className
      )}
    />
  );
}

export function CardHeader(props: { title: string; subtitle?: string; right?: React.ReactNode }) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-100 px-6 py-5">
      <div>
        <div className="text-sm font-semibold text-slate-900">{props.title}</div>
        {props.subtitle ? <div className="mt-1 text-xs text-slate-500">{props.subtitle}</div> : null}
      </div>
      {props.right ? <div className="flex items-center gap-2">{props.right}</div> : null}
    </div>
  );
}

export function CardBody(props: React.HTMLAttributes<HTMLDivElement>) {
  const { className, ...rest } = props;
  return <div {...rest} className={cx("px-6 py-5", className)} />;
}

type ButtonKind = "primary" | "secondary" | "danger" | "ghost";
type ButtonSize = "sm" | "md";

export function Button(
  props: React.ButtonHTMLAttributes<HTMLButtonElement> & { kind?: ButtonKind; size?: ButtonSize }
) {
  const { className, kind = "primary", size = "md", ...rest } = props;

  const base =
    "inline-flex items-center justify-center gap-2 rounded-2xl font-semibold transition focus:outline-none focus:ring-2 focus:ring-slate-300 disabled:cursor-not-allowed disabled:opacity-60";
  const sizes = size === "sm" ? "px-3 py-2 text-xs" : "px-4 py-2 text-sm";

  const kinds =
    kind === "primary"
      ? "bg-slate-900 text-white hover:bg-slate-800"
      : kind === "secondary"
      ? "border border-slate-200 bg-white text-slate-800 hover:bg-slate-50"
      : kind === "danger"
      ? "border border-rose-200 bg-rose-50 text-rose-700 hover:bg-rose-100"
      : "bg-transparent text-slate-700 hover:bg-slate-100";

  return <button {...rest} className={cx(base, sizes, kinds, className)} />;
}

export function Progress(props: { value: number; label?: string }) {
  const v = Math.max(0, Math.min(100, props.value || 0));
  return (
    <div className="w-full">
      {props.label ? <div className="mb-2 text-xs font-semibold text-slate-700">{props.label}</div> : null}
      <div className="h-2 w-full rounded-full bg-slate-200">
        <div className="h-2 rounded-full bg-slate-900" style={{ width: `${v}%` }} />
      </div>
      <div className="mt-1 text-[11px] tabular-nums text-slate-600">{v}%</div>
    </div>
  );
}


export function Label(props: React.HTMLAttributes<HTMLDivElement>) {
  const { className, ...rest } = props;
  return <div {...rest} className={cx("mb-1 text-xs font-medium text-slate-600", className)} />;
}

export function Input(props: React.InputHTMLAttributes<HTMLInputElement> & { error?: string }) {
  const { className, error, ...rest } = props;
  return (
    <div>
      <input
        {...rest}
        className={cx(
          "w-full rounded-xl border bg-white px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-200",
          error ? "border-rose-300" : "border-slate-200",
          className
        )}
      />
      {error ? <div className="mt-1 text-xs text-rose-600">{error}</div> : null}
    </div>
  );
}

export function Select(props: React.SelectHTMLAttributes<HTMLSelectElement>) {
  const { className, ...rest } = props;
  return (
    <select
      {...rest}
      className={cx(
        "w-full appearance-none rounded-xl border border-slate-200 bg-white px-3 py-2 pr-9 text-sm text-slate-900 focus:border-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-200 disabled:bg-slate-50 disabled:text-slate-500",
        className
      )}
      style={{
        backgroundImage:
          "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='20' height='20' viewBox='0 0 20 20'%3E%3Cpath fill='%2364748b' d='M5.5 7.5l4.5 5 4.5-5'/%3E%3C/svg%3E\")",
        backgroundRepeat: "no-repeat",
        backgroundPosition: "right 0.6rem center",
        backgroundSize: "1.1rem 1.1rem",
      }}
    />
  );
}

export function Table(props: React.PropsWithChildren<{ className?: string }>) {
  return (
    <div className={cx("overflow-auto rounded-xl border border-slate-200", props.className)}>
      <table className="min-w-full text-left text-sm">{props.children}</table>
    </div>
  );
}

type ThProps = React.ThHTMLAttributes<HTMLTableCellElement>;
type TdProps = React.TdHTMLAttributes<HTMLTableCellElement>;

export function Th(props: ThProps) {
  const { className, ...rest } = props;
  return (
    <th
      {...rest}
      className={cx(
        "sticky top-0 z-10 whitespace-nowrap border-b border-slate-200 bg-slate-50 px-3 py-2 text-xs font-semibold text-slate-600",
        className
      )}
    />
  );
}

export function Td(props: TdProps) {
  const { className, ...rest } = props;
  return (
    <td
      {...rest}
      className={cx("whitespace-nowrap border-b border-slate-200 px-3 py-2 text-slate-800", className)}
    />
  );
}

export function Banner(props: {
  kind: "error" | "success" | "info";
  text: string;
  onClose?: () => void;
}) {
  const colors =
    props.kind === "error"
      ? "border-rose-200 bg-rose-50 text-rose-800"
      : props.kind === "success"
      ? "border-emerald-200 bg-emerald-50 text-emerald-800"
      : "border-slate-200 bg-slate-50 text-slate-800";
  return (
    <div className={cx("flex items-start justify-between gap-3 rounded-2xl border p-3 text-sm", colors)}>
      <div className="whitespace-pre-wrap">{props.text}</div>
      {props.onClose ? (
        <button
          className="rounded-lg px-2 py-1 text-xs font-semibold text-slate-600 hover:bg-white/60"
          onClick={props.onClose}
          aria-label="Dismiss"
        >
          ✕
        </button>
      ) : null}
    </div>
  );
}

type ToastKind = "success" | "error" | "info";
type ToastItem = { id: string; kind: ToastKind; text: string; createdAt: number };

const ToastCtx = createContext<{ push: (kind: ToastKind, text: string) => void } | null>(null);

export function ToastProvider(props: React.PropsWithChildren) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const timers = useRef<Record<string, number>>({});

  const push = (kind: ToastKind, text: string) => {
    const id = `${Date.now()}_${Math.random().toString(16).slice(2)}`;
    const it: ToastItem = { id, kind, text, createdAt: Date.now() };
    setItems((prev) => [...prev, it]);

    const t = window.setTimeout(() => {
      setItems((prev) => prev.filter((x) => x.id !== id));
      delete timers.current[id];
    }, 3800);
    timers.current[id] = t;
  };

  const value = useMemo(() => ({ push }), []);

  return (
    <ToastCtx.Provider value={value}>
      {props.children}

      <div className="pointer-events-none fixed right-4 top-4 z-50 flex w-[360px] max-w-[calc(100vw-2rem)] flex-col gap-2">
        {items.map((t) => (
          <div
            key={t.id}
            className={cx(
              "pointer-events-auto rounded-2xl border p-3 text-sm shadow-md shadow-slate-200/50",
              t.kind === "success" && "border-emerald-200 bg-emerald-50 text-emerald-900",
              t.kind === "error" && "border-rose-200 bg-rose-50 text-rose-900",
              t.kind === "info" && "border-slate-200 bg-white text-slate-900"
            )}
          >
            <div className="flex items-start justify-between gap-3">
              <div className="whitespace-pre-wrap">{t.text}</div>
              <button
                className="rounded-lg px-2 py-1 text-xs font-semibold text-slate-600 hover:bg-white/60"
                onClick={() => setItems((prev) => prev.filter((x) => x.id !== t.id))}
                aria-label="Dismiss toast"
              >
                ✕
              </button>
            </div>
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastCtx);
  if (!ctx) throw new Error("useToast must be used within <ToastProvider>");
  return {
    success: (text: string) => ctx.push("success", text),
    error: (text: string) => ctx.push("error", text),
    info: (text: string) => ctx.push("info", text),
  };
}

type ConfirmOptions = { title: string; body?: string; confirmText?: string; danger?: boolean };

const ConfirmCtx = createContext<{ confirm: (o: ConfirmOptions) => Promise<boolean> } | null>(null);

export function ConfirmProvider(props: React.PropsWithChildren) {
  const [open, setOpen] = useState(false);
  const resolver = useRef<((v: boolean) => void) | null>(null);
  const [opts, setOpts] = useState<ConfirmOptions>({ title: "" });

  const confirm = (o: ConfirmOptions) =>
    new Promise<boolean>((resolve) => {
      resolver.current = resolve;
      setOpts(o);
      setOpen(true);
    });

  const close = (v: boolean) => {
    setOpen(false);
    resolver.current?.(v);
    resolver.current = null;
  };

  return (
    <ConfirmCtx.Provider value={{ confirm }}>
      {props.children}

      {open ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-slate-900/30" onClick={() => close(false)} />
          <div className="relative w-full max-w-md rounded-3xl border border-slate-200 bg-white p-6 shadow-xl shadow-slate-300/30">
            <div className="text-base font-semibold text-slate-900">{opts.title}</div>
            {opts.body ? <div className="mt-2 text-sm text-slate-600">{opts.body}</div> : null}

            <div className="mt-6 flex justify-end gap-2">
              <Button kind="secondary" onClick={() => close(false)}>
                Cancel
              </Button>
              <Button kind={opts.danger ? "danger" : "primary"} onClick={() => close(true)}>
                {opts.confirmText || "Confirm"}
              </Button>
            </div>
          </div>
        </div>
      ) : null}
    </ConfirmCtx.Provider>
  );
}

export function useConfirm() {
  const ctx = useContext(ConfirmCtx);
  if (!ctx) throw new Error("useConfirm must be used within <ConfirmProvider>");
  return ctx.confirm;
}