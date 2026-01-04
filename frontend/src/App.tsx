import React, { useEffect, useMemo, useState } from "react";
import { LogOut, Building2, Receipt, LineChart, Percent, Download } from "lucide-react";
import * as api from "./api";
import { Banner, Button, Card, CardBody, CardHeader, Input, Label, Select, Table, Td, Th, cx } from "./ui";

type Tab = "ledger" | "transactions" | "rates" | "report";

function fmtMoney(n: number) {
  if (Number.isNaN(n)) return "-";
  return new Intl.NumberFormat(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(n);
}

export default function App() {
  const [role, setRole] = useState(() => api.getRole());
  const [error, setError] = useState<string>("");

  const authed = Boolean(localStorage.getItem("token"));

  useEffect(() => {
    setRole(api.getRole());
  }, [authed]);

  if (!authed) {
    return <LoginView onError={setError} error={error} onAuthed={() => setRole(api.getRole())} />;
  }

  return (
    <Dashboard
      role={role}
      onLogout={() => {
        api.clearAuth();
        location.reload();
      }}
      onError={setError}
      error={error}
    />
  );
}

function LoginView(props: { onAuthed: () => void; onError: (e: string) => void; error: string }) {
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("admin123");
  const [loading, setLoading] = useState(false);

  return (
    <div className="min-h-screen bg-slate-50">
      <div className="mx-auto flex min-h-screen max-w-5xl items-center justify-center p-6">
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

          <Card className="self-center">
            <CardHeader title="Login" subtitle="Use a user that exists in your database." />
            <CardBody>
              {props.error ? <Banner kind="error" text={props.error} onClose={() => props.onError("")} /> : null}
              <div className="space-y-4">
                <div>
                  <Label>Username</Label>
                  <Input value={username} onChange={(e) => setUsername(e.target.value)} placeholder="admin" />
                </div>
                <div>
                  <Label>Password</Label>
                  <Input value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" type="password" />
                </div>
                <Button
                  className="w-full"
                  disabled={loading}
                  onClick={async () => {
                    props.onError("");
                    setLoading(true);
                    try {
                      const out = await api.login(username, password);
                      api.setRole(out.role);
                      props.onAuthed();
                    } catch (e: any) {
                      props.onError(e?.message || "login failed");
                    } finally {
                      setLoading(false);
                    }
                  }}
                >
                  {loading ? "Signing in..." : "Sign in"}
                </Button>
              </div>
            </CardBody>
          </Card>
        </div>
      </div>
    </div>
  );
}

function Dashboard(props: { role: string; onLogout: () => void; onError: (e: string) => void; error: string }) {
  const [banks, setBanks] = useState<api.BankOut[]>([]);
  const [selectedBankId, setSelectedBankId] = useState<number | null>(null);
  const [tab, setTab] = useState<Tab>("ledger");
  const [loadingBanks, setLoadingBanks] = useState(false);

  const selectedBank = useMemo(() => banks.find((b) => b.id === selectedBankId) || null, [banks, selectedBankId]);

  async function refreshBanks() {
    setLoadingBanks(true);
    try {
      const list = await api.listBanks();
      setBanks(list);
      if (!selectedBankId && list.length) setSelectedBankId(list[0].id);
    } catch (e: any) {
      props.onError(e?.message || "failed to load banks");
    } finally {
      setLoadingBanks(false);
    }
  }

  useEffect(() => {
    refreshBanks();
  }, []);

  return (
    <div className="min-h-screen bg-slate-50">
      <div className="mx-auto max-w-6xl p-6">
        <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="text-sm font-semibold text-slate-500">Sugar App</div>
            <div className="mt-1 text-2xl font-semibold text-slate-900">Finance Dashboard</div>
            <div className="mt-1 text-sm text-slate-600">
              Role: <span className="font-semibold">{props.role}</span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="secondary" onClick={refreshBanks} disabled={loadingBanks}>
              {loadingBanks ? "Refreshing..." : "Refresh"}
            </Button>
            <Button variant="secondary" onClick={props.onLogout}>
              <LogOut className="h-4 w-4" /> Logout
            </Button>
          </div>
        </div>

        {props.error ? <Banner kind="error" text={props.error} onClose={() => props.onError("")} /> : null}

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[320px_1fr]">
          <Card>
            <CardHeader
              title="Banks"
              subtitle="Select a bank to view data."
              right={props.role === "admin" ? <CreateBank onCreated={refreshBanks} onError={props.onError} /> : null}
            />
            <CardBody>
              <div className="space-y-2">
                {banks.length === 0 ? (
                  <div className="text-sm text-slate-600">No banks yet.</div>
                ) : (
                  banks.map((b) => (
                    <button
                      key={b.id}
                      className={cx(
                        "flex w-full items-center justify-between rounded-xl border px-3 py-3 text-left text-sm transition",
                        selectedBankId === b.id ? "border-slate-900 bg-slate-900 text-white" : "border-slate-200 bg-white hover:bg-slate-50"
                      )}
                      onClick={() => setSelectedBankId(b.id)}
                    >
                      <div className="flex items-center gap-2">
                        <Building2 className="h-4 w-4 opacity-80" />
                        <div>
                          <div className="font-semibold">{b.name}</div>
                          <div className={cx("text-xs", selectedBankId === b.id ? "text-slate-200" : "text-slate-500")}>
                            {b.bank_type} {b.additional_rate != null ? `• addl ${b.additional_rate}` : ""}
                          </div>
                        </div>
                      </div>
                      <div className={cx("text-xs", selectedBankId === b.id ? "text-slate-200" : "text-slate-400")}>#{b.id}</div>
                    </button>
                  ))
                )}
              </div>
            </CardBody>
          </Card>

          <Card>
            <CardHeader
              title={selectedBank ? selectedBank.name : "Select a bank"}
              subtitle={selectedBank ? "Test ledger, transactions, rates, and report export." : "Choose a bank from the left."}
              right={
                selectedBank ? (
                  <div className="flex flex-wrap items-center gap-2">
                    <TabButton active={tab === "ledger"} onClick={() => setTab("ledger")} icon={<LineChart className="h-4 w-4" />} label="Ledger" />
                    <TabButton active={tab === "transactions"} onClick={() => setTab("transactions")} icon={<Receipt className="h-4 w-4" />} label="Transactions" />
                    <TabButton active={tab === "rates"} onClick={() => setTab("rates")} icon={<Percent className="h-4 w-4" />} label="Rates" />
                    <TabButton active={tab === "report"} onClick={() => setTab("report")} icon={<Download className="h-4 w-4" />} label="Report" />
                  </div>
                ) : null
              }
            />
            <CardBody>
              {!selectedBank ? (
                <div className="text-sm text-slate-600">Pick a bank to begin.</div>
              ) : tab === "ledger" ? (
                <Ledger bankId={selectedBank.id} onError={props.onError} />
              ) : tab === "transactions" ? (
                <Transactions bankId={selectedBank.id} onError={props.onError} />
              ) : tab === "rates" ? (
                <Rates bankId={selectedBank.id} role={props.role} onError={props.onError} />
              ) : (
                <Report bankId={selectedBank.id} onError={props.onError} />
              )}
            </CardBody>
          </Card>
        </div>
      </div>
    </div>
  );
}

function TabButton(props: { active: boolean; onClick: () => void; icon: React.ReactNode; label: string }) {
  return (
    <button
      onClick={props.onClick}
      className={cx(
        "inline-flex items-center gap-2 rounded-xl border px-3 py-2 text-sm font-medium transition",
        props.active ? "border-slate-900 bg-slate-900 text-white" : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
      )}
    >
      {props.icon}
      {props.label}
    </button>
  );
}

function CreateBank(props: { onCreated: () => void; onError: (e: string) => void }) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [bankType, setBankType] = useState("conventional");
  const [additionalRate, setAdditionalRate] = useState<string>("");
  const [loading, setLoading] = useState(false);

  return (
    <div className="relative">
      <Button variant="secondary" onClick={() => setOpen((v) => !v)}>
        + New
      </Button>
      {open ? (
        <div className="absolute right-0 z-10 mt-2 w-[320px] rounded-2xl border border-slate-200 bg-white p-4 shadow-lg">
          <div className="mb-3 text-sm font-semibold text-slate-900">Create Bank (admin)</div>
          <div className="space-y-3">
            <div>
              <Label>Name</Label>
              <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Bank A" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>Type</Label>
                <Select value={bankType} onChange={(e) => setBankType(e.target.value)}>
                  <option value="conventional">conventional</option>
                  <option value="islamic">islamic</option>
                </Select>
              </div>
              <div>
                <Label>Additional rate</Label>
                <Input value={additionalRate} onChange={(e) => setAdditionalRate(e.target.value)} placeholder="e.g. 0.50" inputMode="decimal" />
              </div>
            </div>
            <div className="flex gap-2">
              <Button
                disabled={loading}
                onClick={async () => {
                  props.onError("");
                  setLoading(true);
                  try {
                    const ar = additionalRate.trim() ? Number(additionalRate) : null;
                    await api.createBank({ name: name.trim(), bank_type: bankType, additional_rate: ar });
                    setName("");
                    setAdditionalRate("");
                    setOpen(false);
                    props.onCreated();
                  } catch (e: any) {
                    props.onError(e?.message || "failed to create bank");
                  } finally {
                    setLoading(false);
                  }
                }}
              >
                {loading ? "Creating..." : "Create"}
              </Button>
              <Button variant="secondary" onClick={() => setOpen(false)}>
                Cancel
              </Button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function Ledger(props: { bankId: number; onError: (e: string) => void }) {
  const today = new Date();
  const yyyy = today.getFullYear();
  const mm = String(today.getMonth() + 1).padStart(2, "0");
  const dd = String(today.getDate()).padStart(2, "0");
  const defaultEnd = `${yyyy}-${mm}-${dd}`;
  const defaultStart = `${yyyy}-${mm}-01`;

  const [start, setStart] = useState(defaultStart);
  const [end, setEnd] = useState(defaultEnd);
  const [rows, setRows] = useState<api.LedgerRow[]>([]);
  const [loading, setLoading] = useState(false);

  async function run() {
    props.onError("");
    setLoading(true);
    try {
      const out = await api.getLedger(props.bankId, start, end);
      setRows(out);
    } catch (e: any) {
      props.onError(e?.message || "failed to load ledger");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    run();
  }, [props.bankId]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-3">
        <div>
          <Label>Start</Label>
          <Input type="date" value={start} onChange={(e) => setStart(e.target.value)} />
        </div>
        <div>
          <Label>End</Label>
          <Input type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
        </div>
        <Button onClick={run} disabled={loading}>
          {loading ? "Loading..." : "Run"}
        </Button>
      </div>

      <Table>
        <thead>
          <tr>
            <Th>Date</Th>
            <Th>Principal balance</Th>
            <Th>Daily markup</Th>
            <Th>Accrued markup</Th>
            <Th>Rate %</Th>
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <Td className="text-slate-500" colSpan={5 as any}>
                No rows.
              </Td>
            </tr>
          ) : (
            rows.map((r, i) => (
              <tr key={i}>
                <Td>{r.date}</Td>
                <Td>{fmtMoney(r.principal_balance)}</Td>
                <Td>{fmtMoney(r.daily_markup)}</Td>
                <Td>{fmtMoney(r.accrued_markup)}</Td>
                <Td>{fmtMoney(r.rate_percent)}</Td>
              </tr>
            ))
          )}
        </tbody>
      </Table>
    </div>
  );
}

function Transactions(props: { bankId: number; onError: (e: string) => void }) {
  const today = new Date();
  const yyyy = today.getFullYear();
  const mm = String(today.getMonth() + 1).padStart(2, "0");
  const dd = String(today.getDate()).padStart(2, "0");
  const defaultEnd = `${yyyy}-${mm}-${dd}`;
  const defaultStart = `${yyyy}-${mm}-01`;

  const [start, setStart] = useState(defaultStart);
  const [end, setEnd] = useState(defaultEnd);
  const [rows, setRows] = useState<api.TxOut[]>([]);
  const [loading, setLoading] = useState(false);

  const [date, setDate] = useState(defaultEnd);
  const [category, setCategory] = useState("principal");
  const [amount, setAmount] = useState<string>("");
  const [note, setNote] = useState<string>("");

  async function refresh() {
    props.onError("");
    setLoading(true);
    try {
      const out = await api.listTxs(props.bankId, start, end);
      setRows(out);
    } catch (e: any) {
      props.onError(e?.message || "failed to load transactions");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, [props.bankId]);

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end gap-3">
        <div>
          <Label>Filter start</Label>
          <Input type="date" value={start} onChange={(e) => setStart(e.target.value)} />
        </div>
        <div>
          <Label>Filter end</Label>
          <Input type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
        </div>
        <Button onClick={refresh} disabled={loading}>
          {loading ? "Loading..." : "Apply"}
        </Button>
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white p-4">
        <div className="mb-3 text-sm font-semibold text-slate-900">Add transaction</div>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
          <div>
            <Label>Date</Label>
            <Input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
          </div>
          <div>
            <Label>Category</Label>
            <Select value={category} onChange={(e) => setCategory(e.target.value)}>
              <option value="principal">principal</option>
              <option value="markup">markup</option>
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
            onClick={async () => {
              props.onError("");
              try {
                const parsed = Number(amount);
                if (!Number.isFinite(parsed) || Math.abs(parsed) < 1e-12) {
                  throw new Error("Amount must be a non-zero number");
                }
                await api.addTx(props.bankId, {
                  date,
                  category,
                  amount: parsed,
                  note: note.trim() ? note.trim() : null,
});

                setAmount("");
                setNote("");
                await refresh();
              } catch (e: any) {
                props.onError(e?.message || "failed to add transaction");
              }
            }}
          >
            Add
          </Button>
        </div>
      </div>

      <Table>
        <thead>
          <tr>
            <Th>Date</Th>
            <Th>Category</Th>
            <Th>Amount</Th>
            <Th>Note</Th>
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <Td className="text-slate-500" colSpan={4 as any}>
                No transactions.
              </Td>
            </tr>
          ) : (
            rows.map((t) => (
              <tr key={t.id}>
                <Td>{t.date}</Td>
                <Td>{t.category}</Td>
                <Td>{fmtMoney(t.amount)}</Td>
                <Td className="max-w-[420px] truncate whitespace-nowrap">{t.note || ""}</Td>
              </tr>
            ))
          )}
        </tbody>
      </Table>
    </div>
  );
}

function Rates(props: { bankId: number; role: string; onError: (e: string) => void }) {
  const today = new Date();
  const yyyy = today.getFullYear();
  const mm = String(today.getMonth() + 1).padStart(2, "0");
  const dd = String(today.getDate()).padStart(2, "0");
  const defaultDate = `${yyyy}-${mm}-${dd}`;

  const [rows, setRows] = useState<api.RateOut[]>([]);
  const [loading, setLoading] = useState(false);

  const [effectiveDate, setEffectiveDate] = useState(defaultDate);
  const [rate, setRate] = useState<string>("");

  async function refresh() {
    props.onError("");
    setLoading(true);
    try {
      const out = await api.listRates(props.bankId);
      setRows(out);
    } catch (e: any) {
      props.onError(e?.message || "failed to load rates");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, [props.bankId]);

  return (
    <div className="space-y-5">
      {props.role === "admin" ? (
        <div className="rounded-2xl border border-slate-200 bg-white p-4">
          <div className="mb-3 text-sm font-semibold text-slate-900">Add rate (admin)</div>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
            <div>
              <Label>Effective date</Label>
              <Input type="date" value={effectiveDate} onChange={(e) => setEffectiveDate(e.target.value)} />
            </div>
            <div>
              <Label>Annual rate (%)</Label>
              <Input value={rate} onChange={(e) => setRate(e.target.value)} placeholder="e.g. 12.5" inputMode="decimal" />
            </div>
            <div className="flex items-end">
              <Button
                onClick={async () => {
                  props.onError("");
                  try {
                    await api.addRate(props.bankId, { effective_date: effectiveDate, annual_rate_percent: Number(rate) });
                    setRate("");
                    await refresh();
                  } catch (e: any) {
                    props.onError(e?.message || "failed to add rate");
                  }
                }}
              >
                Add
              </Button>
            </div>
          </div>
        </div>
      ) : (
        <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700">
          Rates can only be added by <span className="font-semibold">admin</span>.
        </div>
      )}

      <div className="flex items-center justify-between">
        <div className="text-sm text-slate-600">Rates are applied by effective date in your ledger computation.</div>
        <Button variant="secondary" onClick={refresh} disabled={loading}>
          {loading ? "Loading..." : "Refresh"}
        </Button>
      </div>

      <Table>
        <thead>
          <tr>
            <Th>Effective date</Th>
            <Th>Annual rate %</Th>
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <Td className="text-slate-500" colSpan={2 as any}>
                No rates.
              </Td>
            </tr>
          ) : (
            rows.map((r) => (
              <tr key={r.id}>
                <Td>{r.effective_date}</Td>
                <Td>{fmtMoney(r.annual_rate_percent)}</Td>
              </tr>
            ))
          )}
        </tbody>
      </Table>
    </div>
  );
}

function Report(props: { bankId: number; onError: (e: string) => void }) {
  const today = new Date();
  const yyyy = today.getFullYear();
  const mm = String(today.getMonth() + 1).padStart(2, "0");
  const dd = String(today.getDate()).padStart(2, "0");
  const defaultEnd = `${yyyy}-${mm}-${dd}`;
  const defaultStart = `${yyyy}-${mm}-01`;

  const [start, setStart] = useState(defaultStart);
  const [end, setEnd] = useState(defaultEnd);
  const [loading, setLoading] = useState(false);

  return (
    <div className="space-y-4">
      <div className="rounded-2xl border border-slate-200 bg-white p-4">
        <div className="mb-3 text-sm font-semibold text-slate-900">Download Excel report</div>
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <Label>Start</Label>
            <Input type="date" value={start} onChange={(e) => setStart(e.target.value)} />
          </div>
          <div>
            <Label>End</Label>
            <Input type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
          </div>
          <Button
            disabled={loading}
            onClick={async () => {
              props.onError("");
              setLoading(true);
              try {
                await api.downloadReport(props.bankId, start, end);
              } catch (e: any) {
                props.onError(e?.message || "failed to download report");
              } finally {
                setLoading(false);
              }
            }}
          >
            <Download className="h-4 w-4" />
            {loading ? "Preparing..." : "Download"}
          </Button>
        </div>
      </div>

      <div className="text-sm text-slate-600">
        Calls <span className="font-mono">GET /banks/{props.bankId}/report</span> and downloads the XLSX.
      </div>
    </div>
  );
}
