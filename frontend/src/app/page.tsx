"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

import { Button } from "@/components/ui/button";
import { login, register } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function HomePage() {
  const { token, setToken } = useAuth();
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "register">("register");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setPending(true);
    const fd = new FormData(e.currentTarget);
    try {
      if (mode === "register") {
        const res = await register({
          company_name: String(fd.get("company_name") || ""),
          company_slug: String(fd.get("company_slug") || ""),
          full_name: String(fd.get("full_name") || ""),
          email: String(fd.get("email") || ""),
          password: String(fd.get("password") || ""),
        });
        setToken(res.access_token);
      } else {
        const res = await login({
          email: String(fd.get("email") || ""),
          password: String(fd.get("password") || ""),
        });
        setToken(res.access_token);
      }
      router.push("/console");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setPending(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-5xl flex-col justify-center gap-12 px-6 py-16 lg:flex-row lg:items-center">
      <section className="flex-1">
        <p className="mb-3 text-sm font-medium uppercase tracking-[0.2em] text-primary">HireFlow</p>
        <h1 className="text-4xl font-semibold tracking-tight text-foreground sm:text-5xl">
          Brief in. Signed offer out.
        </h1>
        <p className="mt-4 max-w-xl text-lg text-muted-foreground">
          Milestone 1: company auth, hiring-brief intake with stated vs hidden filters, and
          structured JD generation — hidden rules never leak into the external JD.
        </p>
        {token ? (
          <div className="mt-8">
            <Button type="button" onClick={() => router.push("/console")}>
              Open console
            </Button>
          </div>
        ) : null}
      </section>

      <section className="w-full max-w-md rounded-lg border border-border bg-white/80 p-6 shadow-sm backdrop-blur">
        <div className="mb-4 flex gap-2">
          <Button
            type="button"
            variant={mode === "register" ? "default" : "outline"}
            onClick={() => setMode("register")}
          >
            Register
          </Button>
          <Button
            type="button"
            variant={mode === "login" ? "default" : "outline"}
            onClick={() => setMode("login")}
          >
            Login
          </Button>
        </div>
        <form className="space-y-3" onSubmit={onSubmit}>
          {mode === "register" ? (
            <>
              <Field name="company_name" label="Company name" required />
              <Field name="company_slug" label="Company slug" placeholder="acme-corp" required />
              <Field name="full_name" label="Your name" required />
            </>
          ) : null}
          <Field name="email" label="Email" type="email" required />
          <Field name="password" label="Password" type="password" required />
          {error ? <p className="text-sm text-destructive">{error}</p> : null}
          <Button type="submit" disabled={pending} className="w-full">
            {pending ? "Working…" : mode === "register" ? "Create workspace" : "Sign in"}
          </Button>
        </form>
        <p className="mt-4 text-xs text-muted-foreground">
          Already in? <Link href="/console">Go to console</Link>
        </p>
      </section>
    </main>
  );
}

function Field({
  name,
  label,
  type = "text",
  placeholder,
  required,
}: {
  name: string;
  label: string;
  type?: string;
  placeholder?: string;
  required?: boolean;
}) {
  return (
    <label className="block text-sm">
      <span className="mb-1 block font-medium text-foreground">{label}</span>
      <input
        name={name}
        type={type}
        placeholder={placeholder}
        required={required}
        className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm outline-none ring-ring focus:ring-2"
      />
    </label>
  );
}
