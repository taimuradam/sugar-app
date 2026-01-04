import React, { useEffect, useMemo, useState } from "react";
import { LogOut, Building2, Receipt, LineChart, Percent, Download, Users, Trash2, Plus } from "lucide-react";
import * as api from "./api";
import { Banner, Button, Card, CardBody, CardHeader, Input, Label, Select, Table, Td, Th, cx } from "./ui";

type Tab = "ledger" | "transactions" | "rates" | "report" | "users";

function fmtMoney(n: number) {
  if (Number.isNaN(n)) return "-";
  return new Intl.NumberFormat(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(n);
}

function todayISO() {
  const d = new Date();
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}`;
}

export default function App() {
  const [role, setRole] = useState(() => api.getRole());
  const [error, setError] = useState<string>("");

  const [tokenReady, setTokenReady] = useState(() => !!localStorage.getItem("token"));
  const [tab, setTab] = useState<Tab>("ledger");

  const [banks, setBanks] = useState<api.BankOut[]>([]);
  const [selectedBankId, setSelectedBankId] = useState<number>(0);
  const [loadingBanks, setLoadingBanks] = useState(false);

  const isAdmin = role === "admin";

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

  useEffect(() => {
    if (!tokenReady) return;
    refreshBanks(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tokenReady]);

  const selectedBank = useMemo(() => banks.find((b) => b.id === selectedBankId) || null, [banks, selectedBankId]);

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
      <div className="mx-auto max-w-6xl px-4 py-10">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="rounded-2xl border border-slate-200 bg-white p-3">
              <Building2 className="h-5 w-5 text-slate-700" />
            </div>
            <div>
              <div className="text-sm font-semibold text-slate-900">Finance dashboard</div>
              <div className="text-xs text-slate-500">
                Role: <span className="font-mono">{role}</span>
              </div>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <div className="w-[320px]">
              <Label>Bank</Label>
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

            <Button
              kind="secondary"
              onClick={() => {
                api.clearToken();
                setTokenReady(false);
                setRole("");
              }}
            >
              <LogOut className="h-4 w-4" />
              Logout
            </Button>
          </div>
        </div>

        <div className="mt-6">{error ? <Banner kind="error" text={error} onClose={() => setError("")} /> : null}</div>

        <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-[260px_1fr]">
          <div className="space-y-3">
            <NavButton active={tab === "ledger"} onClick={() => setTab("ledger")} icon={<LineChart className="h-4 w-4" />} text="Ledger" />
            <NavButton active={tab === "transactions"} onClick={() => setTab("transactions")} icon={<Receipt className="h-4 w-4" />} text="Transactions" />
            <NavButton active={tab === "rates"} onClick={() => setTab("rates")} icon={<Percent className="h-4 w-4" />} text="Rates" />
            <NavButton active={tab === "report"} onClick={() => setTab("report")} icon={<Download className="h-4 w-4" />} text="Export report" />
            {isAdmin ? <NavButton active={tab === "users"} onClick={() => setTab("users")} icon={<Users className="h-4 w-4" />} text="Users" /> : null}

            <Card>
              <CardHeader title="Bank details" subtitle="Matches the old project concept (type + additional rate)." />
              <CardBody>
                {!selectedBank ? (
                  <div className="text-sm text-slate-600">No bank selected.</div>
                ) : (
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <div className="text-slate-600">Type</div>
                      <div className="font-mono">{selectedBank.bank_type}</div>
                    </div>
                    <div className="flex justify-between">
                      <div className="text-slate-600">Additional rate</div>
                      <div className="font-mono">{selectedBank.additional_rate ?? 0}</div>
                    </div>
                  </div>
                )}
              </CardBody>
            </Card>

            {isAdmin ? <CreateBankCard onCreated={() => refreshBanks(true)} onError={setError} /> : null}
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
              <Ledger bankId={selectedBankId} onError={setError} />
            ) : tab === "transactions" ? (
              <Transactions bankId={selectedBankId} role={role} onError={setError} />
            ) : tab === "rates" ? (
              <Rates bankId={selectedBankId} role={role} onError={setError} />
            ) : tab === "report" ? (
              <Report bankId={selectedBankId} onError={setError} />
            ) : (
              <UsersTab role={role} onError={setError} />
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
        "flex w-full items-center gap-2 rounded-2xl border px-4 py-3 text-left text-sm font-medium transition",
        props.active ? "border-slate-300 bg-white text-slate-900" : "border-slate-200 bg-slate-50 text-slate-700 hover:bg-white"
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

function CreateBankCard(props: { onCreated: () => void; onError: (e: string) => void }) {
  const [name, setName] = useState("");
  const [bankType, setBankType] = useState("conventional");
  const [additionalRate, setAdditionalRate] = useState<string>("0");
  const [loading, setLoading] = useState(false);

  return (
    <Card>
      <CardHeader title="Create bank" subtitle="You need at least one bank to test the app." />
      <CardBody>
        <div className="space-y-3">
          <div>
            <Label>Name</Label>
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g., Bank Alfalah" />
          </div>
          <div>
            <Label>Type</Label>
            <Select value={bankType} onChange={(e) => setBankType(e.target.value)}>
              <option value="conventional">conventional</option>
              <option value="islamic">islamic</option>
            </Select>
          </div>
          <div>
            <Label>Additional rate (optional)</Label>
            <Input value={additionalRate} onChange={(e) => setAdditionalRate(e.target.value)} inputMode="decimal" placeholder="0" />
          </div>

          <Button
            onClick={async () => {
              props.onError("");
              const nm = name.trim();
              if (!nm) {
                props.onError("bank_name_required");
                return;
              }
              const add = additionalRate.trim() ? Number(additionalRate) : 0;
              if (!Number.isFinite(add)) {
                props.onError("additional_rate_invalid");
                return;
              }

              setLoading(true);
              try {
                await api.createBank({ name: nm, bank_type: bankType, additional_rate: add });
                setName("");
                setAdditionalRate("0");
                props.onCreated();
              } catch (e: any) {
                props.onError(e?.message || "failed_to_create_bank");
              } finally {
                setLoading(false);
              }
            }}
            disabled={loading}
          >
            <Plus className="h-4 w-4" />
            {loading ? "Creating..." : "Create"}
          </Button>
        </div>
      </CardBody>
    </Card>
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

  async function refresh() {
    props.onError("");
    setLoading(true);
    try {
      const out = await api.ledger(props.bankId, start, end);
      setRows(out);
    } catch (e: any) {
      props.onError(e?.message || "failed_to_load_ledger");
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
          <Label>Start</Label>
          <Input type="date" value={start} onChange={(e) => setStart(e.target.value)} />
        </div>
        <div>
          <Label>End</Label>
          <Input type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
        </div>
        <Button onClick={refresh} kind="secondary">
          {loading ? "Loading..." : "Refresh"}
        </Button>
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white p-4">
        <div className="mb-3 text-sm font-semibold text-slate-900">Ledger rows</div>
        <Table>
          <thead>
            <tr>
              <Th>Date</Th>
              <Th>Principal Balance</Th>
              <Th>Daily Markup</Th>
              <Th>Accrued Markup</Th>
              <Th>Rate %</Th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <Td colSpan={5} className="text-slate-600">
                  No rows. Add rates + transactions and refresh.
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
    </div>
  );
}

function Transactions(props: { bankId: number; role: string; onError: (e: string) => void }) {
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
  const [category, setCategory] = useState<"principal" | "markup">("principal");
  const [direction, setDirection] = useState<"debit" | "credit">("debit");
  const [amount, setAmount] = useState<string>("");
  const [note, setNote] = useState<string>("");

  const isAdmin = props.role === "admin";

  async function refresh() {
    props.onError("");
    setLoading(true);
    try {
      const out = await api.listTxs(props.bankId, start, end);
      setRows(out);
    } catch (e: any) {
      props.onError(e?.message || "failed_to_load_transactions");
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
        <Button kind="secondary" onClick={refresh}>
          {loading ? "Loading..." : "Apply"}
        </Button>
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white p-4">
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
            onClick={async () => {
              props.onError("");
              try {
                const parsed = Number(amount);
                if (!Number.isFinite(parsed) || Math.abs(parsed) < 1e-12) throw new Error("amount_invalid");
                const signed = direction === "credit" ? -Math.abs(parsed) : Math.abs(parsed);
                await api.addTx(props.bankId, { date, category, amount: signed, note: note.trim() ? note.trim() : null });
                setAmount("");
                setNote("");
                await refresh();
              } catch (e: any) {
                props.onError(e?.message || "failed_to_add_tx");
              }
            }}
          >
            Add
          </Button>
        </div>
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white p-4">
        <div className="mb-3 text-sm font-semibold text-slate-900">Transactions</div>
        <Table>
          <thead>
            <tr>
              <Th>Date</Th>
              <Th>Category</Th>
              <Th>Direction</Th>
              <Th>Amount</Th>
              <Th>Note</Th>
              {isAdmin ? <Th /> : null}
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <Td colSpan={isAdmin ? 6 : 5} className="text-slate-600">
                  No transactions in range.
                </Td>
              </tr>
            ) : (
              rows.map((t) => {
                const dir = t.amount < 0 ? "credit" : "debit";
                const abs = Math.abs(t.amount);
                return (
                  <tr key={t.id}>
                    <Td>{t.date}</Td>
                    <Td className="font-mono">{t.category}</Td>
                    <Td className="font-mono">{dir}</Td>
                    <Td className="font-mono">{fmtMoney(abs)}</Td>
                    <Td className="max-w-[420px] truncate whitespace-nowrap">{t.note || ""}</Td>
                    {isAdmin ? (
                      <Td className="text-right">
                        <button
                          className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
                          onClick={async () => {
                            props.onError("");
                            try {
                              await api.deleteTx(props.bankId, t.id);
                              await refresh();
                            } catch (e: any) {
                              props.onError(e?.message || "failed_to_delete_tx");
                            }
                          }}
                        >
                          <Trash2 className="h-4 w-4" />
                          Delete
                        </button>
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

function Rates(props: { bankId: number; role: string; onError: (e: string) => void }) {
  const today = new Date();
  const yyyy = today.getFullYear();
  const mm = String(today.getMonth() + 1).padStart(2, "0");
  const dd = String(today.getDate()).padStart(2, "0");
  const defaultDate = `${yyyy}-${mm}-${dd}`;

  const [rows, setRows] = useState<api.RateOut[]>([]);
  const [loading, setLoading] = useState(false);

  const [effectiveDate, setEffectiveDate] = useState(defaultDate);
  const [annualRate, setAnnualRate] = useState<string>("");

  const isAdmin = props.role === "admin";

  async function refresh() {
    props.onError("");
    setLoading(true);
    try {
      const out = await api.listRates(props.bankId);
      setRows(out);
    } catch (e: any) {
      props.onError(e?.message || "failed_to_load_rates");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, [props.bankId]);

  return (
    <div className="space-y-5">
      <div className="rounded-2xl border border-slate-200 bg-white p-4">
        <div className="mb-3 text-sm font-semibold text-slate-900">Add rate</div>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
          <div>
            <Label>Effective date</Label>
            <Input type="date" value={effectiveDate} onChange={(e) => setEffectiveDate(e.target.value)} />
          </div>
          <div>
            <Label>Annual rate %</Label>
            <Input value={annualRate} onChange={(e) => setAnnualRate(e.target.value)} placeholder="12.5" inputMode="decimal" />
          </div>
          <div className="flex items-end">
            <Button
              onClick={async () => {
                props.onError("");
                try {
                  const parsed = Number(annualRate);
                  if (!Number.isFinite(parsed)) throw new Error("rate_invalid");
                  await api.addRate(props.bankId, { effective_date: effectiveDate, annual_rate_percent: parsed });
                  setAnnualRate("");
                  await refresh();
                } catch (e: any) {
                  props.onError(e?.message || "failed_to_add_rate");
                }
              }}
              disabled={!isAdmin}
              title={!isAdmin ? "Admin only" : ""}
            >
              Add
            </Button>
          </div>
        </div>
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white p-4">
        <div className="mb-3 text-sm font-semibold text-slate-900">Rates</div>
        <Table>
          <thead>
            <tr>
              <Th>Effective date</Th>
              <Th>Annual rate %</Th>
              {isAdmin ? <Th /> : null}
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <Td colSpan={isAdmin ? 3 : 2} className="text-slate-600">
                  No rates yet.
                </Td>
              </tr>
            ) : (
              rows.map((r) => (
                <tr key={r.id}>
                  <Td>{r.effective_date}</Td>
                  <Td className="font-mono">{fmtMoney(r.annual_rate_percent)}</Td>
                  {isAdmin ? (
                    <Td className="text-right">
                      <button
                        className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
                        onClick={async () => {
                          props.onError("");
                          try {
                            await api.deleteRate(props.bankId, r.id);
                            await refresh();
                          } catch (e: any) {
                            props.onError(e?.message || "failed_to_delete_rate");
                          }
                        }}
                      >
                        <Trash2 className="h-4 w-4" />
                        Delete
                      </button>
                    </Td>
                  ) : null}
                </tr>
              ))
            )}
          </tbody>
        </Table>
      </div>

      <div className="text-sm text-slate-600">
        Ledger math uses these rates + bank additional rate to calculate daily markup.
      </div>
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
    <div className="space-y-5">
      <div className="rounded-2xl border border-slate-200 bg-white p-4">
        <div className="mb-3 text-sm font-semibold text-slate-900">Download Excel report</div>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
          <div>
            <Label>Start</Label>
            <Input type="date" value={start} onChange={(e) => setStart(e.target.value)} />
          </div>
          <div>
            <Label>End</Label>
            <Input type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
          </div>
          <div className="flex items-end">
            <Button
              onClick={async () => {
                props.onError("");
                setLoading(true);
                try {
                  await api.downloadReport(props.bankId, start, end);
                } catch (e: any) {
                  props.onError(e?.message || "failed_to_download_report");
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
      </div>

      <div className="text-sm text-slate-600">
        Calls <span className="font-mono">GET /banks/{props.bankId}/report</span> and downloads the XLSX.
      </div>
    </div>
  );
}

function UsersTab(props: { role: string; onError: (e: string) => void }) {
  const isAdmin = props.role === "admin";
  const [rows, setRows] = useState<api.UserOut[]>([]);
  const [loading, setLoading] = useState(false);

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<"admin" | "user">("user");

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
              <option value="user">user</option>
              <option value="admin">admin</option>
            </Select>
          </div>
          <div className="flex items-end">
            <Button
              onClick={async () => {
                props.onError("");
                try {
                  await api.createUser({ username, password, role });
                  setUsername("");
                  setPassword("");
                  setRole("user");
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
        <Button kind="secondary" onClick={refresh}>
          {loading ? "Loading..." : "Refresh"}
        </Button>

        <div className="mt-3">
          <Table>
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
                rows.map((u) => (
                  <tr key={u.id}>
                    <Td className="font-mono">{u.username}</Td>
                    <Td className="font-mono">{u.role}</Td>
                    <Td className="text-right">
                      <button
                        className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
                        onClick={async () => {
                          props.onError("");
                          try {
                            await api.deleteUser(u.id);
                            await refresh();
                          } catch (e: any) {
                            props.onError(e?.message || "failed_to_delete_user");
                          }
                        }}
                      >
                        <Trash2 className="h-4 w-4" />
                        Delete
                      </button>
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