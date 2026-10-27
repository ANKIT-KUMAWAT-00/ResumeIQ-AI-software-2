import type { Config } from "tailwindcss";
const config: Config = { content:["./app/**/*.{js,ts,jsx,tsx,mdx}","./components/**/*.{js,ts,jsx,tsx,mdx}"], theme:{extend:{colors:{ink:{950:"#070913",900:"#0b1020",800:"#121a30"},accent:{violet:"#9b8cff",cyan:"#58e1ef"}},boxShadow:{glow:"0 0 70px rgba(124,93,255,.18)"},backgroundImage:{"hero-grid":"linear-gradient(rgba(255,255,255,.035) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.035) 1px,transparent 1px)"}}},plugins:[require('@tailwindcss/forms')]};
export default config;
