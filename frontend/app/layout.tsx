import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";
import { Navbar } from "@/components/navbar";
export const metadata: Metadata={title:"ResumeIQ AI — Build a Resume That Gets Noticed",description:"AI-powered resume intelligence, role-specific feedback, and professional resume templates."};
export default function RootLayout({children}:{children:ReactNode}){return <html lang="en"><body><Navbar/>{children}<footer className="border-t border-white/10 px-6 py-8"><div className="mx-auto flex max-w-7xl flex-col gap-4 text-sm text-slate-400 md:flex-row md:items-center md:justify-between"><div><span className="font-semibold text-white">ResumeIQ AI</span><span className="ml-3">Build a Resume That Gets Noticed.</span></div><div className="flex flex-wrap gap-5"><a href="/privacy" className="hover:text-white">Privacy</a><a href="/terms" className="hover:text-white">Terms</a><a href="/workspace" className="hover:text-white">Workspace</a><a href="/login" className="hover:text-white">Sign in</a></div><span>Advisory feedback. No hiring guarantees.</span></div></footer></body></html>}
