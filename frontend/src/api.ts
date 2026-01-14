const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

export type TokenOut = { access_token: string; token_type?: string; role: string };

export type BankOut = {
  id: number;
  name: string;
  bank_type: string;
  created_at?: string;
};

export type LoanOut = {
  id: number;
  bank_id: number;
  name: string;
  kibor_tenor_months: 1 | 3 | 6 | 9 | 12;
  additional_rate: number | null;
  kibor_placeholder_rate_percent: number;
  max_loan_amount: number | null;
  created_at?: string;
};

export type RateOut = {
  id: number;
  bank_id: number;
  tenor_months: number;
  effective_date: string; // YYYY-MM-DD
  annual_rate_percent: number;
  created_at?: string;
};

export type LoanDateBoundsOut = { min_date: string | null; max_date: string | null };

export type LoanBalanceOut = {
  bank_id: number;
  loan_id: number;
  principal_balance: number;
  as_of?: string | null;
};

export type TxCategory = "principal" | "markup";

export type TxOut = {
  id: number;
  bank_id: number;
  loan_id: number | null;
  date: string;
  category: TxCategory;
  amount: number;
  kibor_rate_percent?: number | null;
  note?: string | null;
  created_at: string;
};

export type LedgerRow = {
  date: string;
  principal_balance: number;
  daily_markup: number;
  accrued_markup: number;
  rate_percent: number;
};

export type BackfillStatus = {
  status: "idle" | "running" | "done" | "error";
  total_days: number;
  processed_days: number;
  started_at?: string | null;
  message?: string | null;
};

export class BackfillRunningError extends Error {
  status: BackfillStatus;
  constructor(status: BackfillStatus) {
    super("backfill_running");
    this.name = "BackfillRunningError";
    this.status = status;
  }
}

export type UserOut = { id: number; username: string; role: "admin" | "viewer"; created_at?: string };

export type AuditOut = {
  id: number;
  created_at: string;
  username: string;
  action: string;
  entity_type?: string | null;
  entity_id?: number | null;
  details?: any;
};

function getToken() {
  return localStorage.getItem("token") || "";
}

export function setToken(t: string) {
  localStorage.setItem("token", t);
}

export function clearToken() {
  localStorage.removeItem("token");
  localStorage.removeItem("role");
}

export function getRole() {
  return localStorage.getItem("role") || "";
}

export function setRole(r: string) {
  localStorage.setItem("role", r);
}

async function request<T>(path: string, init: RequestInit = {}) {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init.headers as any),
  };

  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const url = `${String(API_URL).replace(/\/$/, "")}${path}`;

  let res: Response;
  try {
    res = await fetch(url, { ...init, headers });
  } catch (e: any) {
    // This is where your UI currently gets "Load failed"
    throw new Error(`NETWORK_ERROR: ${e?.message || "request_failed"} (${url})`);
  }

  if (!res.ok) {
    let msg = res.statusText || `HTTP_${res.status}`;
    try {
      const j = await res.json();
      msg = j?.detail || j?.message || msg;
    } catch {}
    throw new Error(`${msg} (${url})`);
  }

  if (res.status === 204) return undefined as any;
  return (await res.json()) as T;
}

export async function login(username: string, password: string) {
  const url = `${String(API_URL).replace(/\/$/, "")}/auth/login`;
  let res: Response;

  try {
    res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
  } catch (e: any) {
    throw new Error(`NETWORK_ERROR: ${e?.message || "request_failed"} (${url})`);
  }

  if (!res.ok) {
    let msg = res.statusText || `HTTP_${res.status}`;
    try {
      const j = await res.json();
      msg = j?.detail || j?.message || msg;
    } catch {}
    throw new Error(`${msg} (${url})`);
  }

  const out = (await res.json()) as TokenOut;
  const role = out.role === "admin" || out.role === "viewer" ? out.role : "viewer";

  setToken(out.access_token);
  setRole(role);

  return { ...out, role };
}

export async function listBanks() {
  return await request<BankOut[]>("/banks");
}

export async function createBank(body: { name: string; bank_type: string }) {
  return await request<BankOut>("/banks", { method: "POST", body: JSON.stringify(body) });
}

export async function deleteBank(bankId: number) {
  return await request<{ ok: boolean }>(`/banks/${bankId}`, { method: "DELETE" });
}

export async function listLoans(bankId: number) {
  return await request<LoanOut[]>(`/banks/${bankId}/loans`);
}

export async function listRates(bankId: number) {
  return await request<RateOut[]>(`/banks/${bankId}/rates`);
}

export async function loanDateBounds(bankId: number, loanId: number) {
  return request<LoanDateBoundsOut>(`/banks/${bankId}/loans/${loanId}/date-bounds`);
}

export async function createLoan(
  bankId: number,
  body: {
    name: string;
    kibor_tenor_months: 1 | 3 | 6 | 9 | 12;
    additional_rate?: number | null;
    kibor_placeholder_rate_percent: number;
    max_loan_amount?: number | null;
  }
) {
  return await request<LoanOut>(`/banks/${bankId}/loans`, { method: "POST", body: JSON.stringify(body) });
}

export async function deleteLoan(bankId: number, loanId: number) {
  return await request<{ ok: boolean }>(`/banks/${bankId}/loans/${loanId}`, { method: "DELETE" });
}

export async function loanBalance(bankId: number, loanId: number) {
  return await request<LoanBalanceOut>(`/banks/${bankId}/loans/${loanId}/balance`);
}

export async function listTxs(bankId: number, loanId: number, start?: string, end?: string) {
  const qs = new URLSearchParams();
  if (start) qs.set("start", start);
  if (end) qs.set("end", end);
  const q = qs.toString() ? `?${qs.toString()}` : "";
  return await request<TxOut[]>(`/banks/${bankId}/loans/${loanId}/transactions${q}`);
}

export async function addTx(
  bankId: number,
  loanId: number,
  body: { date: string; category: TxCategory; amount: number; note?: string | null }
) {
  return await request<TxOut>(`/banks/${bankId}/loans/${loanId}/transactions`, { method: "POST", body: JSON.stringify(body) });
}

export async function deleteTx(bankId: number, loanId: number, txId: number) {
  return await request<{ ok: boolean }>(`/banks/${bankId}/loans/${loanId}/transactions/${txId}`, { method: "DELETE" });
}

export async function getBackfillStatus(bankId: number, loanId: number) {
  return await request<BackfillStatus>(`/banks/${bankId}/loans/${loanId}/kibor-backfill/status`);
}

export async function startBackfill(bankId: number, loanId: number) {
  return await request<BackfillStatus>(`/banks/${bankId}/loans/${loanId}/kibor-backfill/start`, { method: "POST" });
}

export async function ledger(bankId: number, loanId: number, start: string, end: string) {
  const token = getToken();
  const qs = new URLSearchParams({ start, end });
  const res = await fetch(`${API_URL}/banks/${bankId}/loans/${loanId}/ledger?${qs.toString()}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  });

  if (res.status === 202) {
    const st = (await res.json()) as BackfillStatus;
    throw new BackfillRunningError(st);
  }

  if (!res.ok) {
    let msg = res.statusText;
    try {
      const j = await res.json();
      msg = j?.detail || j?.message || msg;
    } catch {}
    throw new Error(msg);
  }

  return (await res.json()) as LedgerRow[];
}

export async function downloadReport(bankId: number, loanId: number, start: string, end: string, filename?: string) {
  const token = getToken();
  const qs = new URLSearchParams({ start, end, loan_id: String(loanId) });

  const res = await fetch(`${API_URL}/banks/${bankId}/report?${qs.toString()}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  });

  if (res.status === 202) {
    const st = (await res.json()) as BackfillStatus;
    throw new BackfillRunningError(st);
  }

  if (!res.ok) {
    const text = await res.text();
    try {
      const j = JSON.parse(text);
      throw new Error(j?.detail || j?.message || "export_failed");
    } catch {
      throw new Error(text || "export_failed");
    }
  }

  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename || `bank_${bankId}_loan_${loanId}_${start}_to_${end}.xlsx`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export async function listUsers() {
  return await request<UserOut[]>("/users");
}

export async function createUser(body: { username: string; password: string; role: "admin" | "viewer" }) {
  return await request<UserOut>("/users", { method: "POST", body: JSON.stringify(body) });
}

export async function deleteUser(userId: number) {
  return await request<{ ok: boolean }>(`/users/${userId}`, { method: "DELETE" });
}

export type AuditQuery = {
  username?: string;
  entity_type?: string;
  action?: string;
  limit?: number;
};

export async function listAudit(q: AuditQuery = {}) {
  const token = getToken();
  const params = new URLSearchParams();
  if (q.username) params.set("username", q.username);
  if (q.entity_type) params.set("entity_type", q.entity_type);
  if (q.action) params.set("action", q.action);
  if (q.limit != null) params.set("limit", String(q.limit));

  const res = await fetch(`${API_URL}/audit?${params.toString()}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  });

  if (!res.ok) {
    let msg = res.statusText;
    try {
      const j = await res.json();
      msg = j?.detail || j?.message || msg;
    } catch {}
    throw new Error(msg);
  }

  return (await res.json()) as AuditOut[];
}