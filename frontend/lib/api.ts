const API=(process.env.NEXT_PUBLIC_API_URL||"http://localhost:8000").replace(/\/$/,"");
export class ApiError extends Error{status:number;constructor(message:string,status:number){super(message);this.status=status}}
export async function api<T=any>(path:string,init:RequestInit={}):Promise<T>{
 const headers=new Headers(init.headers||{});if(init.body && !(init.body instanceof FormData) && !headers.has("Content-Type"))headers.set("Content-Type","application/json");
 const res=await fetch(`${API}/api${path}`,{...init,headers,credentials:"include",cache:"no-store"});
 const raw=await res.text();let data:any={};try{data=raw?JSON.parse(raw):{}}catch{data={detail:raw}}
 if(!res.ok)throw new ApiError(data.detail||`Request failed (${res.status})`,res.status);return data as T;
}
export const packages=[{id:"resume-review",name:"Resume Review",price:299,desc:"Clarity on where your resume stands.",features:["Role-fit assessment","ATS compatibility findings","Line-by-line fixes","3 rewritten bullets"]},{id:"resume-template",name:"Resume + Template",price:499,desc:"A stronger resume, ready to send.",features:["Everything in Resume Review","Selected template rebuild","DOCX + PDF downloads"]},{id:"resume-linkedin",name:"Resume + LinkedIn + Template",price:799,desc:"Align your professional story.",features:["Everything above","LinkedIn headline options","About-section rewrite","Skills and keyword guidance"]},{id:"full-makeover",name:"Full Makeover",price:1199,desc:"Guided finishing support.",features:["Everything in LinkedIn package","One revision round","Admin-recorded voice-note link"]}];
