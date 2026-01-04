const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

export type TokenOut = { access_token: string; token_type?: string; role: string };

export type BankOut = {
  id: number;
  name: string;
  bank_type: string;
  additional_rate: number | null;
  created_at?: string;
};

export type RateOut = {
  id: number;
  bank_id: number;
  effective_date: string;
  annual_rate_percent: number;
  created_at?: string;
};

export type TxOut = {
  id: number;
  bank_id: number;
  date: string;
  category: string;
  amount: number;
  note: string | null;
  created_at?: string;
};

export type LedgerRow = {
  date: string;
  principal_balance: number;
  daily_markup: number;
  accrued_markup: number;
  rate_percent: number;
};

function getToken() {
  return localStorage.getItem("token") || "";
}

export function setToken(token: string) {
  localStorage.setItem("token", token);
}

export function clearAuth() {
  localStorage.removeItem("token");
  localStorage.removeItem("role");
}

export function setRole(role: string) {
  localStorage.setItem("role", role);
}

export function getRole() {
  return localStorage.getItem("role") || "";
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init.headers as Record<string, string> | undefined),
  };
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(`${API_URL}${path}`, { ...init, headers });

  if (!res.ok) {
    let detail = "";
    try {
      const data = await res.json();
      detail = data?.detail ? String(data.detail) : JSON.stringify(data);
    } catch {
      detail = await res.text();
    }
    throw new Error(`${res.status} ${res.statusText} ${detail}`.trim());
  }

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export async function login(username: string, password: string) {
  const out = await request<TokenOut>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
  setToken(out.access_token);
  setRole(out.role);
  return out;
}

export async function listBanks() {
  return await request<BankOut[]>("/banks");
}

export async function createBank(body: { name: string; bank_type: string; additional_rate?: number | null }) {
  return await request<BankOut>("/banks", { method: "POST", body: JSON.stringify(body) });
}

export async function listRates(bankId: number) {
  return await request<RateOut[]>(`/banks/${bankId}/rates`);
}

export async function addRate(bankId: number, body: { effective_date: string; annual_rate_percent: number }) {
  return await request<RateOut>(`/banks/${bankId}/rates`, { method: "POST", body: JSON.stringify(body) });
}

export async function listTxs(bankId: number, start?: string, end?: string) {
  const qs = new URLSearchParams();
  if (start) qs.set("start", start);
  if (end) qs.set("end", end);
  const suffix = qs.toString() ? `?${qs}` : "";
  return await request<TxOut[]>(`/banks/${bankId}/transactions${suffix}`);
}

export async function addTx(bankId: number, body: { date: string; category: string; amount: number; note?: string | null }) {
  return await request<TxOut>(`/banks/${bankId}/transactions`, { method: "POST", body: JSON.stringify(body) });
}

export async function getLedger(bankId: number, start: string, end: string) {
  const qs = new URLSearchParams({ start, end });
  return await request<LedgerRow[]>(`/banks/${bankId}/ledger?${qs}`);
}

export async function downloadReport(bankId: number, start: string, end: string) {
  const token = getToken();
  const qs = new URLSearchParams({ start, end });

  const res = await fetch(`${API_URL}/banks/${bankId}/report?${qs}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });

  if (!res.ok) {
    const txt = await res.text();
    throw new Error(`${res.status} ${res.statusText} ${txt}`.trim());
  }

  const blob = await res.blob();
  const cd = res.headers.get("content-disposition") || "";
  const m = cd.match(/filename="([^"]+)"/);
  const filename = m?.[1] || `bank_${bankId}_${start}_to_${end}.xlsx`;

  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
