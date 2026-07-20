"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useState, Suspense } from "react";
import { Eye, EyeOff, ConciergeBell, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";

const REASON_MESSAGES: Record<string, string> = {
  expired: "Your session has expired. Please sign in again.",
};

/** Distinguishes *why* login failed rather than always showing one
 * generic message — a wrong password, a rate limit, and "our own server
 * couldn't be reached" are different problems with different next steps
 * for the person looking at this screen. */
function errorMessageForResponse(status: number, code: string | undefined, message: string | undefined): string {
  if (status === 401 || status === 422) return "Incorrect email or password.";
  if (status === 429) return "Too many sign-in attempts. Please wait a moment and try again.";
  if (code === "UPSTREAM_UNREACHABLE" || status === 502 || status === 503) {
    return "Our server is temporarily unavailable. Please try again shortly.";
  }
  if (status >= 500) return "Something went wrong on our end. Please try again in a moment.";
  return message ?? "Something went wrong. Please try again.";
}

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const reason = searchParams.get("reason");

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [rememberSession, setRememberSession] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);

    let response: Response;
    try {
      response = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password, remember_session: rememberSession }),
      });
    } catch {
      setSubmitting(false);
      setError("Unable to reach the server. Check your connection and try again.");
      return;
    }

    const payload = await response.json().catch(() => null);
    setSubmitting(false);

    if (!response.ok || !payload?.success) {
      setError(errorMessageForResponse(response.status, payload?.error?.code, payload?.error?.message));
      return;
    }
    router.push("/");
    router.refresh();
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-sand/30 px-4 py-10">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-sm space-y-5 rounded-xl border border-sand bg-white p-8 shadow-lg"
      >
        <div className="flex flex-col items-center text-center">
          <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-primary text-ivory">
            <ConciergeBell size={22} aria-hidden="true" />
          </div>
          <h1 className="text-lg font-semibold text-charcoal">RKPR Resort</h1>
          <p className="text-sm text-charcoal/50">Staff operations dashboard</p>
        </div>

        {reason && REASON_MESSAGES[reason] && (
          <p role="status" className="rounded-md bg-accent/10 px-3 py-2 text-xs text-accent">
            {REASON_MESSAGES[reason]}
          </p>
        )}

        <div>
          <Label htmlFor="email">Email</Label>
          <Input
            id="email"
            type="email"
            autoComplete="username"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>

        <div>
          <Label htmlFor="password">Password</Label>
          <div className="relative">
            <Input
              id="password"
              type={showPassword ? "text" : "password"}
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="pr-10"
            />
            <button
              type="button"
              onClick={() => setShowPassword((v) => !v)}
              aria-label={showPassword ? "Hide password" : "Show password"}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-charcoal/40 hover:text-charcoal"
            >
              {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>
          </div>
        </div>

        <div className="flex items-center justify-between text-sm">
          <label className="flex items-center gap-2 text-charcoal/70">
            <input
              type="checkbox"
              checked={rememberSession}
              onChange={(e) => setRememberSession(e.target.checked)}
              className="rounded border-sand text-primary focus:ring-accent"
            />
            Remember this session
          </label>
        </div>

        {error && (
          <p role="alert" className="text-sm text-red-600">
            {error}
          </p>
        )}

        <Button type="submit" loading={submitting} className="w-full">
          {submitting ? "Signing in…" : "Sign in"}
        </Button>
      </form>
    </main>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<Loader2 className="mx-auto mt-24 animate-spin text-charcoal/30" />}>
      <LoginForm />
    </Suspense>
  );
}
