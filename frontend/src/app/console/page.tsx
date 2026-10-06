"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Company,
  createRole,
  generateJd,
  getCompany,
  listRoles,
  Role,
  RulePredicate,
  updateCompany,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function ConsolePage() {
  const { token, setToken } = useAuth();
  const router = useRouter();
  const [company, setCompany] = useState<Company | null>(null);
  const [roles, setRoles] = useState<Role[]>([]);
  const [selected, setSelected] = useState<Role | null>(null);
  const [jd, setJd] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  useEffect(() => {
    if (!token) {
      router.replace("/");
      return;
    }
    void (async () => {
      try {
        const [c, r] = await Promise.all([getCompany(token), listRoles(token)]);
        setCompany(c);
        setRoles(r);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load");
      }
    })();
  }, [token, router]);

  async function onCreateRole(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!token) return;
    setPending(true);
    setError(null);
    const fd = new FormData(e.currentTarget);
    const stated: RulePredicate[] = parsePredicates(String(fd.get("stated_filters") || ""));
    const hidden: RulePredicate[] = parsePredicates(String(fd.get("hidden_filters") || ""));
    try {
      const role = await createRole(token, {
        title: String(fd.get("title") || ""),
        department: String(fd.get("department") || "") || undefined,
        location: String(fd.get("location") || "") || undefined,
        employment_type: String(fd.get("employment_type") || "") || undefined,
        brief_text: String(fd.get("brief_text") || ""),
        stated_filters: stated,
        hidden_filters: hidden,
        extract_filters: fd.get("extract_filters") === "on",
      });
      setRoles((prev) => [role, ...prev]);
      setSelected(role);
      setJd(null);
      e.currentTarget.reset();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Create failed");
    } finally {
      setPending(false);
    }
  }

  async function onGenerateJd() {
    if (!token || !selected) return;
    setPending(true);
    setError(null);
    try {
      const res = await generateJd(token, selected.id);
      setJd(res.jd);
      setRoles((prev) =>
        prev.map((r) => (r.id === selected.id ? { ...r, jd: res.jd, status: "jd_ready" } : r)),
      );
      setSelected((prev) => (prev ? { ...prev, jd: res.jd, status: "jd_ready" } : prev));
    } catch (err) {
      setError(err instanceof Error ? err.message : "JD generation failed");
    } finally {
      setPending(false);
    }
  }

  async function toggleGate(flag: "auto_approve_gate1" | "auto_approve_gate2") {
    if (!token || !company) return;
    const next = await updateCompany(token, { [flag]: !company[flag] });
    setCompany(next);
  }

  if (!token) return null;

  return (
    <main className="mx-auto min-h-screen max-w-6xl px-6 py-10">
      <header className="mb-8 flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-sm font-medium uppercase tracking-[0.2em] text-primary">HireFlow</p>
          <h1 className="text-3xl font-semibold tracking-tight">Hiring console</h1>
          <p className="text-muted-foreground">
            {company ? `${company.name} · /${company.slug}` : "Loading company…"}
          </p>
        </div>
        <div className="flex gap-2">
          <Button type="button" variant="outline" onClick={() => router.push("/")}>
            Home
          </Button>
          <Button
            type="button"
            variant="secondary"
            onClick={() => {
              setToken(null);
              router.push("/");
            }}
          >
            Sign out
          </Button>
        </div>
      </header>

      {company ? (
        <section className="mb-8 rounded-lg border border-border bg-white/70 p-4">
          <h2 className="mb-2 text-lg font-semibold">Auto-gates</h2>
          <p className="mb-3 text-sm text-muted-foreground">
            Checkpoints always evaluate + audit. These flags only control whether humans must click.
          </p>
          <div className="flex flex-wrap gap-3">
            <Button type="button" variant="outline" onClick={() => void toggleGate("auto_approve_gate1")}>
              Gate 1 (post-sourcing): {company.auto_approve_gate1 ? "auto" : "human"}
            </Button>
            <Button type="button" variant="outline" onClick={() => void toggleGate("auto_approve_gate2")}>
              Gate 2 (post-call): {company.auto_approve_gate2 ? "auto" : "human"}
            </Button>
          </div>
        </section>
      ) : null}

      <div className="grid gap-8 lg:grid-cols-2">
        <section className="rounded-lg border border-border bg-white/70 p-5">
          <h2 className="mb-3 text-lg font-semibold">New hiring brief</h2>
          <form className="space-y-3" onSubmit={onCreateRole}>
            <Input name="title" label="Role title" required />
            <Input name="department" label="Department" />
            <Input name="location" label="Location" />
            <Input name="employment_type" label="Employment type" placeholder="full_time" />
            <label className="block text-sm">
              <span className="mb-1 block font-medium">Brief</span>
              <textarea
                name="brief_text"
                required
                minLength={10}
                rows={5}
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none ring-ring focus:ring-2"
                placeholder="Stated requirements go here. Put internal prefs in hidden filters."
              />
            </label>
            <label className="block text-sm">
              <span className="mb-1 block font-medium">Stated filters (JSON array)</span>
              <textarea
                name="stated_filters"
                rows={3}
                className="w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-xs outline-none ring-ring focus:ring-2"
                defaultValue='[{"field":"years_experience","operator":"gte","value":5}]'
              />
            </label>
            <label className="block text-sm">
              <span className="mb-1 block font-medium">Hidden filters (JSON array, internal only)</span>
              <textarea
                name="hidden_filters"
                rows={3}
                className="w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-xs outline-none ring-ring focus:ring-2"
                defaultValue='[{"field":"commute_miles","operator":"lte","value":25,"description":"INTERNAL_ONLY"}]'
              />
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" name="extract_filters" />
              Auto-extract filters from brief when lists empty
            </label>
            {error ? <p className="text-sm text-destructive">{error}</p> : null}
            <Button type="submit" disabled={pending}>
              {pending ? "Saving…" : "Create role"}
            </Button>
          </form>
        </section>

        <section className="rounded-lg border border-border bg-white/70 p-5">
          <h2 className="mb-3 text-lg font-semibold">Roles</h2>
          <ul className="mb-4 max-h-48 space-y-2 overflow-auto">
            {roles.map((role) => (
              <li key={role.id}>
                <button
                  type="button"
                  className={`w-full rounded-md border px-3 py-2 text-left text-sm ${
                    selected?.id === role.id ? "border-primary bg-accent" : "border-border"
                  }`}
                  onClick={() => {
                    setSelected(role);
                    setJd(role.jd);
                  }}
                >
                  <span className="font-medium">{role.title}</span>
                  <span className="ml-2 text-muted-foreground">{role.status}</span>
                  <span className="mt-1 block text-xs text-muted-foreground">
                    stated {role.stated_filters.length} · hidden {role.hidden_filters.length}
                  </span>
                </button>
              </li>
            ))}
            {!roles.length ? <li className="text-sm text-muted-foreground">No roles yet.</li> : null}
          </ul>

          {selected ? (
            <div className="space-y-3">
              <div className="rounded-md border border-dashed border-border p-3 text-sm">
                <p className="font-medium">Hidden filters (never published)</p>
                <pre className="mt-2 overflow-auto font-mono text-xs">
                  {JSON.stringify(selected.hidden_filters, null, 2)}
                </pre>
              </div>
              <Button type="button" onClick={() => void onGenerateJd()} disabled={pending}>
                Generate structured JD
              </Button>
              {jd ? (
                <div className="rounded-md border border-border bg-background p-3">
                  <p className="mb-2 font-medium">JD preview (structured JSON)</p>
                  <pre className="max-h-80 overflow-auto font-mono text-xs">
                    {JSON.stringify(jd, null, 2)}
                  </pre>
                </div>
              ) : null}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">Select a role to generate a JD.</p>
          )}
        </section>
      </div>

      <p className="mt-10 text-xs text-muted-foreground">
        <Link href="/">HireFlow</Link> · Milestone 1 intake
      </p>
    </main>
  );
}

function Input({
  name,
  label,
  required,
  placeholder,
}: {
  name: string;
  label: string;
  required?: boolean;
  placeholder?: string;
}) {
  return (
    <label className="block text-sm">
      <span className="mb-1 block font-medium">{label}</span>
      <input
        name={name}
        required={required}
        placeholder={placeholder}
        className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm outline-none ring-ring focus:ring-2"
      />
    </label>
  );
}

function parsePredicates(raw: string): RulePredicate[] {
  const trimmed = raw.trim();
  if (!trimmed) return [];
  const parsed = JSON.parse(trimmed) as RulePredicate[];
  if (!Array.isArray(parsed)) throw new Error("Filters must be a JSON array");
  return parsed;
}
