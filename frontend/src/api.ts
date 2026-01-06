const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

export type TokenOut = { access_token: string; token_type?: string; role: string };

export type BankOut = {
  id: number;
  name: string;
  bank_type: string;
  created_at?: string;

  settings_year: number;
  kibor_tenor_months: 1 | 3 | 6;
  additional_rate: number | null;
  kibor_placeholder_rate_percent: number;
  max_loan_amount: number | null;

  kibor_started?: boolean;
  kibor_start_date?: string | null;

  current_kibor_rate_percent?: number | null;
  current_kibor_effective_date?: string | null;
  current_total_rate_percent?: number | null;

  principal_balance?: number;
  remaining_loan_amount?: number | null;
  loan_utilization_percent?: number | null;
};

export type TxOut = {
  id: number;
  bank_id: number;
  date: string;
  category: string;
  amount: number;
  note?: string | null;
  created_at?: string;
};

export type LedgerRow = {
  date: string;
  principal_balance: number;
  daily_markup: number;
  accrued_markup: number;
  rate_percent: number;
};

export type UserOut = { id: number; username: string; role: string; created_at?: string };

export type AuditOut = {
  id: number;
  created_at: string;
  username: string;
  action: string;
  entity_type: string;
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

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getToken();
  const headers: any = { "Content-Type": "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`${API_URL}${path}`, { ...init, headers: { ...headers, ...(init?.headers || {}) } });

  const text = await res.text();
  if (!res.ok) {
    try {
      const j = JSON.parse(text);
      throw new Error(j?.detail || "request_failed");
    } catch {
      throw new Error(text || "request_failed");
    }
  }
  return text ? (JSON.parse(text) as T) : (undefined as T);
}

export async function login(username: string, password: string) {
  const out = await request<TokenOut>("/auth/login", { method: "POST", body: JSON.stringify({ username, password }) });
  const role = out.role === "user" ? "viewer" : out.role;
  setToken(out.access_token);
  setRole(role);
  return { ...out, role };
}

export async function listBanks() {
  return await request<BankOut[]>("/banks");
}

export async function createBank(body: {
  name: string;
  bank_type: string;
  kibor_tenor_months: 1 | 3 | 6;
  additional_rate?: number | null;
  kibor_placeholder_rate_percent: number;
  max_loan_amount?: number | null;
  year?: number | null;
}) {
  return await request<BankOut>("/banks", { method: "POST", body: JSON.stringify(body) });
}

export async function listTxs(bankId: number, start?: string, end?: string) {
  const qs = new URLSearchParams();
  if (start) qs.set("start", start);
  if (end) qs.set("end", end);
  const path = qs.toString()
    ? `/banks/${bankId}/transactions?${qs.toString()}`
    : `/banks/${bankId}/transactions`;
  return await request<TxOut[]>(path);
}

export async function addTx(
  bankId: number,
  body: { date: string; category: string; amount: number; note?: string | null }
) {
  return await request<TxOut>(`/banks/${bankId}/transactions`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function deleteTx(bankId: number, txId: number) {
  return await request<{ ok: boolean }>(`/banks/${bankId}/transactions/${txId}`, {
    method: "DELETE",
  });
}

export async function ledger(bankId: number, start: string, end: string) {
  const qs = new URLSearchParams({ start, end });
  return await request<LedgerRow[]>(`/banks/${bankId}/ledger?${qs.toString()}`);
}

/** App.tsx uses this name */
export async function downloadReport(bankId: number, start: string, end: string) {
  const qs = new URLSearchParams({ start, end });
  const token = getToken();

  const res = await fetch(`${API_URL}/banks/${bankId}/report?${qs.toString()}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  });

  if (!res.ok) {
    const text = await res.text();
    try {
      const j = JSON.parse(text);
      throw new Error(j?.detail || "export_failed");
    } catch {
      throw new Error(text || "export_failed");
    }
  }
  return await res.blob();
}

/** Optional newer name */
export const exportReport = downloadReport;

export async function listUsers() {
  return await request<UserOut[]>("/users");
}

export async function createUser(body: { username: string; password: string; role: string }) {
  return await request<UserOut>("/users", { method: "POST", body: JSON.stringify(body) });
}

export async function deleteUser(userId: number) {
  return await request<{ ok: boolean }>(`/users/${userId}`, { method: "DELETE" });
}

export async function listAudit(params?: { username?: string; entity_type?: string; action?: string; limit?: number }) {
  const qs = new URLSearchParams();
  if (params?.username) qs.set("username", params.username);
  if (params?.entity_type) qs.set("entity_type", params.entity_type);
  if (params?.action) qs.set("action", params.action);
  qs.set("limit", String(params?.limit ?? 200));

  const path = qs.toString() ? `/audit?${qs.toString()}` : "/audit";
  return await request<AuditOut[]>(path);
}