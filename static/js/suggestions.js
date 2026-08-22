import {$,api,state,esc,payload,toast,showError} from './api.js?v=5.2.0';

const ACTIVE_SUGGESTION_KEY='brcom-active-suggestion';
let activeSuggestion=null;
let openingChat=null;

function messageLabel(type){
  return type==='USUARIO'?'Você':type==='IA'?'Assistente IA':'Administração';
}

function scrollChatToEnd(){
  const messages=$('suggestionMessages');
  messages.scrollTop=messages.scrollHeight;
}

function renderMessages(item,{completed=false}={}){
  const messages=item?.mensagens||[];
  const welcome='<article class="suggestion-message ia"><span class="message-avatar"><i class="fa-solid fa-wand-magic-sparkles"></i></span><div><b>Assistente IA</b><p>Olá! Conte a sua ideia de melhoria. Vou fazer perguntas curtas para entender o problema, o resultado esperado e os detalhes importantes.</p></div></article>';
  const conversation=messages.map(message=>`<article class="suggestion-message ${message.autor_tipo.toLowerCase()}"><span class="message-avatar"><i class="fa-solid ${message.autor_tipo==='USUARIO'?'fa-user':message.autor_tipo==='IA'?'fa-wand-magic-sparkles':'fa-user-shield'}"></i></span><div><b>${messageLabel(message.autor_tipo)}</b><p>${esc(message.conteudo)}</p></div></article>`).join('');
  const confirmation=completed?`<article class="suggestion-message system"><span class="message-avatar"><i class="fa-solid fa-circle-check"></i></span><div><b>Sugestão enviada</b><p>Protocolo <strong>${esc(item.numero)}</strong> criado. Você poderá acompanhar o andamento na página Sugestões.</p></div></article>`:'';
  $('suggestionMessages').innerHTML=(messages.length?conversation:welcome)+confirmation;
  requestAnimationFrame(scrollChatToEnd);
}

function setChatStatus(message='',type='info'){
  const status=$('suggestionChatStatus');
  status.textContent=message;
  status.className=`suggestion-chat-status ${message?'':'hidden'} ${type}`;
}

function setChatBusy(busy){
  $('suggestionTyping').classList.toggle('hidden',!busy);
  $('suggestionMessage').disabled=busy;
  $('suggestionMessageForm').querySelector('button').disabled=busy;
  if(busy)requestAnimationFrame(scrollChatToEnd);
}

function resetReview(){
  $('suggestionConfirmForm').reset();
  $('suggestionConfirmForm').classList.add('hidden');
}

function fillReview(result){
  if(result.title)$('suggestionTitle').value=result.title;
  if(result.module)$('suggestionModule').value=result.module;
  if(result.summary){
    $('suggestionSummary').value=result.summary;
    $('suggestionDescription').value=result.summary;
  }
  if(result.ready||($('suggestionTitle').value&&$('suggestionModule').value&&$('suggestionSummary').value)){
    $('suggestionConfirmForm').classList.remove('hidden');
    requestAnimationFrame(scrollChatToEnd);
  }
}

function prepareActiveSuggestion(item){
  activeSuggestion=item;
  localStorage.setItem(ACTIVE_SUGGESTION_KEY,String(item.id));
  $('suggestionMessageForm').classList.remove('hidden');
  resetReview();
  renderMessages(item);
  if(item.titulo||item.modulo||item.resumo_ia){
    fillReview({ready:Boolean(item.titulo&&item.modulo&&item.resumo_ia),title:item.titulo,module:item.modulo,summary:item.resumo_ia});
  }
}

async function resumeOrCreateSuggestion(forceNew=false){
  setChatStatus(forceNew?'Iniciando uma nova conversa...':'Preparando sua conversa...');
  if(!forceNew){
    const storedId=Number(localStorage.getItem(ACTIVE_SUGGESTION_KEY));
    if(storedId){
      try{
        const stored=await api(`/sugestoes/${storedId}`);
        if(stored.status==='COLETANDO_IDEIA'&&stored.usuario_id===state.user.id){
          prepareActiveSuggestion(stored);
          setChatStatus();
          return;
        }
      }catch(_){localStorage.removeItem(ACTIVE_SUGGESTION_KEY)}
    }
    const drafts=await api(`/sugestoes/?status=COLETANDO_IDEIA&usuario_id=${state.user.id}`);
    if(drafts.length){
      prepareActiveSuggestion(drafts[0]);
      setChatStatus();
      return;
    }
  }
  const created=await api('/sugestoes/',{method:'POST'});
  prepareActiveSuggestion(created);
  setChatStatus();
}

function minimizeChat(minimized=true){
  const chat=$('suggestionChat');
  chat.classList.toggle('minimized',minimized);
  $('suggestionChatMinimize').setAttribute('aria-label',minimized?'Expandir assistente':'Minimizar assistente');
  $('suggestionChatMinimize').title=minimized?'Expandir':'Minimizar';
  $('suggestionChatMinimize').querySelector('i').className=`fa-solid ${minimized?'fa-up-right-and-down-left-from-center':'fa-minus'}`;
}

export async function openSuggestionChat({forceNew=false}={}){
  if(!state.user?.pode_enviar_sugestoes){
    toast('Seu usuário não possui permissão para enviar sugestões.',true);
    return;
  }
  $('suggestionChat').classList.remove('hidden');
  minimizeChat(false);
  $('suggestionMessage').focus();
  if(forceNew||!activeSuggestion){
    if(openingChat)return openingChat;
    openingChat=resumeOrCreateSuggestion(forceNew).catch(error=>{
      setChatStatus(error.message||'Não foi possível iniciar a conversa.','error');
      showError(error);
    }).finally(()=>{openingChat=null});
    return openingChat;
  }
  renderMessages(activeSuggestion);
}

export async function loadSuggestions(){
  const params=new URLSearchParams();
  [['status','suggestionFilterStatus'],['modulo','suggestionFilterModule'],['prioridade','suggestionFilterPriority']].forEach(([key,id])=>{if($(id).value)params.set(key,$(id).value)});
  const list=await api(`/sugestoes/?${params}`);
  const admin=state.user.pode_administrar_sugestoes||['DONO','DESENVOLVEDOR'].includes(state.user.tipo_usuario);
  $('suggestionList').innerHTML=list.map(s=>`<details class="suggestion-card"><summary><b>${esc(s.numero||'Rascunho')} — ${esc(s.titulo||'Ideia em elaboração')}</b><span class="badge">${esc(s.status.replaceAll('_',' '))}</span><small>${esc(s.modulo||'Módulo a definir')} · prioridade ${esc(s.prioridade)} · ${new Date(s.atualizado_em).toLocaleString('pt-BR')}</small></summary><div class="suggestion-detail"><div class="calendar-view-switch"><button type="button" class="btn-secondary" data-suggestion-view="summary">Resumo da IA</button><button type="button" class="btn-secondary" data-suggestion-view="chat">Conversa completa</button></div><div data-suggestion-summary><p>${esc(s.resumo_ia||s.descricao||'Sem resumo.')}</p></div><div data-suggestion-chat class="hidden">${s.mensagens.map(m=>`<p><b>${esc(messageLabel(m.autor_tipo))}:</b> ${esc(m.conteudo)}</p>`).join('')}</div>${s.resposta_administrativa?`<p><b>Resposta administrativa:</b> ${esc(s.resposta_administrativa)}</p>`:''}${admin&&s.status!=='COLETANDO_IDEIA'?`<form data-admin-suggestion="${s.id}" class="form-grid"><label>Status<select name="status">${['EM_ANALISE','AGUARDANDO_INFORMACAO','APROVADA','EM_ATENDIMENTO','IMPLEMENTADA','RESPONDIDA','FINALIZADA','RECUSADA','ARQUIVADA'].map(v=>`<option ${v===s.status?'selected':''}>${v}</option>`).join('')}</select></label><label>Prioridade<select name="priority">${['BAIXA','NORMAL','ALTA','URGENTE'].map(v=>`<option ${v===s.prioridade?'selected':''}>${v}</option>`).join('')}</select></label><label class="col-span-full">Resposta<textarea name="response"></textarea></label><div class="form-actions"><button class="btn-primary">Atualizar</button></div></form>`:''}</div></details>`).join('')||'<p class="help-text">Nenhuma sugestão registrada.</p>';
}

export async function loadNotifications(){
  const list=await api('/notificacoes/');
  $('notificationList').innerHTML=list.map(n=>`<button class="list-card notification-item ${n.lida_em?'':'unread'}" data-notification="${n.id}"><div><b>${esc(n.titulo)}</b><p>${esc(n.mensagem)}</p><small>${new Date(n.criado_em).toLocaleString('pt-BR')}</small></div></button>`).join('')||'<p class="help-text">Nenhuma notificação.</p>';
  await refreshNotificationBadge();
}

export async function refreshNotificationBadge(){
  const result=await api('/notificacoes/nao-lidas');
  const badge=$('notificationBadge');
  badge.textContent=result.quantidade;
  badge.classList.toggle('hidden',!result.quantidade);
}

export function initSuggestions(){
  document.querySelectorAll('[data-open-suggestion-chat]').forEach(button=>button.addEventListener('click',()=>openSuggestionChat()));
  $('suggestionChatNew').addEventListener('click',()=>openSuggestionChat({forceNew:true}));
  $('suggestionChatMinimize').addEventListener('click',()=>minimizeChat(!$('suggestionChat').classList.contains('minimized')));
  $('suggestionChatExpand').addEventListener('click',()=>{if($('suggestionChat').classList.contains('minimized'))minimizeChat(false)});
  $('suggestionMessage').addEventListener('keydown',event=>{
    if(event.key==='Enter'&&!event.shiftKey&&!event.isComposing){event.preventDefault();$('suggestionMessageForm').requestSubmit()}
  });
  $('suggestionMessageForm').addEventListener('submit',async event=>{
    event.preventDefault();
    const text=$('suggestionMessage').value.trim();
    if(!text)return;
    if(!activeSuggestion)await openSuggestionChat();
    if(!activeSuggestion)return;
    setChatBusy(true);
    setChatStatus();
    try{
      const result=await api(`/sugestoes/${activeSuggestion.id}/mensagens`,payload({conteudo:text}));
      $('suggestionMessage').value='';
      activeSuggestion=await api(`/sugestoes/${activeSuggestion.id}`);
      renderMessages(activeSuggestion);
      fillReview(result);
      if(!result.ai_available)setChatStatus(result.message,'error');
    }catch(error){
      setChatStatus(error.message||'A mensagem não pôde ser enviada.','error');
      showError(error);
    }finally{
      setChatBusy(false);
      $('suggestionMessage').focus();
    }
  });
  $('suggestionConfirmForm').addEventListener('submit',async event=>{
    event.preventDefault();
    if(!activeSuggestion)return;
    const submitButton=event.currentTarget.querySelector('button[type="submit"]');
    submitButton.disabled=true;
    try{
      const sent=await api(`/sugestoes/${activeSuggestion.id}/confirmar`,payload({titulo:$('suggestionTitle').value,modulo:$('suggestionModule').value,descricao:$('suggestionDescription').value,resumo_ia:$('suggestionSummary').value}));
      activeSuggestion=sent;
      localStorage.removeItem(ACTIVE_SUGGESTION_KEY);
      renderMessages(sent,{completed:true});
      $('suggestionConfirmForm').classList.add('hidden');
      $('suggestionMessageForm').classList.add('hidden');
      setChatStatus('Enviada com sucesso. Use o botão + para iniciar outra ideia.','success');
      toast(`Sugestão ${sent.numero} enviada com sucesso`);
      if(!$('sugestoesTab').classList.contains('hidden'))await loadSuggestions();
      activeSuggestion=null;
    }catch(error){
      setChatStatus(error.message||'Não foi possível confirmar a sugestão.','error');
      showError(error);
    }finally{submitButton.disabled=false}
  });
  $('notificationList').addEventListener('click',async event=>{const item=event.target.closest('[data-notification]');if(item){await api(`/notificacoes/${item.dataset.notification}/ler`,{method:'POST'});await loadNotifications()}});
  $('readAllNotifications').addEventListener('click',async()=>{await api('/notificacoes/ler-todas',{method:'POST'});await loadNotifications()});
  $('suggestionFilters').addEventListener('submit',event=>{event.preventDefault();loadSuggestions().catch(showError)});
  $('suggestionList').addEventListener('click',event=>{const view=event.target.closest('[data-suggestion-view]');if(view){const detail=view.closest('.suggestion-detail');detail.querySelector('[data-suggestion-summary]').classList.toggle('hidden',view.dataset.suggestionView!=='summary');detail.querySelector('[data-suggestion-chat]').classList.toggle('hidden',view.dataset.suggestionView!=='chat')}});
  $('suggestionList').addEventListener('submit',async event=>{const form=event.target.closest('[data-admin-suggestion]');if(!form)return;event.preventDefault();try{await api(`/sugestoes/${form.dataset.adminSuggestion}`,{method:'PATCH',body:JSON.stringify({status:form.elements.status.value,prioridade:form.elements.priority.value,resposta:form.elements.response.value||null})});toast('Sugestão atualizada e autor notificado');await loadSuggestions()}catch(error){showError(error)}});
}
