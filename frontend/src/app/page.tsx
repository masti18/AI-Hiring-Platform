import { Button } from "@/components/ui/button";

const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export default function HomePage() {
  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col justify-center px-6 py-16">
      <p className="mb-3 text-sm font-medium uppercase tracking-[0.2em] text-primary">HireFlow</p>
      <h1 className="text-4xl font-semibold tracking-tight text-foreground sm:text-5xl">
        Brief in. Signed offer out.
      </h1>
      <p className="mt-4 max-w-xl text-lg text-muted-foreground">
        Autonomous AI hiring pipeline with config-driven review gates, structured hidden rules, and
        a full audit trail — from sourcing through voice screen to offer.
      </p>
      <div className="mt-8 flex flex-wrap gap-3">
        <Button type="button">Open console</Button>
        <Button type="button" variant="outline">
          API: {apiBase}
        </Button>
      </div>
      <p className="mt-10 font-mono text-xs text-muted-foreground">
        Skeleton ready · Milestone 0 · Next.js 14 + FastAPI + LangGraph
      </p>
    </main>
  );
}
