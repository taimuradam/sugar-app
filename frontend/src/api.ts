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
  category: "principal" | "markup";
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

export type UserOut = { id: number; username: string; role: string; created_at?: string };

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

async function request<T>(path: string, init?: RequestInit) {
  const token = getToken();
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "content-type": "application/json",
      ...(init?.headers || {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });

  if (!res.ok) {
    let detail = `http_${res.status}`;
    try {
      const data = await res.json();
      if (data?.detail) detail = String(data.detail);
    } catch {}
    throw new Error(detail);
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

export async function deleteRate(bankId: number, rateId: number) {
  return await request<{ ok: boolean }>(`/banks/${bankId}/rates/${rateId}`, { method: "DELETE" });
}

export async function listTxs(bankId: number, start?: string, end?: string) {
  const qs = new URLSearchParams();
  if (start) qs.set("start", start);
  if (end) qs.set("end", end);
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  return await request<TxOut[]>(`/banks/${bankId}/transactions${suffix}`);
}

export async function addTx(
  bankId: number,
  body: { date: string; category: "principal" | "markup"; amount: number; note?: string | null }
) {
  return await request<TxOut>(`/banks/${bankId}/transactions`, { method: "POST", body: JSON.stringify(body) });
}

export async function deleteTx(bankId: number, txId: number) {
  return await request<{ ok: boolean }>(`/banks/${bankId}/transactions/${txId}`, { method: "DELETE" });
}

export async function ledger(bankId: number, start: string, end: string) {
  return await request<LedgerRow[]>(
    `/banks/${bankId}/ledger?start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}`
  );
}

export async function downloadReport(bankId: number, start: string, end: string) {
  const token = getToken();
  const res = await fetch(`${API_URL}/banks/${bankId}/report?start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}`, {
    headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
  });
  if (!res.ok) throw new Error(`http_${res.status}`);

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

export async function listUsers() {
  return await request<UserOut[]>("/users");
}

export async function createUser(body: { username: string; password: string; role: "admin" | "user" }) {
  return await request<UserOut>("/users", { method: "POST", body: JSON.stringify(body) });
}

export async function deleteUser(userId: number) {
  return await request<{ ok: boolean }>(`/users/${userId}`, { method: "DELETE" });
}

export async function updateUser(userId: number, body: { password?: string; role?: "admin" | "user" }) {
  return await request<UserOut>(`/users/${userId}`, { method: "PATCH", body: JSON.stringify(body) });
}
