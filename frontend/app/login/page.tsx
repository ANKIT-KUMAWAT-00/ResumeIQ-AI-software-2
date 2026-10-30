"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Mail, Lock, User, Phone, ShieldCheck, Orbit, KeyRound } from "lucide-react";
import { api } from "@/lib/api";

type AuthMode = "login-password" | "login-otp" | "register" | "forgot-password";

export default function LoginPage() {
  const [mode, setMode] = useState<AuthMode>("login-password");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [devCode, setDevCode] = useState("");
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const router = useRouter();

  async function handleRegister(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const res = await api<any>("/auth/register", {
        method: "POST",
        body: JSON.stringify({
          full_name: fullName,
          email,
          phone: phone || null,
          password,
        }),
      });
      if (res.verification?.development_code) {
        setDevCode(res.verification.development_code);
      }
      setMessage("Account created successfully! Please verify your email.");
      setSent(true);
    } catch (err: any) {
      setError(err instanceof Error ? err.message : "Registration failed.");
    } finally {
      setBusy(false);
    }
  }

  async function handleLoginPassword(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      router.push("/workspace");
    } catch (err: any) {
      setError(err instanceof Error ? err.message : "Invalid email or password.");
    } finally {
      setBusy(false);
    }
  }

  async function handleRequestOtp() {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const r = await api<{ development_code?: string }>("/auth/request-otp", {
        method: "POST",
        body: JSON.stringify({ email }),
      });
      setSent(true);
      if (r.development_code) {
        setDevCode(r.development_code);
      }
    } catch (err: any) {
      setError(err instanceof Error ? err.message : "Could not send code.");
    } finally {
      setBusy(false);
    }
  }

  async function handleVerifyOtp() {
    setBusy(true);
    setError("");
    try {
      await api("/auth/verify-otp", {
        method: "POST",
        body: JSON.stringify({ email, code }),
      });
      router.push("/workspace");
    } catch (err: any) {
      setError(err instanceof Error ? err.message : "Could not sign in with this code.");
    } finally {
      setBusy(false);
    }
  }

  async function handleVerifyEmail() {
    setBusy(true);
    setError("");
    try {
      await api("/auth/verify-email", {
        method: "POST",
        body: JSON.stringify({ email, code }),
      });
      setMessage("Email verified successfully! You can now proceed to your workspace.");
      setTimeout(() => router.push("/workspace"), 1000);
    } catch (err: any) {
      setError(err instanceof Error ? err.message : "Verification failed.");
    } finally {
      setBusy(false);
    }
  }

  async function handleForgotPassword() {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const r = await api<any>("/auth/forgot-password", {
        method: "POST",
        body: JSON.stringify({ email }),
      });
      setSent(true);
      if (r.development_code) {
        setDevCode(r.development_code);
      }
      setMessage("Password reset code sent.");
    } catch (err: any) {
      setError(err instanceof Error ? err.message : "Could not send reset code.");
    } finally {
      setBusy(false);
    }
  }

  async function handleResetPassword() {
    setBusy(true);
    setError("");
    try {
      await api("/auth/reset-password", {
        method: "POST",
        body: JSON.stringify({ email, code, new_password: newPassword }),
      });
      setMessage("Password reset successful! Please log in with your new password.");
      setMode("login-password");
      setSent(false);
      setCode("");
    } catch (err: any) {
      setError(err instanceof Error ? err.message : "Password reset failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="relative min-h-[85vh] overflow-hidden px-5 py-12 md:py-16">
      <div className="absolute left-1/2 top-12 -z-10 h-72 w-72 -translate-x-1/2 rounded-full bg-violet-600/15 blur-[100px]" />
      <div className="glass mx-auto max-w-md rounded-3xl p-7 sm:p-9">
        <Link
          href="/"
          className="inline-flex items-center gap-2 text-sm text-slate-400 hover:text-white"
        >
          <ArrowLeft size={15} /> Back to home
        </Link>

        <div className="mt-6 flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-violet-400 to-cyan-300 text-slate-950">
          <Orbit size={24} />
        </div>

        <h1 className="mt-5 text-2xl font-semibold">
          {mode === "register"
            ? "Create an Account"
            : mode === "forgot-password"
            ? "Reset Password"
            : "Welcome to ResumeIQ AI"}
        </h1>
        <p className="mt-1 text-sm leading-6 text-slate-400">
          {mode === "register"
            ? "Set up your credentials for resume intelligence."
            : mode === "forgot-password"
            ? "Enter your email to receive a password recovery code."
            : "Sign in to access your resumes and templates."}
        </p>

        {/* Auth Mode Tabs */}
        {mode !== "forgot-password" && (
          <div className="mt-6 flex rounded-xl border border-white/10 bg-white/[.02] p-1">
            <button
              onClick={() => {
                setMode("login-password");
                setError("");
                setSent(false);
              }}
              className={`flex-1 rounded-lg py-2 text-xs font-medium transition ${
                mode === "login-password"
                  ? "bg-violet-400/20 text-violet-200"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              Password
            </button>
            <button
              onClick={() => {
                setMode("login-otp");
                setError("");
                setSent(false);
              }}
              className={`flex-1 rounded-lg py-2 text-xs font-medium transition ${
                mode === "login-otp"
                  ? "bg-violet-400/20 text-violet-200"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              Email OTP
            </button>
            <button
              onClick={() => {
                setMode("register");
                setError("");
                setSent(false);
              }}
              className={`flex-1 rounded-lg py-2 text-xs font-medium transition ${
                mode === "register"
                  ? "bg-violet-400/20 text-violet-200"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              Register
            </button>
          </div>
        )}

        {/* 1. Register Form */}
        {mode === "register" && !sent && (
          <form onSubmit={handleRegister} className="mt-6 space-y-4">
            <div>
              <label className="block text-xs text-slate-300">Full Name</label>
              <div className="relative mt-1">
                <User size={16} className="absolute left-3 top-3 text-slate-500" />
                <input
                  className="field pl-9"
                  type="text"
                  required
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="Ankit Kumawat"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs text-slate-300">Email Address</label>
              <div className="relative mt-1">
                <Mail size={16} className="absolute left-3 top-3 text-slate-500" />
                <input
                  className="field pl-9"
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs text-slate-300">Phone (Optional)</label>
              <div className="relative mt-1">
                <Phone size={16} className="absolute left-3 top-3 text-slate-500" />
                <input
                  className="field pl-9"
                  type="tel"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  placeholder="+91-9999999999"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs text-slate-300">Password (min 8 characters)</label>
              <div className="relative mt-1">
                <Lock size={16} className="absolute left-3 top-3 text-slate-500" />
                <input
                  className="field pl-9"
                  type="password"
                  required
                  minLength={8}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                />
              </div>
            </div>

            <button type="submit" className="button-primary mt-2 w-full" disabled={busy}>
              {busy ? "Creating account…" : "Register & Start"}
            </button>
          </form>
        )}

        {/* Register Verification Step */}
        {mode === "register" && sent && (
          <div className="mt-6 space-y-4">
            <p className="text-xs text-slate-300">
              Enter the 6-digit verification code sent to <b>{email}</b>.
            </p>
            <input
              className="field tracking-[.4em]"
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
              inputMode="numeric"
              placeholder="000000"
            />
            {devCode && (
              <div className="rounded-xl border border-amber-300/20 bg-amber-300/[.06] p-3 text-xs text-amber-100">
                Development-only simulated OTP: <b className="tracking-widest">{devCode}</b>
              </div>
            )}
            <button
              onClick={handleVerifyEmail}
              disabled={busy || code.length !== 6}
              className="button-primary w-full"
            >
              {busy ? "Verifying…" : "Verify Email & Enter Workspace"}
            </button>
          </div>
        )}

        {/* 2. Login with Password */}
        {mode === "login-password" && (
          <form onSubmit={handleLoginPassword} className="mt-6 space-y-4">
            <div>
              <label className="block text-xs text-slate-300">Email Address</label>
              <div className="relative mt-1">
                <Mail size={16} className="absolute left-3 top-3 text-slate-500" />
                <input
                  className="field pl-9"
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                />
              </div>
            </div>

            <div>
              <div className="flex items-center justify-between">
                <label className="block text-xs text-slate-300">Password</label>
                <button
                  type="button"
                  onClick={() => {
                    setMode("forgot-password");
                    setError("");
                    setSent(false);
                  }}
                  className="text-xs text-violet-300 hover:underline"
                >
                  Forgot password?
                </button>
              </div>
              <div className="relative mt-1">
                <Lock size={16} className="absolute left-3 top-3 text-slate-500" />
                <input
                  className="field pl-9"
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                />
              </div>
            </div>

            <button type="submit" className="button-primary mt-2 w-full" disabled={busy}>
              {busy ? "Signing in…" : "Sign In with Password"}
            </button>
          </form>
        )}

        {/* 3. Login with OTP */}
        {mode === "login-otp" && (
          <div className="mt-6 space-y-4">
            {!sent ? (
              <>
                <label className="block text-xs text-slate-300">Email Address</label>
                <div className="relative">
                  <Mail size={16} className="absolute left-3 top-3 text-slate-500" />
                  <input
                    className="field pl-9"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="you@example.com"
                  />
                </div>
                <button
                  onClick={handleRequestOtp}
                  disabled={busy || !email.includes("@")}
                  className="button-primary w-full"
                >
                  {busy ? "Sending…" : "Send One-Time Code"}
                </button>
              </>
            ) : (
              <>
                <label className="block text-xs text-slate-300">6-Digit One-Time Code</label>
                <input
                  className="field tracking-[.4em]"
                  value={code}
                  onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                  inputMode="numeric"
                  placeholder="000000"
                />
                {devCode && (
                  <div className="rounded-xl border border-amber-300/20 bg-amber-300/[.06] p-3 text-xs text-amber-100">
                    Development-only simulated OTP: <b className="tracking-widest">{devCode}</b>
                  </div>
                )}
                <button
                  onClick={handleVerifyOtp}
                  disabled={busy || code.length !== 6}
                  className="button-primary w-full"
                >
                  {busy ? "Verifying…" : "Verify & Sign In"}
                </button>
                <button
                  onClick={() => {
                    setSent(false);
                    setCode("");
                  }}
                  className="w-full text-center text-xs text-slate-400 hover:text-white"
                >
                  Use a different email
                </button>
              </>
            )}
          </div>
        )}

        {/* 4. Forgot / Reset Password */}
        {mode === "forgot-password" && (
          <div className="mt-6 space-y-4">
            {!sent ? (
              <>
                <label className="block text-xs text-slate-300">Account Email Address</label>
                <div className="relative">
                  <Mail size={16} className="absolute left-3 top-3 text-slate-500" />
                  <input
                    className="field pl-9"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="you@example.com"
                  />
                </div>
                <button
                  onClick={handleForgotPassword}
                  disabled={busy || !email.includes("@")}
                  className="button-primary w-full"
                >
                  {busy ? "Sending…" : "Send Recovery Code"}
                </button>
                <button
                  onClick={() => setMode("login-password")}
                  className="w-full text-center text-xs text-slate-400 hover:text-white"
                >
                  Return to sign in
                </button>
              </>
            ) : (
              <>
                <label className="block text-xs text-slate-300">6-Digit Reset Code</label>
                <input
                  className="field tracking-[.4em]"
                  value={code}
                  onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                  inputMode="numeric"
                  placeholder="000000"
                />
                {devCode && (
                  <div className="rounded-xl border border-amber-300/20 bg-amber-300/[.06] p-3 text-xs text-amber-100">
                    Development-only simulated code: <b className="tracking-widest">{devCode}</b>
                  </div>
                )}
                <label className="block text-xs text-slate-300 mt-3">New Password (min 8 chars)</label>
                <div className="relative">
                  <KeyRound size={16} className="absolute left-3 top-3 text-slate-500" />
                  <input
                    className="field pl-9"
                    type="password"
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    placeholder="••••••••"
                  />
                </div>
                <button
                  onClick={handleResetPassword}
                  disabled={busy || code.length !== 6 || newPassword.length < 8}
                  className="button-primary w-full mt-2"
                >
                  {busy ? "Resetting…" : "Reset Password & Login"}
                </button>
              </>
            )}
          </div>
        )}

        {message && (
          <p className="mt-4 rounded-xl border border-cyan-300/20 bg-cyan-400/10 p-3 text-xs text-cyan-200">
            {message}
          </p>
        )}

        {error && (
          <p role="alert" className="mt-4 rounded-xl border border-red-300/20 bg-red-400/10 p-3 text-xs text-red-200">
            {error}
          </p>
        )}

        <p className="mt-7 flex gap-2 text-xs leading-5 text-slate-500">
          <ShieldCheck size={15} className="mt-0.5 shrink-0" />
          By continuing, you agree to our{" "}
          <Link href="/terms" className="text-violet-200 underline">
            Terms
          </Link>{" "}
          and{" "}
          <Link href="/privacy" className="text-violet-200 underline">
            Privacy Policy
          </Link>
          .
        </p>
      </div>
    </main>
  );
}
