export const state = {user:null, products:[], clients:[], formulas:[], quotes:[], serviceOrders:[]};
export const $ = id => document.getElementById(id);
export const esc = value => String(value ?? "").replace(/[&<>'"]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
export const money = value => Number(value || 0).toLocaleString('pt-BR',{style:'currency',currency:'BRL'});
export const qty = value => Number(value || 0).toLocaleString('pt-BR',{maximumFractionDigits:4});
export const date = value => value ? (String(value).length===10?String(value).split('-').reverse().join('/'):new Date(value).toLocaleDateString('pt-BR')) : '—';
export const datetimeLocal = value => value ? new Date(value).toISOString().slice(0,16) : '';

export function toast(message, error=false){const el=$('toast');el.textContent=message;el.className=`toast ${error?'error':''}`;setTimeout(()=>el.classList.add('hidden'),4200)}
export async function api(url, options={}){
  const isForm=typeof FormData!=='undefined'&&options.body instanceof FormData;
  const response=await fetch(url,{credentials:'same-origin',...options,headers:{...(options.body&&!isForm?{'Content-Type':'application/json'}:{}),...(options.headers||{})}});
  if(response.status===401){if(!['/api/me','/api/login'].includes(url))location.reload();throw new Error('Sessão expirada')}
  const contentType=response.headers.get('content-type')||'';
  const body=contentType.includes('json')?await response.json():await response.text();
  if(!response.ok)throw new Error(typeof body==='object'?body.detail||'Não foi possível concluir':body);
  return body;
}
export const payload = data => ({method:'POST',body:JSON.stringify(data)});
export function optionList(items,label='nome'){return items.map(item=>`<option value="${item.id}">${esc(typeof label==='function'?label(item):item[label])}</option>`).join('')}
export function showError(error){toast(error.message||String(error),true)}
export function criticalConfirmation(title,warning){return new Promise(resolve=>{const dialog=$('criticalActionDialog'),form=$('criticalActionForm');$('criticalActionTitle').textContent=title;$('criticalActionWarning').textContent=warning;form.reset();const finish=value=>{form.onsubmit=null;$('criticalActionCancel').onclick=null;dialog.close();resolve(value)};form.onsubmit=e=>{e.preventDefault();finish({senha:$('criticalActionPassword').value,motivo:$('criticalActionReason').value})};$('criticalActionCancel').onclick=()=>finish(null);dialog.showModal()})}
