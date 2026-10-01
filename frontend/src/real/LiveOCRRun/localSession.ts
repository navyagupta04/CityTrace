let token='';
export const getOCRToken=()=>token;
export const clearOCRToken=()=>{token='';};
export async function loginOCRService(username:string,password:string){const env=(import.meta as ImportMeta & {env:Record<string,string>}).env,base=(env.VITE_OCR_API_BASE||env.VITE_API_BASE_URL||'/api').replace(/\/$/,'');const response=await fetch(`${base}/auth/login`,{method:'POST',credentials:'include',headers:{'Content-Type':'application/json'},body:JSON.stringify({username,password,unit:'Central District'})});const data=await response.json();if(!response.ok)throw Error(typeof data.detail==='string'?data.detail:'Sign-in failed');if(!['officer','admin'].includes(data.user.role))throw Error('Officer role required');token=data.access_token;}
