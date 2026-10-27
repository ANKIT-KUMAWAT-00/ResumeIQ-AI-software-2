// "use client";import {useEffect,useState,Suspense} from "react";import {useSearchParams} from "next/navigation";import Link from "next/link";import {api,packages} from "@/lib/api";import {ArrowRight,UploadCloud,FileText,ShieldCheck,RefreshCw,Download,CheckCircle2,AlertCircle,LoaderCircle,LogIn,Settings2} from "lucide-react";
// type User={id:number;email:string;role:string};type Resume={id:number;filename:string;status:string;target_role:string;template_id:string;created_at:string};type Template={template_id:string;display_name:string;description:string};
// declare global{interface Window{Razorpay?:new(options:any)=>{open:()=>void}}}
// export default function Workspace(){return <Suspense fallback={<main className="mx-auto max-w-7xl px-5 py-16 text-slate-400">Loading workspace…</main>}><WorkspaceContent/></Suspense>}
// function WorkspaceContent(){const params=useSearchParams();const initialTemplate=params.get('template')||'ats-clean';const [user,setUser]=useState<User|null>(null);const [authChecked,setAuthChecked]=useState(false);const [catalog,setCatalog]=useState<any[]>(packages);const [templates,setTemplates]=useState<Template[]>([]);const [orders,setOrders]=useState<any[]>([]);const [resumes,setResumes]=useState<Resume[]>([]);const [selectedPackage,setSelectedPackage]=useState(params.get('package')||'resume-template');const [templateId,setTemplateId]=useState(initialTemplate);const [role,setRole]=useState('sde-general');const [bodySize,setBodySize]=useState(8.5);const [marginIn,setMarginIn]=useState((initialTemplate==='lpu-standard'||initialTemplate==='modern-one-page')?0.38:0.55);const [fontFamily,setFontFamily]=useState('Arial');const [revisionNotes,setRevisionNotes]=useState('');const [testimonialName,setTestimonialName]=useState('');const [testimonialText,setTestimonialText]=useState('');const [testimonialConsent,setTestimonialConsent]=useState(false);const [file,setFile]=useState<File|null>(null);const [message,setMessage]=useState('');const [error,setError]=useState('');const [busy,setBusy]=useState(false);const [activeResume,setActiveResume]=useState<any>(null);
// async function refresh(){try{const me=await api<User>('/auth/me');setUser(me);const [ts,rs,os]=await Promise.all([api<Template[]>('/templates'),api<Resume[]>('/resumes'),api<any[]>('/orders/me')]);setTemplates(ts);setResumes(rs);setOrders(os)}catch{setUser(null)}finally{setAuthChecked(true)}}useEffect(()=>{refresh();api<any[]>('/packages').then(setCatalog).catch(()=>{});const script=document.createElement('script');script.src='https://checkout.razorpay.com/v1/checkout.js';script.async=true;document.body.appendChild(script);return()=>{script.remove()}},[]);
// async function startCheckout(){setError('');setMessage('');if(!user){window.location.href='/login';return}setBusy(true);try{const order=await api<any>('/payments/orders',{method:'POST',body:JSON.stringify({package_id:selectedPackage})});if(!window.Razorpay)throw new Error('Razorpay checkout did not load. Check your network and retry.');const checkout=new window.Razorpay({key:order.key_id,amount:order.amount,currency:order.currency,name:'ResumeIQ AI',description:order.package.name,order_id:order.razorpay_order_id,prefill:{email:user.email},theme:{color:'#9b8cff'},handler:async(resp:any)=>{try{const verified=await api<any>('/payments/verify',{method:'POST',body:JSON.stringify({internal_order_id:order.internal_order_id,razorpay_order_id:resp.razorpay_order_id,razorpay_payment_id:resp.razorpay_payment_id,razorpay_signature:resp.razorpay_signature})});setOrders(o=>[{id:order.internal_order_id,package_id:selectedPackage,status:verified.status},...o]);setMessage(verified.status==='paid'?'Payment signature verified. You can now upload your resume.':'Payment is awaiting provider confirmation. Refresh in a moment.')}catch(e){setError(e instanceof Error?e.message:'Payment verification failed.')}} ,modal:{ondismiss:()=>setMessage('Checkout closed. No payment is assumed successful unless verified by the server.')}});checkout.open()}catch(e){setError(e instanceof Error?e.message:'Could not start checkout.')}finally{setBusy(false)}}
// async function upload(){setError('');setMessage('');if(!file){setError('Choose a PDF or DOCX file first.');return}const paid=orders.find(o=>o.status==='paid');if(!paid){setError('Complete and verify a package payment before uploading.');return}setBusy(true);try{const form=new FormData();form.append('file',file);form.append('order_id',String(paid.id));form.append('target_role',role);form.append('template_id',templateId);form.append('template_overrides',JSON.stringify({fonts:{family:fontFamily,body_pt:bodySize},margins:{top_in:marginIn,bottom_in:marginIn,left_in:marginIn,right_in:marginIn}}));const result=await api<any>('/resumes',{method:'POST',body:form});setMessage(`Resume #${result.id} accepted. Current status: ${result.status}.`);setFile(null);await refresh()}catch(e){setError(e instanceof Error?e.message:'Upload failed.')}finally{setBusy(false)}}
// async function openResume(id:number){setError('');try{const r=await api<any>(`/resumes/${id}`);setActiveResume(r);await refresh()}catch(e){setError(e instanceof Error?e.message:'Could not load resume.')}}async function retry(id:number){try{await api(`/resumes/${id}/retry`,{method:'POST'});setMessage('Retry submitted.');await refresh()}catch(e){setError(e instanceof Error?e.message:'Retry failed.')}}async function requestRevision(id:number){try{await api(`/resumes/${id}/revision`,{method:'POST',body:JSON.stringify({notes:revisionNotes})});setMessage('Revision request submitted for admin review.');setRevisionNotes('')}catch(e){setError(e instanceof Error?e.message:'Could not request revision.')}}async function submitTestimonial(){try{await api('/testimonials',{method:'POST',body:JSON.stringify({display_name:testimonialName,body:testimonialText,consent_public:testimonialConsent})});setMessage('Thank you. Your testimonial is awaiting admin approval.');setTestimonialText('')}catch(e){setError(e instanceof Error?e.message:'Could not submit testimonial.')}}async function logout(){await api('/auth/logout',{method:'POST'});setUser(null);window.location.href='/'}
// const paidOrder=orders.find(o=>o.status==='paid');return <main className="mx-auto min-h-[78vh] max-w-7xl px-5 py-10 md:px-8 md:py-14"><div className="mb-10 flex flex-col justify-between gap-4 md:flex-row md:items-end"><div><p className="section-kicker">Your workspace</p><h1 className="mt-3 text-3xl font-semibold tracking-tight sm:text-4xl">Resume intelligence, <span className="gradient-text">in progress.</span></h1><p className="mt-3 max-w-2xl text-sm leading-6 text-slate-400">Choose your package, verify payment, upload a resume, then follow the actual backend job status.</p></div>{user?<div className="flex items-center gap-3 rounded-full border border-white/10 bg-white/[.03] px-4 py-2"><span className="h-2 w-2 rounded-full bg-cyan-300"/><span className="max-w-52 truncate text-sm">{user.email}</span><button onClick={logout} className="text-xs text-slate-400 hover:text-white">Sign out</button></div>:<Link href="/login" className="button-primary self-start"><LogIn size={16}/> Sign in to continue</Link>}</div>{!authChecked?<div className="glass rounded-2xl p-6 text-slate-400">Checking your session…</div>:!user?<div className="glass rounded-2xl p-8"><h2 className="text-xl font-semibold">Sign in to access your workspace</h2><p className="mt-2 text-sm text-slate-400">Your resumes and orders are private to your account.</p><Link href="/login" className="button-primary mt-5">Continue to sign in <ArrowRight size={16}/></Link></div>:<><div className="grid gap-6 lg:grid-cols-[1.05fr_.95fr]"><section className="glass rounded-2xl p-6 md:p-7"><div className="flex items-center justify-between"><div><p className="section-kicker">01 / Package</p><h2 className="mt-2 text-xl font-semibold">Choose your outcome</h2></div><span className="pill">Server-priced</span></div><div className="mt-5 grid gap-3 sm:grid-cols-2">{catalog.map((p:any)=><button key={p.id} onClick={()=>setSelectedPackage(p.id)} className={`rounded-xl border p-4 text-left transition ${selectedPackage===p.id?'border-violet-300/50 bg-violet-300/[.08]':'border-white/10 bg-white/[.02] hover:bg-white/[.05]'}`}><div className="flex items-start justify-between gap-2"><span className="font-medium">{p.name}</span><span className="text-lg font-semibold">₹{p.price_inr??p.price}</span></div><p className="mt-2 text-xs leading-5 text-slate-400">{p.desc||p.features?.slice(0,2).join(' · ')}</p></button>)}</div><button className="button-primary mt-5 w-full" onClick={startCheckout} disabled={busy}>{busy?<LoaderCircle size={16} className="animate-spin"/>:<ShieldCheck size={16}/>} Pay securely with Razorpay</button><p className="mt-3 text-xs leading-5 text-slate-500">Checkout requires valid server credentials. The app never marks payment successful based only on a browser event.</p></section><section className="glass rounded-2xl p-6 md:p-7"><div className="flex items-center justify-between"><div><p className="section-kicker">02 / Upload</p><h2 className="mt-2 text-xl font-semibold">Prepare your analysis</h2></div><UploadCloud className="text-cyan-200"/></div><label className="mt-5 flex min-h-36 cursor-pointer flex-col items-center justify-center rounded-xl border border-dashed border-violet-300/30 bg-violet-300/[.035] px-5 text-center transition hover:bg-violet-300/[.07]"><UploadCloud size={24} className="text-violet-200"/><span className="mt-3 text-sm font-medium">{file?file.name:'Choose PDF or DOCX'}</span><span className="mt-1 text-xs text-slate-500">Maximum size 10 MB</span><input type="file" accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" className="sr-only" onChange={e=>setFile(e.target.files?.[0]||null)}/></label><div className="mt-4 grid gap-4 sm:grid-cols-2"><div><label className="mb-2 block text-xs text-slate-400">Target role</label><select className="field" value={role} onChange={e=>setRole(e.target.value)}>{[['sde-general','General SDE'],['backend','Backend'],['frontend','Frontend'],['fullstack','Full-stack'],['ai-ml','AI / ML'],['data-analyst','Data Analyst'],['cloud-devops','Cloud / DevOps'],['mobile','Mobile'],['cybersecurity','Cybersecurity']].map(([v,l])=><option value={v} key={v}>{l}</option>)}</select></div><div><label className="mb-2 block text-xs text-slate-400">Resume template</label><select className="field" value={templateId} onChange={e=>{setTemplateId(e.target.value);setMarginIn((e.target.value==='lpu-standard'||e.target.value==='modern-one-page')?0.38:0.55);setBodySize(e.target.value==='ats-clean'?9.5:8.5)}}>{(templates.length?templates:[{template_id:'ats-clean',display_name:'ATS Clean'}]).map(t=><option value={t.template_id} key={t.template_id}>{t.display_name}</option>)}</select></div></div><div className="mt-4 rounded-xl border border-white/10 bg-[#f6f7fb] p-4 text-slate-800"><div className="flex items-center justify-between gap-3 border-b border-slate-300 pb-2"><div><p className="font-semibold" style={{fontFamily,fontSize:'15pt'}}>Your Name</p><p className="mt-1 text-[10px] text-slate-500">email · phone · LinkedIn · GitHub</p></div><span className="rounded-full bg-indigo-100 px-2 py-1 text-[9px] font-semibold text-indigo-700">{templateId}</span></div><div className="mt-3 grid gap-3 sm:grid-cols-[1fr_1fr]" style={{padding:`${Math.max(2,marginIn*8)}px`}}><div><p className="text-[10px] font-bold tracking-wider text-indigo-700">EXPERIENCE</p><div className="mt-2 h-1.5 w-full rounded bg-slate-300"/><div className="mt-1.5 h-1.5 w-5/6 rounded bg-slate-300"/><div className="mt-1.5 h-1.5 w-4/6 rounded bg-slate-300"/></div><div><p className="text-[10px] font-bold tracking-wider text-indigo-700">PROJECTS</p><div className="mt-2 h-1.5 w-full rounded bg-slate-300"/><div className="mt-1.5 h-1.5 w-5/6 rounded bg-slate-300"/><div className="mt-1.5 h-1.5 w-3/5 rounded bg-slate-300"/></div></div><p className="mt-2 text-[10px] text-slate-500">Approximate live preview; final pagination and PDF rendering may differ.</p></div><div className="mt-4 grid gap-4 sm:grid-cols-3"><div><label className="mb-2 block text-xs text-slate-400">Font family</label><select className="field" value={fontFamily} onChange={e=>setFontFamily(e.target.value)}><option>Arial</option><option>Calibri</option><option>Georgia</option></select></div><div><label className="mb-2 block text-xs text-slate-400">Body size: {bodySize.toFixed(1)} pt</label><input type="range" min="7.5" max="11" step="0.5" value={bodySize} onChange={e=>setBodySize(Number(e.target.value))} className="w-full accent-violet-400"/></div><div><label className="mb-2 block text-xs text-slate-400">Page margins</label><select className="field" value={marginIn} onChange={e=>setMarginIn(Number(e.target.value))}><option value={0.35}>Compact · 0.35 in</option><option value={0.55}>Standard · 0.55 in</option><option value={0.7}>Roomy · 0.70 in</option></select></div></div><button onClick={upload} disabled={busy||!paidOrder||!file} className="button-primary mt-5 w-full disabled:cursor-not-allowed disabled:opacity-40">{busy?'Working…':'Upload and start analysis'} <ArrowRight size={16}/></button>{!paidOrder&&<p className="mt-3 text-xs text-amber-200/80">A verified paid order is required before upload.</p>}</section></div><div className="mt-6 grid gap-6 lg:grid-cols-[.85fr_1.15fr]"><section className="glass rounded-2xl p-6"><div className="flex items-center justify-between"><div><p className="section-kicker">Privacy controls</p><h2 className="mt-2 text-lg font-semibold">Your data, your choice</h2></div><ShieldCheck className="text-cyan-200"/></div><p className="mt-3 text-sm leading-6 text-slate-400">Resume files are private, retention is configurable, and AI processing uses Google Gemini. Export or delete account data from these controls.</p><div className="mt-5 flex flex-wrap gap-3"><a href={`${process.env.NEXT_PUBLIC_API_URL||'http://localhost:8000'}/api/account/export`} className="button-secondary text-sm" target="_blank" rel="noreferrer">Export account data <Download size={14}/></a><button onClick={async()=>{if(confirm('Delete your ResumeIQ AI account data? This action cannot be undone.')){try{await api('/account',{method:'DELETE'});await api('/auth/logout',{method:'POST'});window.location.href='/'}catch(e){setError(e instanceof Error?e.message:'Deletion failed')}}}} className="rounded-full border border-red-300/20 px-4 py-2 text-sm text-red-200 hover:bg-red-300/10">Delete account</button></div></section><section className="glass rounded-2xl p-6"><div className="flex items-center justify-between"><div><p className="section-kicker">03 / History</p><h2 className="mt-2 text-lg font-semibold">Your resume jobs</h2></div><button onClick={refresh} className="button-secondary px-3 py-2" aria-label="Refresh jobs"><RefreshCw size={15}/></button></div>{resumes.length===0?<div className="mt-5 rounded-xl border border-dashed border-white/10 p-7 text-center"><FileText size={24} className="mx-auto text-slate-500"/><p className="mt-3 text-sm font-medium">No resume jobs yet</p><p className="mt-1 text-xs text-slate-500">Once you upload, processing status will appear here.</p></div>:<div className="mt-4 space-y-3">{resumes.map(r=><div key={r.id} className="flex flex-col justify-between gap-3 rounded-xl border border-white/10 bg-white/[.02] p-4 sm:flex-row sm:items-center"><div className="flex min-w-0 items-start gap-3"><span className="rounded-lg bg-violet-300/10 p-2 text-violet-200"><FileText size={17}/></span><div className="min-w-0"><p className="truncate text-sm font-medium">{r.filename}</p><p className="mt-1 text-xs text-slate-500">{r.target_role} · {r.template_id} · #{r.id}</p></div></div><div className="flex items-center gap-2"><span className={`rounded-full px-2.5 py-1 text-xs ${r.status==='completed'?'bg-emerald-300/10 text-emerald-200':r.status==='failed'?'bg-red-300/10 text-red-200':'bg-violet-300/10 text-violet-200'}`}>{r.status}</span><button onClick={()=>openResume(r.id)} className="button-secondary px-3 py-2 text-xs">View</button>{r.status==='failed'&&<button onClick={()=>retry(r.id)} className="button-secondary px-3 py-2 text-xs">Retry</button>}</div></div>)}</div>}</section></div><section className="glass mt-6 rounded-2xl p-6"><p className="section-kicker">Feedback</p><h2 className="mt-2 text-lg font-semibold">Share your experience</h2><p className="mt-1 text-sm text-slate-400">Testimonials are reviewed by an administrator before they appear publicly.</p><div className="mt-4 grid gap-3 md:grid-cols-[220px_1fr]"><input className="field" value={testimonialName} onChange={e=>setTestimonialName(e.target.value)} maxLength={100} placeholder="Display name (optional)"/><textarea className="field min-h-20" value={testimonialText} onChange={e=>setTestimonialText(e.target.value)} maxLength={1000} placeholder="What was useful? (20–1000 characters)"/></div><label className="mt-3 flex items-start gap-2 text-xs leading-5 text-slate-400"><input type="checkbox" className="mt-0.5 rounded border-white/20 bg-slate-900" checked={testimonialConsent} onChange={e=>setTestimonialConsent(e.target.checked)}/><span>I consent to displaying this testimonial publicly if an administrator approves it.</span></label><button className="button-secondary mt-3" disabled={testimonialText.trim().length<20||!testimonialConsent} onClick={submitTestimonial}>Submit testimonial <ArrowRight size={15}/></button></section>{activeResume&&<section className="glass mt-6 rounded-2xl p-6 md:p-8"><div className="flex items-start justify-between gap-4"><div><p className="section-kicker">Resume #{activeResume.id}</p><h2 className="mt-2 text-xl font-semibold">Analysis results</h2><p className="mt-2 text-sm text-slate-400">Status: {activeResume.status}</p></div><button onClick={()=>setActiveResume(null)} className="button-secondary">Close</button></div>{activeResume.status==='failed'&&<p className="mt-5 flex gap-2 rounded-xl bg-red-300/[.07] p-4 text-sm text-red-200"><AlertCircle size={18}/>{activeResume.error||'Processing failed.'}</p>}{activeResume.status!=='completed'&&activeResume.status!=='failed'&&<p className="mt-5 flex gap-2 rounded-xl bg-violet-300/[.06] p-4 text-sm text-violet-100"><LoaderCircle size={18} className="animate-spin"/>The backend reports this job is still processing. Refresh shortly for updates.</p>}{activeResume.review&&<><div className="mt-6 grid gap-5 md:grid-cols-[160px_1fr]"><div className="flex flex-col items-center justify-center rounded-2xl border border-violet-300/20 bg-violet-300/[.06] p-5"><span className="text-4xl font-semibold">{activeResume.review.role_fit_score}<span className="text-base text-slate-500">/100</span></span><span className="mt-2 text-center text-xs text-slate-400">Advisory role-fit score</span></div><div><h3 className="font-semibold">Priority fixes</h3><ol className="mt-3 list-decimal space-y-2 pl-5 text-sm leading-6 text-slate-300">{activeResume.review.priority_fixes.map((x:string,i:number)=><li key={i}>{x}</li>)}</ol></div></div><div className="mt-6 grid gap-4 md:grid-cols-2"><div className="rounded-xl border border-white/10 p-4"><h3 className="font-semibold">ATS findings</h3><div className="mt-3 space-y-3">{activeResume.review.ats_findings.map((x:any,i:number)=><div key={i} className="border-l-2 border-violet-300/50 pl-3"><p className="text-sm font-medium">{x.issue}</p><p className="mt-1 text-xs leading-5 text-slate-400">{x.recommendation}</p></div>)}</div></div><div className="rounded-xl border border-white/10 p-4"><h3 className="font-semibold">Missing role keywords</h3><div className="mt-3 flex flex-wrap gap-2">{activeResume.review.missing_keywords.map((x:string)=><span key={x} className="pill">{x}</span>)}</div><p className="mt-5 text-xs leading-5 text-slate-500">{activeResume.review.advisory_note}</p></div></div><div className="mt-6"><h3 className="font-semibold">Before / after suggestions</h3><div className="mt-3 space-y-3">{activeResume.review.bullet_rewrites.map((b:any,i:number)=><div key={i} className="grid gap-3 rounded-xl border border-white/10 p-4 md:grid-cols-2"><div><p className="mb-2 text-xs uppercase tracking-wider text-slate-500">Original</p><p className="text-sm leading-6 text-slate-300">{b.original}</p></div><div><p className="mb-2 text-xs uppercase tracking-wider text-cyan-200">Suggested</p><p className="text-sm leading-6 text-slate-200">{b.rewritten}</p>{b.needs_input&&<p className="mt-2 text-xs text-amber-200">Needs input: {b.question}</p>}</div></div>)}</div></div>{activeResume.review.linkedin&&<div className="mt-6 rounded-xl border border-violet-300/20 p-5"><h3 className="font-semibold">LinkedIn optimization</h3><p className="mt-3 text-sm text-slate-400">{activeResume.review.linkedin.about_rewrite}</p><div className="mt-3 flex flex-wrap gap-2">{activeResume.review.linkedin.headlines.map((x:string)=><span key={x} className="pill">{x}</span>)}</div></div>}</>}{activeResume.voice_note_url&&<div className="mt-5"><a href={activeResume.voice_note_url} target="_blank" rel="noreferrer" className="button-secondary">Open admin voice-note link <ArrowRight size={15}/></a></div>}{activeResume.package_id==='full-makeover'&&<div className="mt-6 rounded-xl border border-violet-300/20 p-4"><h3 className="font-semibold">Included revision round</h3><p className="mt-1 text-xs text-slate-400">Describe the corrections you want the reviewer to consider.</p><textarea className="field mt-3 min-h-24" value={revisionNotes} onChange={e=>setRevisionNotes(e.target.value)} placeholder="Tell us what needs adjusting…"/><button className="button-primary mt-3" disabled={revisionNotes.trim().length<5} onClick={()=>requestRevision(activeResume.id)}>Request revision <ArrowRight size={15}/></button></div>}<div className="mt-5"><a href={`${process.env.NEXT_PUBLIC_API_URL||'http://localhost:8000'}/api/resumes/${activeResume.id}/original/download`} target="_blank" rel="noreferrer" className="button-secondary"><Download size={15}/> Download original resume</a></div>{activeResume.outputs?.length>0&&<div className="mt-6 flex flex-wrap gap-3">{activeResume.outputs.map((o:any)=><a key={o.id} href={`${process.env.NEXT_PUBLIC_API_URL||'http://localhost:8000'}${o.download_url}`} target="_blank" rel="noreferrer" className="button-primary"><Download size={16}/> Download {o.kind.toUpperCase()}</a>)}</div>}</section>}</>}{message&&<p role="status" className="mt-5 flex gap-2 rounded-xl border border-cyan-300/20 bg-cyan-300/[.05] p-4 text-sm text-cyan-100"><CheckCircle2 size={18}/>{message}</p>}{error&&<p role="alert" className="mt-5 flex gap-2 rounded-xl border border-red-300/20 bg-red-300/[.06] p-4 text-sm text-red-100"><AlertCircle size={18}/>{error}</p>}<p className="mt-8 flex items-center gap-2 text-xs leading-5 text-slate-600"><Settings2 size={14}/> Analysis requires configured Gemini credentials; document downloads require the relevant paid package entitlement.</p></main>}

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
} from "lucide-react";

type User = { id: number; email: string; role: string };
type Resume = {
  id: number;
  filename: string;
  status: string;
  target_role: string;
  template_id: string;
  created_at: string;
};
type Template = {
  template_id: string;
  display_name: string;
  description: string;
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
  // This bypass is enabled only when NEXT_PUBLIC_APP_ENV is "development".
  const devPaymentBypass =
    process.env.NEXT_PUBLIC_APP_ENV === "development";

  const params = useSearchParams();
  const initialTemplate = params.get("template") || "ats-clean";

  const [user, setUser] = useState<User | null>(null);
  const [authChecked, setAuthChecked] = useState(false);
  const [catalog, setCatalog] = useState<any[]>(packages);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [orders, setOrders] = useState<any[]>([]);
  const [resumes, setResumes] = useState<Resume[]>([]);
  const [selectedPackage, setSelectedPackage] = useState(
    params.get("package") || "resume-template",
  );
  const [templateId, setTemplateId] = useState(initialTemplate);
  const [role, setRole] = useState("sde-general");
  const [bodySize, setBodySize] = useState(8.5);
  const [marginIn, setMarginIn] = useState(
    initialTemplate === "lpu-standard" ||
      initialTemplate === "modern-one-page"
      ? 0.38
      : 0.55,
  );
  const [fontFamily, setFontFamily] = useState("Arial");
  const [revisionNotes, setRevisionNotes] = useState("");
  const [testimonialName, setTestimonialName] = useState("");
  const [testimonialText, setTestimonialText] = useState("");
  const [testimonialConsent, setTestimonialConsent] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [activeResume, setActiveResume] = useState<any>(null);

  async function refresh() {
    try {
      const me = await api<User>("/auth/me");
      setUser(me);

      const [ts, rs, os] = await Promise.all([
        api<Template[]>("/templates"),
        api<Resume[]>("/resumes"),
        api<any[]>("/orders/me"),
      ]);

      setTemplates(ts);
      setResumes(rs);
      setOrders(os);
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
        throw new Error(
          "Razorpay checkout did not load. Check your network and retry.",
        );
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
            setError(
              e instanceof Error
                ? e.message
                : "Payment verification failed.",
            );
          }
        },

        modal: {
          ondismiss: () =>
            setMessage(
              "Checkout closed. No payment is assumed successful unless verified by the server.",
            ),
        },
      });

      checkout.open();
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Could not start checkout.",
      );
    } finally {
      setBusy(false);
    }
  }

  // UPDATED: In development, uploading does not require a paid order.
  // In production, a verified paid order is still required.
  async function upload() {
    setError("");
    setMessage("");

    if (!file) {
      setError("Choose a PDF or DOCX file first.");
      return;
    }

    const paid = orders.find((o) => o.status === "paid");

    if (!paid && !devPaymentBypass) {
      setError("Complete and verify a package payment before uploading.");
      return;
    }

    setBusy(true);

    try {
      const form = new FormData();

      form.append("file", file);

      // Only attach an order ID when a paid order actually exists.
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

      setMessage(
        `Resume #${result.id} accepted. Current status: ${result.status}.`,
      );

      setFile(null);
      await refresh();
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
      await refresh();
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Could not load resume.",
      );
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
      setError(
        e instanceof Error
          ? e.message
          : "Could not request revision.",
      );
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

      setMessage(
        "Thank you. Your testimonial is awaiting admin approval.",
      );
      setTestimonialText("");
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : "Could not submit testimonial.",
      );
    }
  }

  async function logout() {
    await api("/auth/logout", { method: "POST" });
    setUser(null);
    window.location.href = "/";
  }

  const paidOrder = orders.find((o) => o.status === "paid");

  return (
    <main className="mx-auto min-h-[78vh] max-w-7xl px-5 py-10 md:px-8 md:py-14">
      <div className="mb-10 flex flex-col justify-between gap-4 md:flex-row md:items-end">
        <div>
          <p className="section-kicker">Your workspace</p>
          <h1 className="mt-3 text-3xl font-semibold tracking-tight sm:text-4xl">
            Resume intelligence,{" "}
            <span className="gradient-text">in progress.</span>
          </h1>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-400">
            Choose your package, verify payment, upload a resume, then follow
            the actual backend job status.
          </p>
        </div>

        {user ? (
          <div className="flex items-center gap-3 rounded-full border border-white/10 bg-white/[.03] px-4 py-2">
            <span className="h-2 w-2 rounded-full bg-cyan-300" />
            <span className="max-w-52 truncate text-sm">{user.email}</span>
            <button
              onClick={logout}
              className="text-xs text-slate-400 hover:text-white"
            >
              Sign out
            </button>
          </div>
        ) : (
          <Link href="/login" className="button-primary self-start">
            <LogIn size={16} /> Sign in to continue
          </Link>
        )}
      </div>

      {!authChecked ? (
        <div className="glass rounded-2xl p-6 text-slate-400">
          Checking your session…
        </div>
      ) : !user ? (
        <div className="glass rounded-2xl p-8">
          <h2 className="text-xl font-semibold">
            Sign in to access your workspace
          </h2>
          <p className="mt-2 text-sm text-slate-400">
            Your resumes and orders are private to your account.
          </p>
          <Link href="/login" className="button-primary mt-5">
            Continue to sign in <ArrowRight size={16} />
          </Link>
        </div>
      ) : (
        <>
          <div className="grid gap-6 lg:grid-cols-[1.05fr_.95fr]">
            <section className="glass rounded-2xl p-6 md:p-7">
              <div className="flex items-center justify-between">
                <div>
                  <p className="section-kicker">01 / Package</p>
                  <h2 className="mt-2 text-xl font-semibold">
                    Choose your outcome
                  </h2>
                </div>
                <span className="pill">Server-priced</span>
              </div>

              <div className="mt-5 grid gap-3 sm:grid-cols-2">
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
                      <span className="font-medium">{p.name}</span>
                      <span className="text-lg font-semibold">
                        ₹{p.price_inr ?? p.price}
                      </span>
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
                Pay securely with Razorpay
              </button>

              <p className="mt-3 text-xs leading-5 text-slate-500">
                Checkout requires valid server credentials. The app never
                marks payment successful based only on a browser event.
              </p>
            </section>

            <section className="glass rounded-2xl p-6 md:p-7">
              <div className="flex items-center justify-between">
                <div>
                  <p className="section-kicker">02 / Upload</p>
                  <h2 className="mt-2 text-xl font-semibold">
                    Prepare your analysis
                  </h2>
                </div>
                <UploadCloud className="text-cyan-200" />
              </div>

              <label className="mt-5 flex min-h-36 cursor-pointer flex-col items-center justify-center rounded-xl border border-dashed border-violet-300/30 bg-violet-300/[.035] px-5 text-center transition hover:bg-violet-300/[.07]">
                <UploadCloud size={24} className="text-violet-200" />
                <span className="mt-3 text-sm font-medium">
                  {file ? file.name : "Choose PDF or DOCX"}
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

              <div className="mt-4 grid gap-4 sm:grid-cols-2">
                <div>
                  <label className="mb-2 block text-xs text-slate-400">
                    Target role
                  </label>
                  <select
                    className="field"
                    value={role}
                    onChange={(e) => setRole(e.target.value)}
                  >
                    {[
                      ["sde-general", "General SDE"],
                      ["backend", "Backend"],
                      ["frontend", "Frontend"],
                      ["fullstack", "Full-stack"],
                      ["ai-ml", "AI / ML"],
                      ["data-analyst", "Data Analyst"],
                      ["cloud-devops", "Cloud / DevOps"],
                      ["mobile", "Mobile"],
                      ["cybersecurity", "Cybersecurity"],
                    ].map(([v, l]) => (
                      <option value={v} key={v}>
                        {l}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="mb-2 block text-xs text-slate-400">
                    Resume template
                  </label>
                  <select
                    className="field"
                    value={templateId}
                    onChange={(e) => {
                      setTemplateId(e.target.value);
                      setMarginIn(
                        e.target.value === "lpu-standard" ||
                          e.target.value === "modern-one-page"
                          ? 0.38
                          : 0.55,
                      );
                      setBodySize(e.target.value === "ats-clean" ? 9.5 : 8.5);
                    }}
                  >
                    {(templates.length
                      ? templates
                      : [{ template_id: "ats-clean", display_name: "ATS Clean" }]
                    ).map((t) => (
                      <option value={t.template_id} key={t.template_id}>
                        {t.display_name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="mt-4 rounded-xl border border-white/10 bg-[#f6f7fb] p-4 text-slate-800">
                <div className="flex items-center justify-between gap-3 border-b border-slate-300 pb-2">
                  <div>
                    <p
                      className="font-semibold"
                      style={{ fontFamily, fontSize: "15pt" }}
                    >
                      Your Name
                    </p>
                    <p className="mt-1 text-[10px] text-slate-500">
                      email · phone · LinkedIn · GitHub
                    </p>
                  </div>
                  <span className="rounded-full bg-indigo-100 px-2 py-1 text-[9px] font-semibold text-indigo-700">
                    {templateId}
                  </span>
                </div>

                <div
                  className="mt-3 grid gap-3 sm:grid-cols-[1fr_1fr]"
                  style={{ padding: `${Math.max(2, marginIn * 8)}px` }}
                >
                  <div>
                    <p className="text-[10px] font-bold tracking-wider text-indigo-700">
                      EXPERIENCE
                    </p>
                    <div className="mt-2 h-1.5 w-full rounded bg-slate-300" />
                    <div className="mt-1.5 h-1.5 w-5/6 rounded bg-slate-300" />
                    <div className="mt-1.5 h-1.5 w-4/6 rounded bg-slate-300" />
                  </div>
                  <div>
                    <p className="text-[10px] font-bold tracking-wider text-indigo-700">
                      PROJECTS
                    </p>
                    <div className="mt-2 h-1.5 w-full rounded bg-slate-300" />
                    <div className="mt-1.5 h-1.5 w-5/6 rounded bg-slate-300" />
                    <div className="mt-1.5 h-1.5 w-3/5 rounded bg-slate-300" />
                  </div>
                </div>

                <p className="mt-2 text-[10px] text-slate-500">
                  Approximate live preview; final pagination and PDF rendering
                  may differ.
                </p>
              </div>

              <div className="mt-4 grid gap-4 sm:grid-cols-3">
                <div>
                  <label className="mb-2 block text-xs text-slate-400">
                    Font family
                  </label>
                  <select
                    className="field"
                    value={fontFamily}
                    onChange={(e) => setFontFamily(e.target.value)}
                  >
                    <option>Arial</option>
                    <option>Calibri</option>
                    <option>Georgia</option>
                  </select>
                </div>

                <div>
                  <label className="mb-2 block text-xs text-slate-400">
                    Body size: {bodySize.toFixed(1)} pt
                  </label>
                  <input
                    type="range"
                    min="7.5"
                    max="11"
                    step="0.5"
                    value={bodySize}
                    onChange={(e) => setBodySize(Number(e.target.value))}
                    className="w-full accent-violet-400"
                  />
                </div>

                <div>
                  <label className="mb-2 block text-xs text-slate-400">
                    Page margins
                  </label>
                  <select
                    className="field"
                    value={marginIn}
                    onChange={(e) => setMarginIn(Number(e.target.value))}
                  >
                    <option value={0.35}>Compact · 0.35 in</option>
                    <option value={0.55}>Standard · 0.55 in</option>
                    <option value={0.7}>Roomy · 0.70 in</option>
                  </select>
                </div>
              </div>

              {/* UPDATED: allow uploads without payment only in development. */}
              <button
                onClick={upload}
                disabled={
                  busy || (!paidOrder && !devPaymentBypass) || !file
                }
                className="button-primary mt-5 w-full disabled:cursor-not-allowed disabled:opacity-40"
              >
                {busy ? "Working…" : "Upload and start analysis"}
                <ArrowRight size={16} />
              </button>

              {!paidOrder && !devPaymentBypass && (
                <p className="mt-3 text-xs text-amber-200/80">
                  A verified paid order is required before upload.
                </p>
              )}

              {!paidOrder && devPaymentBypass && (
                <p className="mt-3 text-xs text-cyan-200/80">
                  Development mode: payment check is bypassed for local
                  testing only.
                </p>
              )}
            </section>
          </div>

          <div className="mt-6 grid gap-6 lg:grid-cols-[.85fr_1.15fr]">
            <section className="glass rounded-2xl p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="section-kicker">Privacy controls</p>
                  <h2 className="mt-2 text-lg font-semibold">
                    Your data, your choice
                  </h2>
                </div>
                <ShieldCheck className="text-cyan-200" />
              </div>

              <p className="mt-3 text-sm leading-6 text-slate-400">
                Resume files are private, retention is configurable, and AI
                processing uses Google Gemini. Export or delete account data
                from these controls.
              </p>

              <div className="mt-5 flex flex-wrap gap-3">
                <a
                  href={`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/account/export`}
                  className="button-secondary text-sm"
                  target="_blank"
                  rel="noreferrer"
                >
                  Export account data <Download size={14} />
                </a>

                <button
                  onClick={async () => {
                    if (
                      confirm(
                        "Delete your ResumeIQ AI account data? This action cannot be undone.",
                      )
                    ) {
                      try {
                        await api("/account", { method: "DELETE" });
                        await api("/auth/logout", { method: "POST" });
                        window.location.href = "/";
                      } catch (e) {
                        setError(
                          e instanceof Error
                            ? e.message
                            : "Deletion failed",
                        );
                      }
                    }
                  }}
                  className="rounded-full border border-red-300/20 px-4 py-2 text-sm text-red-200 hover:bg-red-300/10"
                >
                  Delete account
                </button>
              </div>
            </section>

            <section className="glass rounded-2xl p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="section-kicker">03 / History</p>
                  <h2 className="mt-2 text-lg font-semibold">
                    Your resume jobs
                  </h2>
                </div>
                <button
                  onClick={refresh}
                  className="button-secondary px-3 py-2"
                  aria-label="Refresh jobs"
                >
                  <RefreshCw size={15} />
                </button>
              </div>

              {resumes.length === 0 ? (
                <div className="mt-5 rounded-xl border border-dashed border-white/10 p-7 text-center">
                  <FileText size={24} className="mx-auto text-slate-500" />
                  <p className="mt-3 text-sm font-medium">
                    No resume jobs yet
                  </p>
                  <p className="mt-1 text-xs text-slate-500">
                    Once you upload, processing status will appear here.
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
                          <p className="truncate text-sm font-medium">
                            {r.filename}
                          </p>
                          <p className="mt-1 text-xs text-slate-500">
                            {r.target_role} · {r.template_id} · #{r.id}
                          </p>
                        </div>
                      </div>

                      <div className="flex items-center gap-2">
                        <span
                          className={`rounded-full px-2.5 py-1 text-xs ${
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
                          className="button-secondary px-3 py-2 text-xs"
                        >
                          View
                        </button>
                        {r.status === "failed" && (
                          <button
                            onClick={() => retry(r.id)}
                            className="button-secondary px-3 py-2 text-xs"
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
          </div>

          <section className="glass mt-6 rounded-2xl p-6">
            <p className="section-kicker">Feedback</p>
            <h2 className="mt-2 text-lg font-semibold">
              Share your experience
            </h2>
            <p className="mt-1 text-sm text-slate-400">
              Testimonials are reviewed by an administrator before they appear
              publicly.
            </p>

            <div className="mt-4 grid gap-3 md:grid-cols-[220px_1fr]">
              <input
                className="field"
                value={testimonialName}
                onChange={(e) => setTestimonialName(e.target.value)}
                maxLength={100}
                placeholder="Display name (optional)"
              />
              <textarea
                className="field min-h-20"
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
              <span>
                I consent to displaying this testimonial publicly if an
                administrator approves it.
              </span>
            </label>

            <button
              className="button-secondary mt-3"
              disabled={
                testimonialText.trim().length < 20 || !testimonialConsent
              }
              onClick={submitTestimonial}
            >
              Submit testimonial <ArrowRight size={15} />
            </button>
          </section>

          {activeResume && (
            <section className="glass mt-6 rounded-2xl p-6 md:p-8">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="section-kicker">
                    Resume #{activeResume.id}
                  </p>
                  <h2 className="mt-2 text-xl font-semibold">
                    Analysis results
                  </h2>
                  <p className="mt-2 text-sm text-slate-400">
                    Status: {activeResume.status}
                  </p>
                </div>
                <button
                  onClick={() => setActiveResume(null)}
                  className="button-secondary"
                >
                  Close
                </button>
              </div>

              {activeResume.status === "failed" && (
                <p className="mt-5 flex gap-2 rounded-xl bg-red-300/[.07] p-4 text-sm text-red-200">
                  <AlertCircle size={18} />
                  {activeResume.error || "Processing failed."}
                </p>
              )}

              {activeResume.status !== "completed" &&
                activeResume.status !== "failed" && (
                  <p className="mt-5 flex gap-2 rounded-xl bg-violet-300/[.06] p-4 text-sm text-violet-100">
                    <LoaderCircle size={18} className="animate-spin" />
                    The backend reports this job is still processing. Refresh
                    shortly for updates.
                  </p>
                )}

              {activeResume.review && (
                <>
                  <div className="mt-6 grid gap-5 md:grid-cols-[160px_1fr]">
                    <div className="flex flex-col items-center justify-center rounded-2xl border border-violet-300/20 bg-violet-300/[.06] p-5">
                      <span className="text-4xl font-semibold">
                        {activeResume.review.role_fit_score}
                        <span className="text-base text-slate-500">
                          /100
                        </span>
                      </span>
                      <span className="mt-2 text-center text-xs text-slate-400">
                        Advisory role-fit score
                      </span>
                    </div>

                    <div>
                      <h3 className="font-semibold">Priority fixes</h3>
                      <ol className="mt-3 list-decimal space-y-2 pl-5 text-sm leading-6 text-slate-300">
                        {activeResume.review.priority_fixes.map(
                          (x: string, i: number) => (
                            <li key={i}>{x}</li>
                          ),
                        )}
                      </ol>
                    </div>
                  </div>

                  <div className="mt-6 grid gap-4 md:grid-cols-2">
                    <div className="rounded-xl border border-white/10 p-4">
                      <h3 className="font-semibold">ATS findings</h3>
                      <div className="mt-3 space-y-3">
                        {activeResume.review.ats_findings.map(
                          (x: any, i: number) => (
                            <div
                              key={i}
                              className="border-l-2 border-violet-300/50 pl-3"
                            >
                              <p className="text-sm font-medium">
                                {x.issue}
                              </p>
                              <p className="mt-1 text-xs leading-5 text-slate-400">
                                {x.recommendation}
                              </p>
                            </div>
                          ),
                        )}
                      </div>
                    </div>

                    <div className="rounded-xl border border-white/10 p-4">
                      <h3 className="font-semibold">
                        Missing role keywords
                      </h3>
                      <div className="mt-3 flex flex-wrap gap-2">
                        {activeResume.review.missing_keywords.map(
                          (x: string) => (
                            <span key={x} className="pill">
                              {x}
                            </span>
                          ),
                        )}
                      </div>
                      <p className="mt-5 text-xs leading-5 text-slate-500">
                        {activeResume.review.advisory_note}
                      </p>
                    </div>
                  </div>

                  <div className="mt-6">
                    <h3 className="font-semibold">
                      Before / after suggestions
                    </h3>
                    <div className="mt-3 space-y-3">
                      {activeResume.review.bullet_rewrites.map(
                        (b: any, i: number) => (
                          <div
                            key={i}
                            className="grid gap-3 rounded-xl border border-white/10 p-4 md:grid-cols-2"
                          >
                            <div>
                              <p className="mb-2 text-xs uppercase tracking-wider text-slate-500">
                                Original
                              </p>
                              <p className="text-sm leading-6 text-slate-300">
                                {b.original}
                              </p>
                            </div>
                            <div>
                              <p className="mb-2 text-xs uppercase tracking-wider text-cyan-200">
                                Suggested
                              </p>
                              <p className="text-sm leading-6 text-slate-200">
                                {b.rewritten}
                              </p>
                              {b.needs_input && (
                                <p className="mt-2 text-xs text-amber-200">
                                  Needs input: {b.question}
                                </p>
                              )}
                            </div>
                          </div>
                        ),
                      )}
                    </div>
                  </div>

                  {activeResume.review.linkedin && (
                    <div className="mt-6 rounded-xl border border-violet-300/20 p-5">
                      <h3 className="font-semibold">
                        LinkedIn optimization
                      </h3>
                      <p className="mt-3 text-sm text-slate-400">
                        {activeResume.review.linkedin.about_rewrite}
                      </p>
                      <div className="mt-3 flex flex-wrap gap-2">
                        {activeResume.review.linkedin.headlines.map(
                          (x: string) => (
                            <span key={x} className="pill">
                              {x}
                            </span>
                          ),
                        )}
                      </div>
                    </div>
                  )}
                </>
              )}

              {activeResume.voice_note_url && (
                <div className="mt-5">
                  <a
                    href={activeResume.voice_note_url}
                    target="_blank"
                    rel="noreferrer"
                    className="button-secondary"
                  >
                    Open admin voice-note link <ArrowRight size={15} />
                  </a>
                </div>
              )}

              {activeResume.package_id === "full-makeover" && (
                <div className="mt-6 rounded-xl border border-violet-300/20 p-4">
                  <h3 className="font-semibold">Included revision round</h3>
                  <p className="mt-1 text-xs text-slate-400">
                    Describe the corrections you want the reviewer to consider.
                  </p>
                  <textarea
                    className="field mt-3 min-h-24"
                    value={revisionNotes}
                    onChange={(e) => setRevisionNotes(e.target.value)}
                    placeholder="Tell us what needs adjusting…"
                  />
                  <button
                    className="button-primary mt-3"
                    disabled={revisionNotes.trim().length < 5}
                    onClick={() => requestRevision(activeResume.id)}
                  >
                    Request revision <ArrowRight size={15} />
                  </button>
                </div>
              )}

              <div className="mt-5">
                <a
                  href={`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/resumes/${activeResume.id}/original/download`}
                  target="_blank"
                  rel="noreferrer"
                  className="button-secondary"
                >
                  <Download size={15} /> Download original resume
                </a>
              </div>

              {activeResume.outputs?.length > 0 && (
                <div className="mt-6 flex flex-wrap gap-3">
                  {activeResume.outputs.map((o: any) => (
                    <a
                      key={o.id}
                      href={`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}${o.download_url}`}
                      target="_blank"
                      rel="noreferrer"
                      className="button-primary"
                    >
                      <Download size={16} /> Download {o.kind.toUpperCase()}
                    </a>
                  ))}
                </div>
              )}
            </section>
          )}
        </>
      )}

      {message && (
        <p
          role="status"
          className="mt-5 flex gap-2 rounded-xl border border-cyan-300/20 bg-cyan-300/[.05] p-4 text-sm text-cyan-100"
        >
          <CheckCircle2 size={18} />
          {message}
        </p>
      )}

      {error && (
        <p
          role="alert"
          className="mt-5 flex gap-2 rounded-xl border border-red-300/20 bg-red-300/[.06] p-4 text-sm text-red-100"
        >
          <AlertCircle size={18} />
          {error}
        </p>
      )}

      <p className="mt-8 flex items-center gap-2 text-xs leading-5 text-slate-600">
        <Settings2 size={14} />
        Analysis requires configured Gemini credentials; document downloads
        require the relevant paid package entitlement.
      </p>
    </main>
  );
}