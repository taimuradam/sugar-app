import React from "react";

export function cx(...classes: Array<string | false | null | undefined>) {
  return classes.filter(Boolean).join(" ");
}

export function Card(props: React.PropsWithChildren<{ className?: string }>) {
  return (
    <div className={cx("rounded-2xl border border-slate-200 bg-white shadow-sm", props.className)}>
      {props.children}
    </div>
  );
}

export function CardHeader(props: { title: string; subtitle?: string }) {
  return (
    <div className="border-b border-slate-200 px-4 py-3">
      <div className="text-sm font-semibold text-slate-900">{props.title}</div>
      {props.subtitle ? <div className="mt-1 text-xs text-slate-500">{props.subtitle}</div> : null}
    </div>
  );
}

export function CardBody(props: React.PropsWithChildren<{ className?: string }>) {
  return <div className={cx("px-4 py-4", props.className)}>{props.children}</div>;
}

export function Button(
  props: React.ButtonHTMLAttributes<HTMLButtonElement> & { kind?: "primary" | "secondary" }
) {
  const { className, kind = "primary", ...rest } = props;
  return (
    <button
      {...rest}
      className={cx(
        "inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold transition disabled:opacity-60",
        kind === "primary" && "bg-slate-900 text-white hover:bg-slate-800",
        kind === "secondary" && "border border-slate-200 bg-white text-slate-800 hover:bg-slate-50",
        className
      )}
    />
  );
}

export function Label(props: React.HTMLAttributes<HTMLDivElement>) {
  const { className, ...rest } = props;
  return <div {...rest} className={cx("mb-1 text-xs font-medium text-slate-600", className)} />;
}

export function Input(props: React.InputHTMLAttributes<HTMLInputElement>) {
  const { className, ...rest } = props;
  return (
    <input
      {...rest}
      className={cx(
        "w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-slate-400 focus:outline-none",
        className
      )}
    />
  );
}

export function Select(props: React.SelectHTMLAttributes<HTMLSelectElement>) {
  const { className, ...rest } = props;
  return (
    <select
      {...rest}
      className={cx(
        "w-full appearance-none rounded-xl border border-slate-200 bg-white px-3 py-2 pr-10 text-sm text-slate-900 focus:border-slate-400 focus:outline-none",
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
    <th {...rest} className={cx("whitespace-nowrap border-b border-slate-200 px-3 py-2 text-xs font-semibold text-slate-600", className)} />
  );
}

export function Td(props: TdProps) {
  const { className, ...rest } = props;
  return (
    <td {...rest} className={cx("whitespace-nowrap border-b border-slate-200 px-3 py-2 text-slate-800", className)} />
  );
}

export function Banner(props: { kind?: "info" | "error"; text: string; onClose?: () => void }) {
  const kind = props.kind || "info";
  return (
    <div
      className={cx(
        "mb-4 flex items-start justify-between gap-3 rounded-2xl border p-4 text-sm",
        kind === "info" && "border-slate-200 bg-slate-50 text-slate-700",
        kind === "error" && "border-rose-200 bg-rose-50 text-rose-700"
      )}
    >
      <div className="leading-5">{props.text}</div>
      {props.onClose ? (
        <button onClick={props.onClose} className="rounded-lg px-2 py-1 text-xs hover:bg-white/60">
          ✕
        </button>
      ) : null}
    </div>
  );
}
