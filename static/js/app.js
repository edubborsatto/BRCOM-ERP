import {$,api,state,toast,showError} from './api.js';
import {initCatalog,loadProducts,loadFormulas} from './catalog.js';
import {initOperations,loadDashboard,loadQuotes,loadOrders,loadSales,loadReports} from './operations.js';
import {initAdministration,loadClients,loadAgenda,loadFutureOrders,loadHistory,loadUsers} from './administration.js';

const loaders={dashboardTab:loadDashboard,produtosTab:loadProducts,estoqueTab:loadProducts,formulasTab:loadFormulas,orcamentosTab:loadQuotes,osTab:loadOrders,vendasTab:loadSales,relatoriosTab:loadReports,clientesTab:loadClients,agendaTab:loadAgenda,pedidosTab:loadFutureOrders,historicoTab:loadHistory,usuariosTab:loadUsers};
const titles={dashboardTab:'Painel',produtosTab:'Produtos',estoqueTab:'Movimentar estoque',formulasTab:'Fórmulas',orcamentosTab:'Orçamentos',osTab:'Ordens de serviço',vendasTab:'Vendas',relatoriosTab:'Relatórios',clientesTab:'Clientes',agendaTab:'Agenda',pedidosTab:'Pedidos futuros',historicoTab:'Auditoria',usuariosTab:'Usuários'};

function closeMenu(){$('sidebar').classList.remove('open');$('menuBackdrop').classList.add('hidden')}
async function switchTab(id){document.querySelectorAll('.tab-content').forEach(x=>x.classList.add('hidden'));$(id).classList.remove('hidden');document.querySelectorAll('[data-tab]').forEach(x=>x.classList.toggle('active',x.dataset.tab===id));$('mobileTitle').textContent=titles[id]||'BRCom ERP';closeMenu();try{await loaders[id]?.()}catch(e){showError(e)}}

function applyPermissions(){const u=state.user;document.querySelectorAll('[data-admin]').forEach(x=>x.classList.toggle('hidden',!u.pode_gerenciar_usuarios));document.querySelectorAll('[data-cost],[data-cost-field]').forEach(x=>x.classList.toggle('hidden',!u.pode_alterar_custos));document.querySelectorAll('[data-clients]').forEach(x=>x.classList.toggle('hidden',!u.pode_gerenciar_clientes));document.querySelectorAll('[data-agenda]').forEach(x=>x.classList.toggle('hidden',!u.pode_acessar_agenda));document.querySelectorAll('[data-docs]').forEach(x=>x.classList.toggle('hidden',!u.pode_acessar_docs));}
function enter(){ $('loginScreen').classList.add('hidden');$('mainDashboard').classList.remove('hidden');$('userNameDisplay').textContent=state.user.nome;applyPermissions();switchTab('dashboardTab') }

document.querySelectorAll('[data-toggle]').forEach(button=>button.addEventListener('click',()=>$(button.dataset.toggle).classList.toggle('hidden')));
document.querySelectorAll('[data-tab]').forEach(button=>button.addEventListener('click',()=>switchTab(button.dataset.tab)));
$('openMenu').addEventListener('click',()=>{$('sidebar').classList.add('open');$('menuBackdrop').classList.remove('hidden')});$('closeMenu').addEventListener('click',closeMenu);$('menuBackdrop').addEventListener('click',closeMenu);
$('logoutBtn').addEventListener('click',async()=>{await api('/api/logout',{method:'POST'});location.reload()});
$('loginForm').addEventListener('submit',async event=>{event.preventDefault();try{const result=await api('/api/login',{method:'POST',body:JSON.stringify({usuario_login:$('login_user').value,senha:$('login_pass').value})});state.user=result.usuario;enter()}catch(e){showError(e)}});

initCatalog();initOperations();initAdministration();
try{state.user=await api('/api/me');enter()}catch(e){if(e.message!=='Sessão expirada')toast('Faça login para continuar')}
