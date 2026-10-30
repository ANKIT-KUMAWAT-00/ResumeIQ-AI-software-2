"use client";

import { useEffect, useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { api, packages } from "@/lib/api";
import {
  ArrowRight,
  UploadCloud,
  FileText,
  ShieldCheck,
  RefreshCw,
  Download,
  CheckCircle2,
  AlertCircle,
  LoaderCircle,
  LogIn,
  Settings2,
  Sparkles,
  HelpCircle,
  Check,
  Award,
  Sliders,
  FileCode,
  ChevronRight,
} from "lucide-react";

type User = {
  id: number;
  email: string;
  role: string;
  full_name?: string;
  phone?: string;
  email_verified?: boolean;
};

type TemplateSection = {
  id: string;
  heading: string;
  required: boolean;
  order: number;
};

type TemplateItem = {
  template_id: string;
  template_name?: string;
  display_name: string;
  description: string;
  layout?: string;
  page_size?: string;
  is_confirmed?: boolean;
  template_type?: string;
  sections?: TemplateSection[];
  spec?: any;
};

type AdaptiveQuestion = {
  field_path: string;
  question: string;
  input_type?: string;
  required: boolean;
  help_text?: string | null;
  section_id?: string | null;
  current_value?: any;
};

type MissingInfoReport = {
  resume_id: number;
  template_id: string;
  is_complete: boolean;
  missing_required_count: number;
  missing_optional_count: number;
  questions: AdaptiveQuestion[];
};

type ValidationCheck = {
  name: string;
  passed: boolean;
  message: string;
  severity: "info" | "warning" | "error";
};

type DocumentQualityReport = {
  is_valid: boolean;
  quality_score: number;
  passed_checks: number;
  total_checks: number;
  checks: ValidationCheck[];
  summary: string;
};

type Resume = {
  id: number;
  filename: string;
  status: string;
  collection_status?: string;
  generation_status?: string;
  target_role: string;
  template_id: string;
  created_at: string;
  validation_report?: DocumentQualityReport;
};

declare global {
  interface Window {
    Razorpay?: new (options: any) => { open: () => void };
  }
}

export default function Workspace() {
  return (
    <Suspense
      fallback={
        <main className="mx-auto max-w-7xl px-5 py-16 text-slate-400">
          Loading workspace…
        </main>
      }
    >
      <WorkspaceContent />
    </Suspense>
  );
}

function WorkspaceContent() {
  const isDev = process.env.NEXT_PUBLIC_APP_ENV === "development";

  const params = useSearchParams();
  const initialTemplate = params.get("template") || "lpu-standard";

  const [user, setUser] = useState<User | null>(null);
  const [authChecked, setAuthChecked] = useState(false);
  const [catalog, setCatalog] = useState<any[]>(packages);
  const [templates, setTemplates] = useState<TemplateItem[]>([]);
  const [orders, setOrders] = useState<any[]>([]);
  const [resumes, setResumes] = useState<Resume[]>([]);
  const [selectedPackage, setSelectedPackage] = useState(
    params.get("package") || "resume-template",
  );

  // Template selection & inspection state
  const [templateId, setTemplateId] = useState(initialTemplate);
  const [selectedTemplateSpec, setSelectedTemplateSpec] = useState<any | null>(null);
  const [uploadingTemplate, setUploadingTemplate] = useState(false);
  const [templateFile, setTemplateFile] = useState<File | null>(null);

  // Resume configuration state
  const [role, setRole] = useState("sde-general");
  const [bodySize, setBodySize] = useState(8.5);
  const [marginIn, setMarginIn] = useState(
    initialTemplate === "lpu-standard" || initialTemplate === "modern-one-page"
      ? 0.38
      : 0.55,
  );
  const [fontFamily, setFontFamily] = useState("Arial");
  const [file, setFile] = useState<File | null>(null);

  // Active resume & Q&A state
  const [activeResume, setActiveResume] = useState<any>(null);
  const [missingInfo, setMissingInfo] = useState<MissingInfoReport | null>(null);
  const [userAnswers, setUserAnswers] = useState<Record<string, string>>({});
  const [answeringBusy, setAnsweringBusy] = useState(false);
  const [enhancingBusy, setEnhancingBusy] = useState(false);
  const [generatingBusy, setGeneratingBusy] = useState(false);

  // Feedback & controls
  const [revisionNotes, setRevisionNotes] = useState("");
  const [testimonialName, setTestimonialName] = useState("");
  const [testimonialText, setTestimonialText] = useState("");
  const [testimonialConsent, setTestimonialConsent] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function refresh() {
    try {
      const me = await api<User>("/auth/me");
      setUser(me);

      const [ts, rs, os] = await Promise.all([
        api<TemplateItem[]>("/templates"),
        api<Resume[]>("/resumes"),
        api<any[]>("/orders/me"),
      ]);

      setTemplates(ts);
      setResumes(rs);
      setOrders(os);

      // Refresh spec for current templateId
      const cur = ts.find((t) => t.template_id === templateId);
      if (cur) {
        try {
          const spec = await api<any>(`/templates/${cur.template_id}/specification`);
          setSelectedTemplateSpec(spec);
        } catch {
          // Fallback to cur
          setSelectedTemplateSpec(cur.spec || null);
        }
      }
    } catch {
      setUser(null);
    } finally {
      setAuthChecked(true);
    }
  }

  useEffect(() => {
    refresh();

    api<any[]>("/packages")
      .then(setCatalog)
      .catch(() => {});

    const script = document.createElement("script");
    script.src = "https://checkout.razorpay.com/v1/checkout.js";
    script.async = true;
    document.body.appendChild(script);

    return () => {
      script.remove();
    };
  }, []);

  // Update selected template spec when templateId changes
  async function handleSelectTemplate(id: string) {
    setTemplateId(id);
    if (id === "lpu-standard" || id === "modern-one-page") {
      setMarginIn(0.38);
      setBodySize(8.5);
    } else if (id === "ats-clean") {
      setMarginIn(0.55);
      setBodySize(9.5);
    }

    try {
      const spec = await api<any>(`/templates/${id}/specification`);
      setSelectedTemplateSpec(spec);
    } catch {
      const found = templates.find((t) => t.template_id === id);
      setSelectedTemplateSpec(found?.spec || null);
    }
  }

  // Upload custom template
  async function handleUploadTemplate() {
    if (!templateFile) return;
    setError("");
    setMessage("");
    setUploadingTemplate(true);

    try {
      const form = new FormData();
      form.append("file", templateFile);
      const res = await api<any>("/templates/upload", {
        method: "POST",
        body: form,
      });

      setMessage(`Template "${res.template_name}" parsed. Confirm the specification to activate.`);
      setTemplateFile(null);
      await refresh();
      handleSelectTemplate(res.template_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to upload custom template.");
    } finally {
      setUploadingTemplate(false);
    }
  }

  // Confirm template specification
  async function handleConfirmTemplate(id: string) {
    setError("");
    setMessage("");
    try {
      await api(`/templates/${id}/confirm`, { method: "POST" });
      setMessage(`Template specification confirmed and activated.`);
      await refresh();
      handleSelectTemplate(id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to confirm template.");
    }
  }

  async function startCheckout() {
    setError("");
    setMessage("");

    if (!user) {
      window.location.href = "/login";
      return;
    }

    setBusy(true);

    try {
      const order = await api<any>("/payments/orders", {
        method: "POST",
        body: JSON.stringify({ package_id: selectedPackage }),
      });

      if (!window.Razorpay) {
        throw new Error("Razorpay checkout did not load. Check your network and retry.");
      }

      const checkout = new window.Razorpay({
        key: order.key_id,
        amount: order.amount,
        currency: order.currency,
        name: "ResumeIQ AI",
        description: order.package.name,
        order_id: order.razorpay_order_id,
        prefill: { email: user.email },
        theme: { color: "#9b8cff" },
        handler: async (resp: any) => {
          try {
            const verified = await api<any>("/payments/verify", {
              method: "POST",
              body: JSON.stringify({
                internal_order_id: order.internal_order_id,
                razorpay_order_id: resp.razorpay_order_id,
                razorpay_payment_id: resp.razorpay_payment_id,
                razorpay_signature: resp.razorpay_signature,
              }),
            });

            setOrders((o) => [
              {
                id: order.internal_order_id,
                package_id: selectedPackage,
                status: verified.status,
              },
              ...o,
            ]);

            setMessage(
              verified.status === "paid"
                ? "Payment signature verified. You can now upload your resume."
                : "Payment is awaiting provider confirmation. Refresh in a moment.",
            );
          } catch (e) {
            setError(e instanceof Error ? e.message : "Payment verification failed.");
          }
        },
        modal: {
          ondismiss: () =>
            setMessage("Checkout closed. No payment is assumed successful unless verified by the server."),
        },
      });

      checkout.open();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not start checkout.");
    } finally {
      setBusy(false);
    }
  }

  async function upload() {
    setError("");
    setMessage("");

    if (!file) {
      setError("Choose a PDF or DOCX file first.");
      return;
    }

    const paid = orders.find((o) => o.status === "paid");
    if (!paid && !isDev) {
      setError("Complete and verify a package payment before uploading.");
      return;
    }

    setBusy(true);

    try {
      const form = new FormData();
      form.append("file", file);
      if (paid) {
        form.append("order_id", String(paid.id));
      }
      form.append("target_role", role);
      form.append("template_id", templateId);
      form.append(
        "template_overrides",
        JSON.stringify({
          fonts: {
            family: fontFamily,
            body_pt: bodySize,
          },
          margins: {
            top_in: marginIn,
            bottom_in: marginIn,
            left_in: marginIn,
            right_in: marginIn,
          },
        }),
      );

      const result = await api<any>("/resumes", {
        method: "POST",
        body: form,
      });

      setMessage(`Resume #${result.id} accepted. Status: ${result.status}.`);
      setFile(null);
      await refresh();
      await openResume(result.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed.");
    } finally {
      setBusy(false);
    }
  }

  async function openResume(id: number) {
    setError("");
    try {
      const r = await api<any>(`/resumes/${id}`);
      setActiveResume(r);
      // Fetch missing questions
      try {
        const report = await api<MissingInfoReport>(`/resumes/${id}/missing-information`);
        setMissingInfo(report);
      } catch {
        setMissingInfo(null);
      }
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load resume.");
    }
  }

  async function submitAnswers() {
    if (!activeResume) return;
    setAnsweringBusy(true);
    setError("");
    setMessage("");

    try {
      const res = await api<any>(`/resumes/${activeResume.id}/answers`, {
        method: "POST",
        body: JSON.stringify({
          answers: userAnswers,
          confirm: true,
        }),
      });

      setMessage("Answers applied! Canonical resume updated.");
      setMissingInfo(res.missing_information);
      // Reload active resume
      await openResume(activeResume.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to apply answers.");
    } finally {
      setAnsweringBusy(false);
    }
  }

  async function enhanceContent() {
    if (!activeResume) return;
    setEnhancingBusy(true);
    setError("");
    setMessage("");

    try {
      await api<any>(`/resumes/${activeResume.id}/enhance`, {
        method: "POST",
      });
      setMessage("Resume content enhanced via Gemini! Action verbs and clarity strengthened.");
      await openResume(activeResume.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Content enhancement failed.");
    } finally {
      setEnhancingBusy(false);
    }
  }

  async function generateDocuments() {
    if (!activeResume) return;
    setGeneratingBusy(true);
    setError("");
    setMessage("");

    try {
      const res = await api<any>(`/resumes/${activeResume.id}/generate`, {
        method: "POST",
      });
      setMessage(`Documents generated! Quality Score: ${res.quality_score}/100.`);
      await openResume(activeResume.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Generation failed.");
    } finally {
      setGeneratingBusy(false);
    }
  }

  async function retry(id: number) {
    try {
      await api(`/resumes/${id}/retry`, { method: "POST" });
      setMessage("Retry submitted.");
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Retry failed.");
    }
  }

  async function requestRevision(id: number) {
    try {
      await api(`/resumes/${id}/revision`, {
        method: "POST",
        body: JSON.stringify({ notes: revisionNotes }),
      });
      setMessage("Revision request submitted for admin review.");
      setRevisionNotes("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not request revision.");
    }
  }

  async function submitTestimonial() {
    try {
      await api("/testimonials", {
        method: "POST",
        body: JSON.stringify({
          display_name: testimonialName,
          body: testimonialText,
          consent_public: testimonialConsent,
        }),
      });
      setMessage("Thank you. Your testimonial is awaiting admin approval.");
      setTestimonialText("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not submit testimonial.");
    }
  }

  async function logout() {
    await api("/auth/logout", { method: "POST" });
    setUser(null);
    window.location.href = "/";
  }

  const paidOrder = orders.find((o) => o.status === "paid");
  const currentTemplate = templates.find((t) => t.template_id === templateId);

  return (
    <main className="mx-auto min-h-[78vh] max-w-7xl px-5 py-10 md:px-8 md:py-14">
      {/* Header */}
      <div className="mb-10 flex flex-col justify-between gap-4 md:flex-row md:items-end">
        <div>
          <p className="section-kicker">Template-Aware Intelligence</p>
          <h1 className="mt-3 text-3xl font-semibold tracking-tight sm:text-4xl">
            ResumeIQ <span className="gradient-text">AI Workspace.</span>
          </h1>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-400">
            Select or upload your template, extract and normalize resume data, answer targeted questions, and generate high-fidelity DOCX &amp; PDF resumes.
          </p>
        </div>

        {user ? (
          <div className="flex flex-wrap items-center gap-3">
            {isDev && (
              <span className="rounded-full border border-amber-300/30 bg-amber-300/10 px-3 py-1 text-xs font-medium text-amber-200">
                Dev Environment
              </span>
            )}
            <div className="flex items-center gap-3 rounded-full border border-white/10 bg-white/[.03] px-4 py-2">
              <span className="h-2 w-2 rounded-full bg-cyan-300" />
              <span className="max-w-52 truncate text-sm font-medium">{user.email}</span>
              <button
                onClick={logout}
                className="text-xs text-slate-400 hover:text-white transition"
              >
                Sign out
              </button>
            </div>
          </div>
        ) : (
          <Link href="/login" className="button-primary self-start">
            <LogIn size={16} /> Sign in to continue
          </Link>
        )}
      </div>

      {!authChecked ? (
        <div className="glass rounded-2xl p-6 text-slate-400">Checking your session…</div>
      ) : !user ? (
        <div className="glass rounded-2xl p-8">
          <h2 className="text-xl font-semibold">Sign in to access your workspace</h2>
          <p className="mt-2 text-sm text-slate-400">
            Your resumes, extracted models, and generated documents are securely private to your account.
          </p>
          <Link href="/login" className="button-primary mt-5">
            Continue to sign in <ArrowRight size={16} />
          </Link>
        </div>
      ) : (
        <>
          {/* STEP 1: TEMPLATE INTELLIGENCE HUB */}
          <section className="glass rounded-2xl p-6 md:p-8 mb-8">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <p className="section-kicker">Stage 01 / Template Intelligence</p>
                <h2 className="mt-1 text-2xl font-semibold">Select or Upload Resume Template</h2>
                <p className="mt-1 text-xs text-slate-400">
                  ResumeIQ AI inspects the selected template structure and rules before processing your resume.
                </p>
              </div>
              <span className="pill self-start sm:self-auto flex items-center gap-1.5">
                <FileCode size={13} /> Strict Template-First
              </span>
            </div>

            {/* Template Selection Cards */}
            <div className="mt-6 grid gap-4 md:grid-cols-3">
              {templates.map((tpl) => {
                const isLpu = tpl.template_id === "lpu-standard";
                const isSelected = templateId === tpl.template_id;

                return (
                  <div
                    key={tpl.template_id}
                    onClick={() => handleSelectTemplate(tpl.template_id)}
                    className={`cursor-pointer rounded-2xl border p-5 transition relative flex flex-col justify-between ${
                      isSelected
                        ? "border-violet-300/60 bg-violet-400/[.09] shadow-lg shadow-violet-500/10"
                        : "border-white/10 bg-white/[.02] hover:bg-white/[.05]"
                    }`}
                  >
                    <div>
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-semibold text-base text-white">
                          {tpl.display_name || tpl.template_name || tpl.template_id}
                        </span>
                        {isLpu && (
                          <span className="rounded-full bg-cyan-400/20 text-cyan-200 border border-cyan-300/30 px-2 py-0.5 text-[10px] font-semibold">
                            Recommended
                          </span>
                        )}
                      </div>

                      <p className="mt-2 text-xs leading-5 text-slate-300">
                        {isLpu
                          ? "Official Lovely Professional University format. Single-column tabular layout, #2874B8 headers, right-aligned dates."
                          : tpl.description || "Clean structured resume layout."}
                      </p>

                      <div className="mt-4 flex flex-wrap gap-1.5">
                        <span className="rounded-md bg-white/[.05] px-2 py-0.5 text-[10px] text-slate-400">
                          {tpl.layout || "single-column"}
                        </span>
                        <span className="rounded-md bg-white/[.05] px-2 py-0.5 text-[10px] text-slate-400">
                          {tpl.sections?.length || 5} sections
                        </span>
                        {tpl.is_confirmed && (
                          <span className="rounded-md bg-emerald-400/15 text-emerald-300 px-2 py-0.5 text-[10px] font-medium flex items-center gap-1">
                            <Check size={10} /> Confirmed
                          </span>
                        )}
                      </div>
                    </div>

                    <div className="mt-5 pt-3 border-t border-white/5 flex items-center justify-between">
                      <span className="text-xs font-medium text-slate-400">
                        {isSelected ? "Active Template" : "Select Template"}
                      </span>
                      {isSelected ? (
                        <CheckCircle2 size={16} className="text-violet-300" />
                      ) : (
                        <ChevronRight size={16} className="text-slate-600" />
                      )}
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Custom Template Upload & Specification Inspector */}
            <div className="mt-6 grid gap-6 lg:grid-cols-[1fr_1.2fr]">
              {/* Custom Upload Dropzone */}
              <div className="rounded-xl border border-dashed border-violet-300/25 bg-violet-400/[.02] p-5">
                <div className="flex items-center gap-2 mb-3">
                  <UploadCloud size={18} className="text-violet-300" />
                  <h3 className="text-sm font-semibold text-white">Upload Custom Template (DOCX / PDF)</h3>
                </div>
                <p className="text-xs text-slate-400 leading-5">
                  Upload your university or corporate template. Our analyzer extracts styles, margins, section headings, and layout geometry automatically.
                </p>

                <label className="mt-4 flex min-h-24 cursor-pointer flex-col items-center justify-center rounded-xl border border-dashed border-white/15 bg-white/[.02] px-4 py-3 text-center transition hover:bg-white/[.05]">
                  <span className="text-xs font-medium text-slate-300">
                    {templateFile ? templateFile.name : "Select .docx or .pdf template file"}
                  </span>
                  <input
                    type="file"
                    accept=".docx,.pdf"
                    className="sr-only"
                    onChange={(e) => setTemplateFile(e.target.files?.[0] || null)}
                  />
                </label>

                <button
                  onClick={handleUploadTemplate}
                  disabled={uploadingTemplate || !templateFile}
                  className="button-secondary mt-3 w-full text-xs font-medium disabled:opacity-40"
                >
                  {uploadingTemplate ? (
                    <>
                      <LoaderCircle size={14} className="animate-spin" /> Analyzing Document Structure…
                    </>
                  ) : (
                    <>
                      <Sparkles size={14} className="text-violet-300" /> Parse &amp; Build Specification
                    </>
                  )}
                </button>
              </div>

              {/* Template Specification Inspector */}
              <div className="rounded-xl border border-white/10 bg-white/[.02] p-5">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Sliders size={16} className="text-cyan-300" />
                    <h3 className="text-sm font-semibold text-white">
                      Template Specification: <span className="text-cyan-200">{templateId}</span>
                    </h3>
                  </div>
                  {currentTemplate?.is_confirmed ? (
                    <span className="rounded-full bg-emerald-400/10 text-emerald-300 border border-emerald-400/20 px-2 py-0.5 text-[10px] font-semibold">
                      Confirmed
                    </span>
                  ) : (
                    <button
                      onClick={() => handleConfirmTemplate(templateId)}
                      className="rounded-full bg-violet-400/20 text-violet-200 border border-violet-400/30 px-2.5 py-0.5 text-[10px] font-semibold hover:bg-violet-400/30"
                    >
                      Confirm Specification
                    </button>
                  )}
                </div>

                {selectedTemplateSpec ? (
                  <div className="mt-4 space-y-3">
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px]">
                      <div className="rounded-lg bg-black/30 p-2 border border-white/5">
                        <span className="text-slate-500 block">Page Size</span>
                        <span className="text-slate-200 font-medium">{selectedTemplateSpec.page_size || "LETTER"}</span>
                      </div>
                      <div className="rounded-lg bg-black/30 p-2 border border-white/5">
                        <span className="text-slate-500 block">Margins</span>
                        <span className="text-slate-200 font-medium">
                          {selectedTemplateSpec.margins?.top_in || 0.38}&quot;
                        </span>
                      </div>
                      <div className="rounded-lg bg-black/30 p-2 border border-white/5">
                        <span className="text-slate-500 block">Font Family</span>
                        <span className="text-slate-200 font-medium">
                          {selectedTemplateSpec.fonts?.family || "Arial"}
                        </span>
                      </div>
                      <div className="rounded-lg bg-black/30 p-2 border border-white/5">
                        <span className="text-slate-500 block">Body Size</span>
                        <span className="text-slate-200 font-medium">
                          {selectedTemplateSpec.fonts?.body_pt || 8.5} pt
                        </span>
                      </div>
                    </div>

                    <div>
                      <p className="text-[11px] font-medium text-slate-400 mb-2">Detected Sections &amp; Rules:</p>
                      <div className="max-h-32 overflow-y-auto space-y-1 pr-1 text-xs">
                        {selectedTemplateSpec.sections?.map((s: any, idx: number) => (
                          <div
                            key={idx}
                            className="flex items-center justify-between bg-white/[.03] px-2.5 py-1.5 rounded-md border border-white/5 text-[11px]"
                          >
                            <span className="text-slate-200 font-medium">
                              {idx + 1}. {s.heading || s.label || s.id}
                            </span>
                            <span
                              className={`text-[9px] px-1.5 py-0.5 rounded ${
                                s.required
                                  ? "bg-red-400/10 text-red-300 border border-red-400/20"
                                  : "bg-slate-400/10 text-slate-400"
                              }`}
                            >
                              {s.required ? "Required" : "Optional"}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                ) : (
                  <p className="mt-4 text-xs text-slate-500">Select a template to view analyzed specification.</p>
                )}
              </div>
            </div>
          </section>

          {/* STEP 2: RESUME INTAKE & CONFIGURATION */}
          <div className="grid gap-6 lg:grid-cols-[1fr_1fr] mb-8">
            {/* Packages & Entitlement */}
            <section className="glass rounded-2xl p-6 md:p-7">
              <div className="flex items-center justify-between">
                <div>
                  <p className="section-kicker">Stage 02 / Package</p>
                  <h2 className="mt-2 text-xl font-semibold">Choose Your Plan</h2>
                </div>
                <span className="pill">Server-verified</span>
              </div>

              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                {catalog.map((p: any) => (
                  <button
                    key={p.id}
                    onClick={() => setSelectedPackage(p.id)}
                    className={`rounded-xl border p-4 text-left transition ${
                      selectedPackage === p.id
                        ? "border-violet-300/50 bg-violet-300/[.08]"
                        : "border-white/10 bg-white/[.02] hover:bg-white/[.05]"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <span className="font-medium text-sm">{p.name}</span>
                      <span className="text-base font-semibold">₹{p.price_inr ?? p.price}</span>
                    </div>
                    <p className="mt-2 text-xs leading-5 text-slate-400">
                      {p.desc || p.features?.slice(0, 2).join(" · ")}
                    </p>
                  </button>
                ))}
              </div>

              <button
                className="button-primary mt-5 w-full"
                onClick={startCheckout}
                disabled={busy}
              >
                {busy ? (
                  <LoaderCircle size={16} className="animate-spin" />
                ) : (
                  <ShieldCheck size={16} />
                )}
                Pay Securely with Razorpay
              </button>

              <p className="mt-3 text-[11px] leading-5 text-slate-500">
                In production, checkout requires server verification. In development mode, payment checks are automatically simulated for developer testing.
              </p>
            </section>

            {/* Resume File Upload */}
            <section className="glass rounded-2xl p-6 md:p-7">
              <div className="flex items-center justify-between">
                <div>
                  <p className="section-kicker">Stage 03 / Resume Intake</p>
                  <h2 className="mt-2 text-xl font-semibold">Upload Candidate Resume</h2>
                </div>
                <UploadCloud className="text-cyan-200" />
              </div>

              <label className="mt-4 flex min-h-32 cursor-pointer flex-col items-center justify-center rounded-xl border border-dashed border-violet-300/30 bg-violet-300/[.035] px-5 text-center transition hover:bg-violet-300/[.07]">
                <UploadCloud size={24} className="text-violet-200" />
                <span className="mt-3 text-sm font-medium">
                  {file ? file.name : "Choose PDF or DOCX Resume"}
                </span>
                <span className="mt-1 text-xs text-slate-500">
                  Maximum size 10 MB
                </span>
                <input
                  type="file"
                  accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                  className="sr-only"
                  onChange={(e) => setFile(e.target.files?.[0] || null)}
                />
              </label>

              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                <div>
                  <label className="mb-1.5 block text-xs text-slate-400">Target Role</label>
                  <select
                    className="field text-xs py-2"
                    value={role}
                    onChange={(e) => setRole(e.target.value)}
                  >
                    {[
                      ["sde-general", "General SDE"],
                      ["backend", "Backend Engineer"],
                      ["frontend", "Frontend Engineer"],
                      ["fullstack", "Full-Stack Engineer"],
                      ["ai-ml", "AI / ML Engineer"],
                      ["data-analyst", "Data Analyst"],
                      ["cloud-devops", "Cloud / DevOps"],
                      ["mobile", "Mobile Developer"],
                      ["cybersecurity", "Cybersecurity Specialist"],
                    ].map(([v, l]) => (
                      <option value={v} key={v}>
                        {l}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="mb-1.5 block text-xs text-slate-400">Bound Template</label>
                  <input
                    className="field text-xs py-2 bg-slate-900/50 cursor-not-allowed"
                    readOnly
                    value={`${currentTemplate?.display_name || templateId} (${currentTemplate?.layout || "single-col"})`}
                  />
                </div>
              </div>

              {/* Formatting Controls */}
              <div className="mt-3 grid gap-3 sm:grid-cols-3">
                <div>
                  <label className="mb-1 block text-[11px] text-slate-400">Font</label>
                  <select
                    className="field text-xs py-1.5"
                    value={fontFamily}
                    onChange={(e) => setFontFamily(e.target.value)}
                  >
                    <option>Arial</option>
                    <option>Calibri</option>
                    <option>Georgia</option>
                  </select>
                </div>

                <div>
                  <label className="mb-1 block text-[11px] text-slate-400">
                    Body: {bodySize.toFixed(1)} pt
                  </label>
                  <input
                    type="range"
                    min="7.5"
                    max="11"
                    step="0.5"
                    value={bodySize}
                    onChange={(e) => setBodySize(Number(e.target.value))}
                    className="w-full accent-violet-400 mt-2"
                  />
                </div>

                <div>
                  <label className="mb-1 block text-[11px] text-slate-400">Margins</label>
                  <select
                    className="field text-xs py-1.5"
                    value={marginIn}
                    onChange={(e) => setMarginIn(Number(e.target.value))}
                  >
                    <option value={0.38}>Compact · 0.38 in (LPU)</option>
                    <option value={0.55}>Standard · 0.55 in</option>
                    <option value={0.7}>Roomy · 0.70 in</option>
                  </select>
                </div>
              </div>

              <button
                onClick={upload}
                disabled={busy || (!paidOrder && !isDev) || !file}
                className="button-primary mt-5 w-full disabled:cursor-not-allowed disabled:opacity-40"
              >
                {busy ? (
                  <>
                    <LoaderCircle size={16} className="animate-spin" /> Extracting &amp; Normalizing…
                  </>
                ) : (
                  <>
                    Upload &amp; Analyze Resume <ArrowRight size={16} />
                  </>
                )}
              </button>

              {!paidOrder && !isDev && (
                <p className="mt-2 text-xs text-amber-200/80">
                  A verified paid order is required before upload.
                </p>
              )}
            </section>
          </div>

          {/* ACTIVE RESUME WORKSPACE (ADAPTIVE Q&A + ENHANCEMENT + GENERATION) */}
          {activeResume && (
            <section className="glass rounded-2xl p-6 md:p-8 mb-8 border border-violet-400/30">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-white/10">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="pill text-xs">Resume #{activeResume.id}</span>
                    <span
                      className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
                        activeResume.collection_status === "ready_for_generation"
                          ? "bg-emerald-400/20 text-emerald-300"
                          : activeResume.collection_status === "needs_input"
                            ? "bg-amber-400/20 text-amber-300"
                            : "bg-cyan-400/20 text-cyan-200"
                      }`}
                    >
                      Collection: {activeResume.collection_status}
                    </span>
                    <span
                      className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
                        activeResume.generation_status === "completed"
                          ? "bg-emerald-400/20 text-emerald-300"
                          : "bg-white/10 text-slate-300"
                      }`}
                    >
                      Gen: {activeResume.generation_status}
                    </span>
                  </div>
                  <h2 className="mt-2 text-2xl font-semibold text-white">
                    {activeResume.filename}
                  </h2>
                  <p className="mt-1 text-xs text-slate-400">
                    Bound to template: <strong className="text-slate-200">{activeResume.template_id}</strong> · Target Role: <strong className="text-slate-200">{activeResume.target_role}</strong>
                  </p>
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  <button
                    onClick={() => openResume(activeResume.id)}
                    className="button-secondary text-xs px-3 py-1.5"
                    title="Refresh state"
                  >
                    <RefreshCw size={13} /> Refresh
                  </button>
                  <button
                    onClick={() => setActiveResume(null)}
                    className="button-secondary text-xs px-3 py-1.5"
                  >
                    Close Panel
                  </button>
                </div>
              </div>

              {/* 1. ADAPTIVE Q&A INTERFACE */}
              {missingInfo && missingInfo.questions && missingInfo.questions.length > 0 && (
                <div className="mt-6 rounded-2xl border border-amber-400/30 bg-amber-400/[.04] p-6">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2.5">
                      <HelpCircle size={20} className="text-amber-300" />
                      <div>
                        <h3 className="text-base font-semibold text-white">
                          Adaptive Information Collection ({missingInfo.questions.length} questions)
                        </h3>
                        <p className="text-xs text-amber-200/80">
                          Template <strong>{missingInfo.template_id}</strong> requires or strongly benefits from the following missing details:
                        </p>
                      </div>
                    </div>
                    {missingInfo.missing_required_count > 0 ? (
                      <span className="rounded-full bg-red-400/20 text-red-300 border border-red-400/30 px-3 py-1 text-xs font-semibold">
                        Required Details Missing ({missingInfo.missing_required_count})
                      </span>
                    ) : (
                      <span className="rounded-full bg-emerald-400/20 text-emerald-300 border border-emerald-400/30 px-3 py-1 text-xs font-semibold">
                        Optional Details Only
                      </span>
                    )}
                  </div>

                  <div className="mt-5 space-y-4">
                    {missingInfo.questions.map((q, idx) => (
                      <div
                        key={q.field_path || idx}
                        className="rounded-xl border border-white/10 bg-slate-900/60 p-4 transition focus-within:border-violet-400"
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 block mb-1">
                              Section: {q.section_id || "general"} · Field: {q.field_path}
                            </span>
                            <p className="text-sm font-medium text-slate-100">{q.question}</p>
                            {q.help_text && <p className="text-xs text-slate-400 mt-1">{q.help_text}</p>}
                          </div>
                          {q.required ? (
                            <span className="shrink-0 rounded bg-red-400/15 text-red-300 text-[10px] font-medium px-2 py-0.5">
                              Required
                            </span>
                          ) : (
                            <span className="shrink-0 rounded bg-white/10 text-slate-300 text-[10px] font-medium px-2 py-0.5">
                              Optional
                            </span>
                          )}
                        </div>

                        <div className="mt-3">
                          <input
                            type="text"
                            placeholder={`Enter ${q.field_path}…`}
                            className="field text-xs py-2"
                            value={userAnswers[q.field_path] || ""}
                            onChange={(e) =>
                              setUserAnswers({
                                ...userAnswers,
                                [q.field_path]: e.target.value,
                              })
                            }
                          />
                        </div>
                      </div>
                    ))}
                  </div>

                  <button
                    onClick={submitAnswers}
                    disabled={answeringBusy}
                    className="button-primary mt-4 w-full text-sm"
                  >
                    {answeringBusy ? (
                      <>
                        <LoaderCircle size={15} className="animate-spin" /> Updating Resume Model…
                      </>
                    ) : (
                      <>
                        <Check size={16} /> Submit &amp; Confirm Answers
                      </>
                    )}
                  </button>
                </div>
              )}

              {/* 2. ACTIONS ROW: AI ENHANCE + GENERATE */}
              <div className="mt-6 grid gap-4 sm:grid-cols-2">
                <div className="rounded-xl border border-white/10 bg-white/[.02] p-5">
                  <div className="flex items-center gap-2 mb-2">
                    <Sparkles size={18} className="text-violet-300" />
                    <h3 className="text-sm font-semibold text-white">Gemini Content Enhancement</h3>
                  </div>
                  <p className="text-xs text-slate-400 leading-5">
                    Refines action verbs, technical clarity, and impact without inventing metrics or fabricating experience.
                  </p>
                  <button
                    onClick={enhanceContent}
                    disabled={enhancingBusy}
                    className="button-secondary mt-4 w-full text-xs font-semibold"
                  >
                    {enhancingBusy ? (
                      <>
                        <LoaderCircle size={14} className="animate-spin" /> Enhancing Content…
                      </>
                    ) : (
                      <>
                        <Sparkles size={14} className="text-violet-300" /> Enhance Resume Content
                      </>
                    )}
                  </button>
                </div>

                <div className="rounded-xl border border-white/10 bg-white/[.02] p-5">
                  <div className="flex items-center gap-2 mb-2">
                    <Award size={18} className="text-cyan-300" />
                    <h3 className="text-sm font-semibold text-white">Generate High-Fidelity Resume</h3>
                  </div>
                  <p className="text-xs text-slate-400 leading-5">
                    Builds formatted DOCX and PDF matching the template geometry, followed by strict automated quality validation.
                  </p>
                  <button
                    onClick={generateDocuments}
                    disabled={generatingBusy}
                    className="button-primary mt-4 w-full text-xs font-semibold"
                  >
                    {generatingBusy ? (
                      <>
                        <LoaderCircle size={14} className="animate-spin" /> Rendering &amp; Validating…
                      </>
                    ) : (
                      <>
                        <FileText size={14} /> Generate &amp; Validate Resume
                      </>
                    )}
                  </button>
                </div>
              </div>

              {/* 3. DOCUMENT QUALITY REPORT & DOWNLOADS */}
              {activeResume.validation_report && (
                <div className="mt-6 rounded-2xl border border-emerald-400/30 bg-emerald-400/[.03] p-6">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                    <div>
                      <p className="section-kicker text-emerald-300">Document Validation</p>
                      <h3 className="mt-1 text-xl font-semibold text-white">
                        Document Quality Score:{" "}
                        <span className="text-emerald-300">
                          {activeResume.validation_report.quality_score}/100
                        </span>
                      </h3>
                      <p className="mt-1 text-xs text-slate-300">
                        {activeResume.validation_report.summary}
                      </p>
                    </div>

                    <div className="flex flex-wrap gap-2">
                      <a
                        href={`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/resumes/${activeResume.id}/download?format=docx`}
                        target="_blank"
                        rel="noreferrer"
                        className="button-primary text-xs"
                      >
                        <Download size={14} /> Download DOCX
                      </a>
                      <a
                        href={`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/resumes/${activeResume.id}/download?format=pdf`}
                        target="_blank"
                        rel="noreferrer"
                        className="button-secondary text-xs"
                      >
                        <Download size={14} /> Download PDF
                      </a>
                    </div>
                  </div>

                  {/* Validation Checks */}
                  <div className="mt-5 space-y-2">
                    <p className="text-xs font-medium text-slate-400">Automated Validation Checks:</p>
                    <div className="grid gap-2 sm:grid-cols-2">
                      {activeResume.validation_report.checks?.map((chk: any, idx: number) => (
                        <div
                          key={idx}
                          className="flex items-start gap-2.5 rounded-lg border border-white/5 bg-slate-900/60 p-2.5 text-xs"
                        >
                          {chk.passed ? (
                            <CheckCircle2 size={16} className="text-emerald-400 shrink-0 mt-0.5" />
                          ) : (
                            <AlertCircle size={16} className="text-amber-400 shrink-0 mt-0.5" />
                          )}
                          <div>
                            <span className="font-medium text-slate-200 block">{chk.name}</span>
                            <span className="text-[11px] text-slate-400">{chk.message}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {/* 4. ADVISORY REVIEW & FIXES */}
              {activeResume.review && (
                <div className="mt-8 border-t border-white/10 pt-6">
                  <h3 className="text-lg font-semibold text-white mb-4">Advisory Role Analysis</h3>

                  <div className="grid gap-5 md:grid-cols-[160px_1fr]">
                    <div className="flex flex-col items-center justify-center rounded-2xl border border-violet-300/20 bg-violet-300/[.06] p-5">
                      <span className="text-4xl font-semibold">
                        {activeResume.review.role_fit_score}
                        <span className="text-base text-slate-500">/100</span>
                      </span>
                      <span className="mt-2 text-center text-xs text-slate-400">Role-fit score</span>
                    </div>

                    <div>
                      <h4 className="font-semibold text-sm text-slate-200">Priority Fixes</h4>
                      <ol className="mt-3 list-decimal space-y-1.5 pl-5 text-xs leading-5 text-slate-300">
                        {activeResume.review.priority_fixes?.map((x: string, i: number) => (
                          <li key={i}>{x}</li>
                        ))}
                      </ol>
                    </div>
                  </div>

                  <div className="mt-6 grid gap-4 md:grid-cols-2">
                    <div className="rounded-xl border border-white/10 p-4">
                      <h4 className="font-semibold text-sm text-slate-200">ATS Compatibility Findings</h4>
                      <div className="mt-3 space-y-2">
                        {activeResume.review.ats_findings?.map((x: any, i: number) => (
                          <div key={i} className="border-l-2 border-violet-300/50 pl-3">
                            <p className="text-xs font-medium text-slate-200">{x.issue}</p>
                            <p className="mt-0.5 text-[11px] leading-4 text-slate-400">{x.recommendation}</p>
                          </div>
                        ))}
                      </div>
                    </div>

                    <div className="rounded-xl border border-white/10 p-4">
                      <h4 className="font-semibold text-sm text-slate-200">Missing Target Role Keywords</h4>
                      <div className="mt-3 flex flex-wrap gap-1.5">
                        {activeResume.review.missing_keywords?.map((x: string) => (
                          <span key={x} className="pill text-xs">
                            {x}
                          </span>
                        ))}
                      </div>
                      <p className="mt-4 text-[11px] text-slate-500">{activeResume.review.advisory_note}</p>
                    </div>
                  </div>

                  {activeResume.review.bullet_rewrites?.length > 0 && (
                    <div className="mt-6">
                      <h4 className="font-semibold text-sm text-slate-200 mb-3">Bullet Point Improvements</h4>
                      <div className="space-y-3">
                        {activeResume.review.bullet_rewrites.map((b: any, i: number) => (
                          <div key={i} className="grid gap-3 rounded-xl border border-white/10 p-4 md:grid-cols-2 text-xs">
                            <div>
                              <p className="mb-1 text-[10px] uppercase tracking-wider text-slate-500">Original</p>
                              <p className="leading-5 text-slate-300">{b.original}</p>
                            </div>
                            <div>
                              <p className="mb-1 text-[10px] uppercase tracking-wider text-cyan-200">Suggested</p>
                              <p className="leading-5 text-slate-200">{b.rewritten}</p>
                              {b.needs_input && (
                                <p className="mt-2 text-amber-200">Needs input: {b.question}</p>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {activeResume.package_id === "full-makeover" && (
                <div className="mt-6 rounded-xl border border-violet-300/20 p-4">
                  <h4 className="font-semibold text-sm text-slate-200">Included Revision Round</h4>
                  <p className="mt-1 text-xs text-slate-400">Describe the corrections you want the reviewer to consider.</p>
                  <textarea
                    className="field mt-3 min-h-24 text-xs"
                    value={revisionNotes}
                    onChange={(e) => setRevisionNotes(e.target.value)}
                    placeholder="Tell us what needs adjusting…"
                  />
                  <button
                    className="button-primary mt-3 text-xs"
                    disabled={revisionNotes.trim().length < 5}
                    onClick={() => requestRevision(activeResume.id)}
                  >
                    Request Revision <ArrowRight size={14} />
                  </button>
                </div>
              )}
            </section>
          )}

          {/* HISTORY & PRIVACY */}
          <div className="grid gap-6 lg:grid-cols-[1.1fr_.9fr]">
            {/* History Table */}
            <section className="glass rounded-2xl p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="section-kicker">Stage 04 / History</p>
                  <h2 className="mt-2 text-lg font-semibold">Your Resumes</h2>
                </div>
                <button
                  onClick={refresh}
                  className="button-secondary px-3 py-2 text-xs"
                  aria-label="Refresh jobs"
                >
                  <RefreshCw size={14} /> Refresh
                </button>
              </div>

              {resumes.length === 0 ? (
                <div className="mt-5 rounded-xl border border-dashed border-white/10 p-7 text-center">
                  <FileText size={24} className="mx-auto text-slate-500" />
                  <p className="mt-3 text-sm font-medium">No resumes uploaded yet</p>
                  <p className="mt-1 text-xs text-slate-500">
                    Upload your first resume above to begin intelligent processing.
                  </p>
                </div>
              ) : (
                <div className="mt-4 space-y-3">
                  {resumes.map((r) => (
                    <div
                      key={r.id}
                      className="flex flex-col justify-between gap-3 rounded-xl border border-white/10 bg-white/[.02] p-4 sm:flex-row sm:items-center"
                    >
                      <div className="flex min-w-0 items-start gap-3">
                        <span className="rounded-lg bg-violet-300/10 p-2 text-violet-200">
                          <FileText size={17} />
                        </span>
                        <div className="min-w-0">
                          <p className="truncate text-sm font-medium text-white">{r.filename}</p>
                          <p className="mt-0.5 text-xs text-slate-500">
                            {r.target_role} · {r.template_id} · #{r.id}
                          </p>
                        </div>
                      </div>

                      <div className="flex items-center gap-2">
                        <span
                          className={`rounded-full px-2.5 py-0.5 text-xs ${
                            r.status === "completed"
                              ? "bg-emerald-300/10 text-emerald-200"
                              : r.status === "failed"
                                ? "bg-red-300/10 text-red-200"
                                : "bg-violet-300/10 text-violet-200"
                          }`}
                        >
                          {r.status}
                        </span>
                        <button
                          onClick={() => openResume(r.id)}
                          className="button-secondary px-3 py-1.5 text-xs"
                        >
                          Open Workspace
                        </button>
                        {r.status === "failed" && (
                          <button
                            onClick={() => retry(r.id)}
                            className="button-secondary px-3 py-1.5 text-xs"
                          >
                            Retry
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </section>

            {/* Privacy Controls */}
            <section className="glass rounded-2xl p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="section-kicker">Data Protection</p>
                  <h2 className="mt-2 text-lg font-semibold">Privacy &amp; Data Rights</h2>
                </div>
                <ShieldCheck className="text-cyan-200" />
              </div>

              <p className="mt-3 text-xs leading-5 text-slate-400">
                Uploaded files and extracted models are private to your authenticated account. AI processing uses Google Gemini with non-fabrication guardrails.
              </p>

              <div className="mt-5 flex flex-wrap gap-3">
                <a
                  href={`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/account/export`}
                  className="button-secondary text-xs"
                  target="_blank"
                  rel="noreferrer"
                >
                  Export Data <Download size={13} />
                </a>

                <button
                  onClick={async () => {
                    if (confirm("Delete your account and all stored resumes? This cannot be undone.")) {
                      try {
                        await api("/account", { method: "DELETE" });
                        await api("/auth/logout", { method: "POST" });
                        window.location.href = "/";
                      } catch (e) {
                        setError(e instanceof Error ? e.message : "Deletion failed");
                      }
                    }
                  }}
                  className="rounded-full border border-red-300/20 px-3 py-1.5 text-xs text-red-200 hover:bg-red-300/10"
                >
                  Delete Account
                </button>
              </div>
            </section>
          </div>

          {/* Feedback & Testimonials */}
          <section className="glass rounded-2xl p-6 mt-6">
            <p className="section-kicker">Community Feedback</p>
            <h2 className="mt-2 text-lg font-semibold">Share Your Experience</h2>
            <p className="mt-1 text-xs text-slate-400">
              Testimonials are reviewed by an administrator before appearing publicly.
            </p>
            <div className="mt-4 grid gap-3 md:grid-cols-[220px_1fr]">
              <input
                className="field text-xs"
                value={testimonialName}
                onChange={(e) => setTestimonialName(e.target.value)}
                maxLength={100}
                placeholder="Display name (optional)"
              />
              <textarea
                className="field min-h-20 text-xs"
                value={testimonialText}
                onChange={(e) => setTestimonialText(e.target.value)}
                maxLength={1000}
                placeholder="What was useful? (20–1000 characters)"
              />
            </div>
            <label className="mt-3 flex items-start gap-2 text-xs leading-5 text-slate-400">
              <input
                type="checkbox"
                className="mt-0.5 rounded border-white/20 bg-slate-900"
                checked={testimonialConsent}
                onChange={(e) => setTestimonialConsent(e.target.checked)}
              />
              <span>I consent to displaying this testimonial publicly if an administrator approves it.</span>
            </label>
            <button
              className="button-secondary mt-3 text-xs"
              disabled={testimonialText.trim().length < 20 || !testimonialConsent}
              onClick={submitTestimonial}
            >
              Submit Testimonial <ArrowRight size={14} />
            </button>
          </section>
        </>
      )}

      {/* Global Notifications */}
      {message && (
        <p
          role="status"
          className="mt-6 flex gap-2 rounded-xl border border-cyan-300/20 bg-cyan-300/[.05] p-4 text-xs text-cyan-100"
        >
          <CheckCircle2 size={16} className="shrink-0 mt-0.5" />
          {message}
        </p>
      )}

      {error && (
        <p
          role="alert"
          className="mt-6 flex gap-2 rounded-xl border border-red-300/20 bg-red-300/[.06] p-4 text-xs text-red-100"
        >
          <AlertCircle size={16} className="shrink-0 mt-0.5" />
          {error}
        </p>
      )}

      <p className="mt-8 flex items-center gap-2 text-xs leading-5 text-slate-600">
        <Settings2 size={14} />
        ResumeIQ AI Engine v2.0 · Template-Aware Multi-Stage Intelligence Architecture.
      </p>
    </main>
  );
}
