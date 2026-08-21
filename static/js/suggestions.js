import {$,api,state,esc,payload,toast,showError} from './api.js?v=6.0.0';

let activeSuggestion=null;

function renderMessages(item){
  $('suggestionMessages').innerHTML=(item?.mensagens||[]).map(m=>`<article class="suggestion-message ${m.autor_tipo.toLowerCase()}"><b>${m.autor_tipo==='USUARIO'?'Você':m.autor_tipo==='IA'?'Assistente':'Administração'}</b><p>${esc(m.conteudo)}</p></article>`).join('')||'<p class="help-text">Conte sua ideia. A assistente fará perguntas curtas para entender o problema e a melhoria esperada.</p>';
}

function fillReview(result){
  if(result.title)$('suggestionTitle').value=result.title;
  if(result.module)$('suggestionModule').value=result.module;
  if(result.summary){$('suggestionSummary').value=result.summary;$('suggestionDescription').value=result.summary;}
}

export async function loadSuggestions(){
  const params=new URLSearchParams();[['status','suggestionFilterStatus'],['modulo','suggestionFilterModule'],['prioridade','suggestionFilterPriority']].forEach(([key,id])=>{if($(id).value)params.set(key,$(id).value)});
  const list=await api(`/sugestoes/?${params}`),admin=state.user.pode_administrar_sugestoes||['DONO','DESENVOLVEDOR'].includes(state.user.tipo_usuario);
  $('suggestionList').innerHTML=list.map(s=>`<details class="suggestion-card"><summary><b>${esc(s.numero||'Rascunho')} — ${esc(s.titulo||'Ideia em elaboração')}</b><span class="badge">${esc(s.status.replaceAll('_',' '))}</span><small>${esc(s.modulo||'Módulo a definir')} · prioridade ${esc(s.prioridade)} · ${new Date(s.atualizado_em).toLocaleString('pt-BR')}</small></summary><div class="suggestion-detail"><div class="calendar-view-switch"><button type="button" class="btn-secondary" data-suggestion-view="summary">Resumo da IA</button><button type="button" class="btn-secondary" data-suggestion-view="chat">Conversa completa</button></div><div data-suggestion-summary><p>${esc(s.resumo_ia||s.descricao||'Sem resumo.')}</p></div><div data-suggestion-chat class="hidden">${s.mensagens.map(m=>`<p><b>${esc(m.autor_tipo)}:</b> ${esc(m.conteudo)}</p>`).join('')}</div>${s.resposta_administrativa?`<p><b>Resposta administrativa:</b> ${esc(s.resposta_administrativa)}</p>`:''}${admin&&s.status!=='COLETANDO_IDEIA'?`<form data-admin-suggestion="${s.id}" class="form-grid"><label>Status<select name="status">${['EM_ANALISE','AGUARDANDO_INFORMACAO','APROVADA','EM_ATENDIMENTO','IMPLEMENTADA','RESPONDIDA','FINALIZADA','RECUSADA','ARQUIVADA'].map(v=>`<option ${v===s.status?'selected':''}>${v}</option>`).join('')}</select></label><label>Prioridade<select name="priority">${['BAIXA','NORMAL','ALTA','URGENTE'].map(v=>`<option ${v===s.prioridade?'selected':''}>${v}</option>`).join('')}</select></label><label class="col-span-full">Resposta<textarea name="response"></textarea></label><div class="form-actions"><button class="btn-primary">Atualizar</button></div></form>`:''}</div></details>`).join('')||'<p class="help-text">Nenhuma sugestão registrada.</p>';
}

export async function loadNotifications(){
  const list=await api('/notificacoes/');
  $('notificationList').innerHTML=list.map(n=>`<button class="list-card notification-item ${n.lida_em?'':'unread'}" data-notification="${n.id}"><div><b>${esc(n.titulo)}</b><p>${esc(n.mensagem)}</p><small>${new Date(n.criado_em).toLocaleString('pt-BR')}</small></div></button>`).join('')||'<p class="help-text">Nenhuma notificação.</p>';
  await refreshNotificationBadge();
}

export async function refreshNotificationBadge(){
  const result=await api('/notificacoes/nao-lidas');
  const badge=$('notificationBadge');badge.textContent=result.quantidade;badge.classList.toggle('hidden',!result.quantidade);
}

export function initSuggestions(){
  $('newSuggestion').addEventListener('click',async()=>{try{activeSuggestion=await api('/sugestoes/',{method:'POST'});$('suggestionWorkspace').classList.remove('hidden');$('suggestionConfirmForm').reset();renderMessages(activeSuggestion)}catch(e){showError(e)}});
  $('suggestionMessageForm').addEventListener('submit',async e=>{e.preventDefault();if(!activeSuggestion)return;const text=$('suggestionMessage').value;try{const result=await api(`/sugestoes/${activeSuggestion.id}/mensagens`,payload({conteudo:text}));$('suggestionMessage').value='';activeSuggestion=await api(`/sugestoes/${activeSuggestion.id}`);renderMessages(activeSuggestion);fillReview(result);if(!result.ai_available)toast(result.message,true)}catch(err){showError(err)}});
  $('suggestionConfirmForm').addEventListener('submit',async e=>{e.preventDefault();if(!activeSuggestion)return;try{await api(`/sugestoes/${activeSuggestion.id}/confirmar`,payload({titulo:$('suggestionTitle').value,modulo:$('suggestionModule').value,descricao:$('suggestionDescription').value,resumo_ia:$('suggestionSummary').value}));toast('Sugestão enviada e protocolo gerado');activeSuggestion=null;$('suggestionWorkspace').classList.add('hidden');await loadSuggestions()}catch(err){showError(err)}});
  $('notificationList').addEventListener('click',async e=>{const item=e.target.closest('[data-notification]');if(item){await api(`/notificacoes/${item.dataset.notification}/ler`,{method:'POST'});await loadNotifications()}});
  $('readAllNotifications').addEventListener('click',async()=>{await api('/notificacoes/ler-todas',{method:'POST'});await loadNotifications()});
  $('suggestionFilters').addEventListener('submit',e=>{e.preventDefault();loadSuggestions().catch(showError)});
  $('suggestionList').addEventListener('click',e=>{const view=e.target.closest('[data-suggestion-view]');if(view){const detail=view.closest('.suggestion-detail');detail.querySelector('[data-suggestion-summary]').classList.toggle('hidden',view.dataset.suggestionView!=='summary');detail.querySelector('[data-suggestion-chat]').classList.toggle('hidden',view.dataset.suggestionView!=='chat')}});
  $('suggestionList').addEventListener('submit',async e=>{const form=e.target.closest('[data-admin-suggestion]');if(!form)return;e.preventDefault();try{await api(`/sugestoes/${form.dataset.adminSuggestion}`,{method:'PATCH',body:JSON.stringify({status:form.elements.status.value,prioridade:form.elements.priority.value,resposta:form.elements.response.value||null})});toast('Sugestão atualizada e autor notificado');await loadSuggestions()}catch(err){showError(err)}});
}
