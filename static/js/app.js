import {$,api,state,toast,showError} from './api.js?v=4.7.0';
import {initCatalog,loadProducts,loadFormulas} from './catalog.js?v=4.7.0';
import {initOperations,loadDashboard,loadQuotes,loadOrders,loadSales,loadReports} from './operations.js?v=4.7.0';
import {initAdministration,loadClients,loadAgenda,loadFutureOrders,loadHistory,loadUsers} from './administration.js?v=4.7.0';
import {initImports,loadImports} from './imports.js?v=4.7.0';
import {initSalesSheets,loadSalesSheet} from './sales-sheets.js?v=4.7.0';

const loaders={dashboardTab:loadDashboard,produtosTab:loadProducts,estoqueTab:loadProducts,formulasTab:loadFormulas,orcamentosTab:loadQuotes,osTab:loadOrders,vendasTab:loadSales,importacoesTab:loadImports,planilhasVendasTab:loadSalesSheet,relatoriosTab:loadReports,clientesTab:loadClients,agendaTab:loadAgenda,pedidosTab:loadFutureOrders,historicoTab:async()=>{await loadProducts();return loadHistory()},usuariosTab:loadUsers};
const titles={dashboardTab:'Painel',produtosTab:'Produtos',estoqueTab:'Movimentar estoque',formulasTab:'Fórmulas',orcamentosTab:'Orçamentos',osTab:'Ordens de serviço',vendasTab:'Vendas',importacoesTab:'Importar planilhas',planilhasVendasTab:'Planilhas de Vendas',relatoriosTab:'Relatórios',clientesTab:'Clientes',agendaTab:'Agenda',pedidosTab:'Pedidos futuros',historicoTab:'Auditoria',usuariosTab:'Usuários'};

function closeMenu(){$('sidebar').classList.remove('open');$('menuBackdrop').classList.add('hidden')}
async function switchTab(id){document.querySelectorAll('.tab-content').forEach(x=>x.classList.add('hidden'));$(id).classList.remove('hidden');document.querySelectorAll('[data-tab]').forEach(x=>x.classList.toggle('active',x.dataset.tab===id));$('mobileTitle').textContent=titles[id]||'BRCom ERP';closeMenu();try{await loaders[id]?.()}catch(e){showError(e)}}

function applyPermissions(){const u=state.user;const toggle=(selector,allowed)=>document.querySelectorAll(selector).forEach(x=>x.classList.toggle('hidden',!allowed));toggle('[data-admin]',u.pode_gerenciar_usuarios);toggle('[data-cost],[data-cost-field]',u.pode_alterar_custos);toggle('[data-clients]',u.pode_gerenciar_clientes);toggle('[data-agenda]',u.pode_acessar_agenda);toggle('[data-docs]',u.pode_acessar_docs);toggle('[data-history]',u.pode_gerenciar_historico||u.tipo_usuario==='DESENVOLVEDOR');toggle('[data-sales]',u.pode_registrar_vendas);toggle('[data-import]',u.pode_importar_planilhas);toggle('[data-sheets]',u.pode_editar_planilhas);const quoteButton=document.querySelector('[data-toggle="quotePanel"]');if(quoteButton)quoteButton.classList.toggle('hidden',!u.pode_criar_orcamentos);}
function enter(){ $('loginScreen').classList.add('hidden');$('mainDashboard').classList.remove('hidden');$('userNameDisplay').textContent=state.user.nome;$('userRoleDisplay').textContent={DESENVOLVEDOR:'Desenvolvedor',DONO:'Dono',FUNCIONARIO:'Funcionário'}[state.user.tipo_usuario]||state.user.tipo_usuario;applyPermissions();switchTab('dashboardTab') }

document.querySelectorAll('[data-toggle]').forEach(button=>button.addEventListener('click',()=>$(button.dataset.toggle).classList.toggle('hidden')));
document.querySelectorAll('[data-tab]').forEach(button=>button.addEventListener('click',()=>switchTab(button.dataset.tab)));
$('openMenu').addEventListener('click',()=>{$('sidebar').classList.add('open');$('menuBackdrop').classList.remove('hidden')});$('closeMenu').addEventListener('click',closeMenu);$('menuBackdrop').addEventListener('click',closeMenu);
$('logoutBtn').addEventListener('click',async()=>{await api('/api/logout',{method:'POST'});location.reload()});
$('loginForm').addEventListener('submit',async event=>{event.preventDefault();try{const result=await api('/api/login',{method:'POST',body:JSON.stringify({usuario_login:$('login_user').value,senha:$('login_pass').value})});state.user=result.usuario;enter()}catch(e){showError(e)}});

initCatalog();initOperations();initAdministration();initImports();initSalesSheets();
try{state.user=await api('/api/me');enter()}catch(e){if(e.message!=='Sessão expirada')toast('Faça login para continuar')}
