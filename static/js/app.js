import {$,api,state,toast,showError} from './api.js?v=5.4.0';
import {initCatalog,loadProducts,loadFormulas} from './catalog.js?v=5.4.0';
import {initOperations,loadDashboard,loadQuotes,loadOrders,loadSales,loadReports} from './operations.js?v=5.4.0';
import {initAdministration,loadClients,loadAgenda,loadFutureOrders,loadDeliveredOrders,loadHistory,loadUsers} from './administration.js?v=5.4.0';
import {initEmployees,loadEmployees} from './employees.js?v=5.4.0';
import {initImports,loadImports} from './imports.js?v=5.4.0';
import {initSalesSheets,loadSalesSheet} from './sales-sheets.js?v=5.4.0';
import {initSuggestions,loadSuggestions,loadNotifications,refreshNotificationBadge} from './suggestions.js?v=5.4.0';

const loaders={dashboardTab:loadDashboard,produtosTab:loadProducts,estoqueTab:loadProducts,formulasTab:loadFormulas,orcamentosTab:loadQuotes,osTab:loadOrders,vendasTab:loadSales,importacoesTab:loadImports,planilhasVendasTab:loadSalesSheet,relatoriosTab:loadReports,clientesTab:loadClients,agendaTab:loadAgenda,pedidosTab:loadFutureOrders,entreguesTab:loadDeliveredOrders,historicoTab:async()=>{await loadProducts();return loadHistory()},sugestoesTab:loadSuggestions,notificacoesTab:loadNotifications,funcionariosTab:loadEmployees,usuariosTab:loadUsers};
const titles={dashboardTab:'Painel',produtosTab:'Produtos',estoqueTab:'Movimentar estoque',formulasTab:'Fórmulas',orcamentosTab:'Orçamentos',osTab:'Ordens de serviço',vendasTab:'Vendas',importacoesTab:'Importar planilhas',planilhasVendasTab:'Planilhas de Vendas',relatoriosTab:'Relatórios',clientesTab:'Clientes',agendaTab:'Agenda',pedidosTab:'Pedidos futuros',entreguesTab:'Pedidos entregues',historicoTab:'Auditoria',sugestoesTab:'Sugestões',notificacoesTab:'Notificações',funcionariosTab:'Funcionários',usuariosTab:'Usuários'};

function closeMenu(){$('sidebar').classList.remove('open');$('menuBackdrop').classList.add('hidden')}
async function switchTab(id){document.querySelectorAll('.tab-content').forEach(x=>x.classList.add('hidden'));$(id).classList.remove('hidden');document.querySelectorAll('[data-tab]').forEach(x=>x.classList.toggle('active',x.dataset.tab===id));$('mobileTitle').textContent=titles[id]||'BRCom ERP';closeMenu();try{await loaders[id]?.()}catch(e){showError(e)}}

const THEME_KEY='brcom-theme';
function applyTheme(theme){
  const selected=theme==='dark'?'dark':'light';
  document.documentElement.dataset.theme=selected;
  localStorage.setItem(THEME_KEY,selected);
  document.querySelectorAll('[data-theme-toggle]').forEach(button=>{
    const dark=selected==='dark';
    button.setAttribute('aria-label',dark?'Ativar modo claro':'Ativar modo escuro');
    button.title=dark?'Mudar para modo claro':'Mudar para modo escuro';
    const icon=button.querySelector('[data-theme-icon]');
    if(icon)icon.className=`fa-solid ${dark?'fa-sun':'fa-moon'}`;
  });
}
function initTheme(){
  applyTheme(document.documentElement.dataset.theme||'light');
  document.querySelectorAll('[data-theme-toggle]').forEach(button=>button.addEventListener('click',()=>applyTheme(document.documentElement.dataset.theme==='dark'?'light':'dark')));
}

function applyPermissions(){const u=state.user;const toggle=(selector,allowed)=>document.querySelectorAll(selector).forEach(x=>x.classList.toggle('hidden',!allowed));toggle('[data-admin]',u.pode_gerenciar_usuarios);toggle('[data-employees]',u.pode_gerenciar_funcionarios);toggle('[data-cost],[data-cost-field]',u.pode_alterar_custos);toggle('[data-clients]',u.pode_gerenciar_clientes);toggle('[data-agenda]',u.pode_acessar_agenda);toggle('[data-docs]',u.pode_acessar_docs);toggle('[data-history]',u.pode_gerenciar_historico||u.tipo_usuario==='DESENVOLVEDOR');toggle('[data-sales]',u.pode_registrar_vendas);toggle('[data-import]',u.pode_importar_planilhas);toggle('[data-sheets]',u.pode_editar_planilhas);toggle('[data-suggestions]',u.pode_enviar_sugestoes||u.pode_administrar_sugestoes);const quoteButton=document.querySelector('[data-toggle="quotePanel"]');if(quoteButton)quoteButton.classList.toggle('hidden',!u.pode_criar_orcamentos);}
function enter(){ $('loginScreen').classList.add('hidden');$('mainDashboard').classList.remove('hidden');$('userNameDisplay').textContent=state.user.nome;$('userRoleDisplay').textContent={DESENVOLVEDOR:'Desenvolvedor',DONO:'Dono',FUNCIONARIO:'Funcionário'}[state.user.tipo_usuario]||state.user.tipo_usuario;applyPermissions();refreshNotificationBadge().catch(()=>{});switchTab('dashboardTab') }

document.querySelectorAll('[data-toggle]').forEach(button=>button.addEventListener('click',()=>$(button.dataset.toggle).classList.toggle('hidden')));
document.querySelectorAll('[data-tab]').forEach(button=>button.addEventListener('click',()=>switchTab(button.dataset.tab)));
$('openMenu').addEventListener('click',()=>{$('sidebar').classList.add('open');$('menuBackdrop').classList.remove('hidden')});$('closeMenu').addEventListener('click',closeMenu);$('menuBackdrop').addEventListener('click',closeMenu);
$('logoutBtn').addEventListener('click',async()=>{await api('/api/logout',{method:'POST'});location.reload()});
function loginStatus(message,error=true){const el=$('loginSecurityStatus');el.textContent=message||'';el.className=`login-security-status ${message?'':'hidden'} ${error?'error':'success'}`}
function resetRecovery(clearUser=false){
  $('login_user').disabled=false;$('login_pass').disabled=false;$('loginSubmit').disabled=false;
  if(clearUser)$('login_user').value='';
  $('recoveryRequestForm').classList.add('hidden');$('recoveryCodeForm').classList.add('hidden');
  $('cancelRecovery').classList.add('hidden');
  $('recoveryRequestForm').reset();$('recoveryCodeForm').reset();loginStatus('');$(clearUser?'login_user':'login_pass').focus();
}
function showLockedAccess(detail){
  $('login_user').disabled=true;$('login_pass').disabled=true;$('loginSubmit').disabled=true;
  loginStatus(detail.message||'Acesso temporariamente bloqueado por segurança.');
  $('recoveryRequestForm').classList.toggle('hidden',!detail.recovery_available);
  $('recoveryCodeForm').classList.add('hidden');
  $('cancelRecovery').classList.remove('hidden');
  if(detail.recovery_available)$('recovery_email').focus();
}
$('loginForm').addEventListener('submit',async event=>{event.preventDefault();try{const result=await api('/api/login',{method:'POST',body:JSON.stringify({usuario_login:$('login_user').value,senha:$('login_pass').value})});state.user=result.usuario;enter()}catch(error){const detail=error.data?.detail||{};if(error.code==='ACCOUNT_LOCKED'){showLockedAccess(detail);return}const attempts=detail.remaining_attempts;loginStatus(`${error.message}${Number.isInteger(attempts)?` · ${attempts} tentativa(s) restante(s)`:''}`);$('login_pass').select()}});
$('recoveryRequestForm').addEventListener('submit',async event=>{event.preventDefault();try{const result=await api('/api/recuperacao/solicitar',{method:'POST',body:JSON.stringify({usuario_login:$('login_user').value,email:$('recovery_email').value})});$('recoveryRequestForm').classList.add('hidden');$('recoveryCodeForm').classList.remove('hidden');loginStatus(result.message,false);$('recovery_code').focus()}catch(error){loginStatus(error.message)}});
$('recoveryCodeForm').addEventListener('submit',async event=>{event.preventDefault();try{const result=await api('/api/recuperacao/confirmar',{method:'POST',body:JSON.stringify({usuario_login:$('login_user').value,codigo:$('recovery_code').value})});resetRecovery();loginStatus(result.message,false);$('login_pass').focus()}catch(error){loginStatus(error.message);$('recovery_code').select()}});
$('cancelRecovery').addEventListener('click',()=>resetRecovery(true));

initTheme();initCatalog();initOperations();initAdministration();initEmployees();initImports();initSalesSheets();initSuggestions();
try{state.user=await api('/api/me');enter()}catch(e){if(e.message!=='Sessão expirada')toast('Faça login para continuar')}
