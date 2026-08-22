import {$,api,state,esc,money,date,toast,showError,criticalConfirmation,payload} from './api.js?v=5.4.0';

const fields = {
  matricula:'employee_matricula',nome_completo:'employee_nome',nome_social:'employee_nome_social',
  cpf:'employee_cpf',rg:'employee_rg',orgao_emissor_rg:'employee_rg_orgao',uf_rg:'employee_rg_uf',
  data_nascimento:'employee_birth',email_pessoal:'employee_email',email_corporativo:'employee_corporate_email',
  celular:'employee_cell',telefone:'employee_phone',cep:'employee_cep',logradouro:'employee_street',
  numero:'employee_number',complemento:'employee_complement',bairro:'employee_neighborhood',
  cidade:'employee_city',uf:'employee_state',pis_pasep:'employee_pis',ctps_numero:'employee_ctps',
  ctps_serie:'employee_ctps_series',ctps_uf:'employee_ctps_state',departamento:'employee_department',
  cargo:'employee_job',tipo_contrato:'employee_contract',data_admissao:'employee_admission',
  salario_base:'employee_salary',jornada_semanal:'employee_hours',gestor:'employee_manager',
  contato_emergencia_nome:'employee_emergency_name',contato_emergencia_parentesco:'employee_emergency_relation',
  contato_emergencia_telefone:'employee_emergency_phone',status:'employee_status',
  data_desligamento:'employee_termination_date',motivo_desligamento:'employee_termination_reason',
  observacoes:'employee_notes',
};

const optionalFields = new Set([
  'matricula','nome_social','orgao_emissor_rg','uf_rg','email_corporativo','telefone','complemento',
  'pis_pasep','ctps_numero','ctps_serie','ctps_uf','salario_base','jornada_semanal','gestor',
  'data_desligamento','motivo_desligamento','observacoes',
]);

function localToday(){const now=new Date();return `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}-${String(now.getDate()).padStart(2,'0')}`}
function phone(value){const digits=String(value||'').replace(/\D/g,'');if(digits.length===11)return `(${digits.slice(0,2)}) ${digits.slice(2,7)}-${digits.slice(7)}`;if(digits.length===10)return `(${digits.slice(0,2)}) ${digits.slice(2,6)}-${digits.slice(6)}`;return value||'—'}
function cpf(value){const digits=String(value||'').replace(/\D/g,'');return digits.length===11?`${digits.slice(0,3)}.${digits.slice(3,6)}.${digits.slice(6,9)}-${digits.slice(9)}`:value||'—'}
function cep(value){const digits=String(value||'').replace(/\D/g,'');return digits.length===8?`${digits.slice(0,5)}-${digits.slice(5)}`:value||'—'}
function textOrNull(id){const value=$(id).value.trim();return value||null}
function numberOrNull(id){return $(id).value===''?null:Number($(id).value)}
function contractName(value){return {CLT:'CLT',PJ:'PJ',ESTAGIO:'Estágio',TEMPORARIO:'Temporário',APRENDIZ:'Aprendiz',OUTRO:'Outro'}[value]||value}

function syncTerminationFields(){
  const terminated=$('employee_status').value==='DESLIGADO';
  $('employeeTerminationFields').classList.toggle('hidden',!terminated);
  $('employee_termination_date').required=terminated;
  $('employee_termination_reason').required=terminated;
  if(terminated&&!$('employee_termination_date').value)$('employee_termination_date').value=localToday();
  if(!terminated){$('employee_termination_date').value='';$('employee_termination_reason').value=''}
}

function employeePayload(){
  const data={};
  Object.entries(fields).forEach(([key,id])=>{data[key]=optionalFields.has(key)?textOrNull(id):$(id).value.trim()});
  data.usuario_id=$('employee_user').value?Number($('employee_user').value):null;
  data.salario_base=numberOrNull('employee_salary');
  data.jornada_semanal=numberOrNull('employee_hours');
  if(data.status!=='DESLIGADO'){data.data_desligamento=null;data.motivo_desligamento=null}
  return data;
}

function renderUserOptions(employeeId=null,selectedUserId=null){
  $('employee_user').innerHTML='<option value="">Sem acesso ao ERP</option>'+state.employeeUsers.map(user=>{
    const used=user.funcionario_id&&user.funcionario_id!==employeeId;
    const selected=user.id===Number(selectedUserId);
    return `<option value="${user.id}" ${used?'disabled':''} ${selected?'selected':''}>${esc(user.nome)} · ${esc(user.usuario_login)}${user.ativo?'':' · inativo'}${used?' · já vinculado':''}</option>`;
  }).join('');
}

function resetEmployeeForm(){
  $('employeeForm').reset();$('employee_id').value='';$('employeeFormTitle').textContent='Novo funcionário';
  $('employee_status').value='ATIVO';renderUserOptions();syncTerminationFields();$('employeePanel').classList.add('hidden');
}

function fillEmployeeForm(employee){
  $('employeeForm').reset();$('employee_id').value=employee.id;$('employeeFormTitle').textContent=`Editar ${employee.nome_completo}`;
  Object.entries(fields).forEach(([key,id])=>{$(id).value=employee[key]??''});
  renderUserOptions(employee.id,employee.usuario_id);syncTerminationFields();$('employeePanel').classList.remove('hidden');
  $('employeePanel').scrollIntoView({behavior:'smooth',block:'start'});
}

async function editEmployee(employeeId){fillEmployeeForm(await api(`/funcionarios/${employeeId}`))}

function renderDepartmentFilter(departments){
  const selected=$('employee_filter_department').value;
  $('employee_filter_department').innerHTML='<option value="">Todos os departamentos</option>'+departments.map(item=>`<option value="${esc(item)}">${esc(item)}</option>`).join('');
  $('employee_filter_department').value=selected;
}

function renderEmployees(list){
  const permanent=['DONO','DESENVOLVEDOR'].includes(state.user.tipo_usuario);
  $('employeeList').innerHTML=list.map(employee=>{
    const active=employee.status==='ATIVO';
    const access=employee.usuario_id?`<span class="badge ${employee.usuario_ativo?'badge-green':'badge-red'}"><i class="fa-solid fa-key"></i> ${employee.usuario_ativo?'Acesso ativo':'Acesso bloqueado'}</span>`:'<span class="badge">Sem acesso ao ERP</span>';
    return `<article class="list-card employee-card ${active?'':'employee-terminated'}"><div class="employee-avatar"><i class="fa-solid ${active?'fa-user-tie':'fa-user-slash'}"></i></div><div class="employee-card-body"><div class="employee-card-title"><div><b>${esc(employee.nome_social||employee.nome_completo)}</b>${employee.nome_social?`<small>${esc(employee.nome_completo)}</small>`:''}</div><span class="badge ${active?'badge-green':'badge-red'}">${active?'Ativo':'Desligado'}</span></div><p>${esc(employee.matricula)} · ${esc(employee.cargo)} · ${esc(employee.departamento)}</p><div class="employee-card-meta"><span><i class="fa-regular fa-id-card"></i> ${esc(employee.cpf_mascarado)}</span><span><i class="fa-solid fa-mobile-screen"></i> ${esc(phone(employee.celular))}</span><span><i class="fa-regular fa-envelope"></i> ${esc(employee.email_corporativo||'Sem e-mail corporativo')}</span><span><i class="fa-regular fa-calendar"></i> Admissão: ${date(employee.data_admissao)}</span></div><div class="employee-access">${access}${employee.usuario_login?`<small>${esc(employee.usuario_login)}</small>`:''}</div></div><div class="actions employee-actions"><button class="btn-secondary" data-view-employee="${employee.id}"><i class="fa-solid fa-eye"></i> Visualizar</button><button class="btn-secondary" data-edit-employee="${employee.id}"><i class="fa-solid fa-pen"></i> Editar</button>${active?`<button class="btn-danger" data-terminate-employee="${employee.id}"><i class="fa-solid fa-user-slash"></i> Desligar</button>`:`<button class="btn-secondary" data-reactivate-employee="${employee.id}"><i class="fa-solid fa-user-check"></i> Reativar</button>${permanent?`<button class="btn-danger" data-delete-employee="${employee.id}"><i class="fa-solid fa-trash"></i> Excluir</button>`:''}`}</div></article>`;
  }).join('')||'<div class="card p-5"><b>Nenhum funcionário encontrado.</b><p class="help-text">Revise os filtros ou adicione o primeiro cadastro.</p></div>';
}

export async function loadEmployees(){
  if(!state.user.pode_gerenciar_funcionarios)return;
  const params=new URLSearchParams();
  if($('employee_search').value)params.set('busca',$('employee_search').value);
  if($('employee_filter_status').value)params.set('status',$('employee_filter_status').value);
  if($('employee_filter_department').value)params.set('departamento',$('employee_filter_department').value);
  const [list,overview,users]=await Promise.all([
    api(`/funcionarios/?${params}`),api('/funcionarios/resumo'),api('/funcionarios/usuarios-disponiveis'),
  ]);
  state.employees=list;state.employeeUsers=users;
  $('employeeTotal').textContent=overview.total;$('employeeActive').textContent=overview.ativos;$('employeeTerminated').textContent=overview.desligados;
  renderDepartmentFilter(overview.departamentos);renderUserOptions(Number($('employee_id').value)||null,$('employee_user').value||null);renderEmployees(list);
}

function detailItem(label,value){return `<div class="employee-detail-item"><span>${esc(label)}</span><b>${esc(value??'—')}</b></div>`}
function detailSection(title,icon,items){return `<section><h3><i class="fa-solid ${icon}"></i>${esc(title)}</h3><div class="employee-detail-grid">${items.join('')}</div></section>`}

async function showEmployee(employeeId){
  const employee=await api(`/funcionarios/${employeeId}`);state.selectedEmployee=employee;
  $('employeeDetailTitle').textContent=employee.nome_social||employee.nome_completo;
  $('employeeDetailSubtitle').textContent=`${employee.matricula} · ${employee.cargo} · ${employee.status==='ATIVO'?'Ativo':'Desligado'}`;
  $('employeeDetailBody').innerHTML=[
    detailSection('Identificação','fa-id-card',[
      detailItem('Nome completo',employee.nome_completo),detailItem('Nome social',employee.nome_social),detailItem('CPF',cpf(employee.cpf)),detailItem('RG',`${employee.rg}${employee.orgao_emissor_rg?` · ${employee.orgao_emissor_rg}`:''}${employee.uf_rg?`/${employee.uf_rg}`:''}`),detailItem('Nascimento',date(employee.data_nascimento)),
    ]),
    detailSection('Contato e endereço','fa-location-dot',[
      detailItem('Celular',phone(employee.celular)),detailItem('Telefone',phone(employee.telefone)),detailItem('E-mail pessoal',employee.email_pessoal),detailItem('E-mail corporativo',employee.email_corporativo),detailItem('Endereço',`${employee.logradouro}, ${employee.numero}${employee.complemento?` · ${employee.complemento}`:''}`),detailItem('Bairro',employee.bairro),detailItem('Cidade/UF',`${employee.cidade}/${employee.uf}`),detailItem('CEP',cep(employee.cep)),
    ]),
    detailSection('Vínculo profissional','fa-briefcase',[
      detailItem('Departamento',employee.departamento),detailItem('Cargo',employee.cargo),detailItem('Contrato',contractName(employee.tipo_contrato)),detailItem('Admissão',date(employee.data_admissao)),detailItem('Salário base',employee.salario_base===null?'Não informado':money(employee.salario_base)),detailItem('Jornada semanal',employee.jornada_semanal===null?'Não informada':`${employee.jornada_semanal} h`),detailItem('Gestor',employee.gestor),detailItem('PIS/PASEP',employee.pis_pasep),detailItem('CTPS',[employee.ctps_numero,employee.ctps_serie,employee.ctps_uf].filter(Boolean).join(' · ')||'—'),detailItem('Conta no ERP',employee.usuario_login?`${employee.usuario_nome} · ${employee.usuario_login} · ${employee.usuario_ativo?'ativa':'bloqueada'}`:'Sem conta vinculada'),
    ]),
    detailSection('Emergência e situação','fa-shield-heart',[
      detailItem('Contato',employee.contato_emergencia_nome),detailItem('Relação',employee.contato_emergencia_parentesco),detailItem('Telefone',phone(employee.contato_emergencia_telefone)),detailItem('Status',employee.status==='ATIVO'?'Ativo':'Desligado'),detailItem('Data do desligamento',date(employee.data_desligamento)),detailItem('Motivo',employee.motivo_desligamento),detailItem('Observações',employee.observacoes),detailItem('Última atualização',`${new Date(employee.atualizado_em).toLocaleString('pt-BR')} · ${employee.atualizado_por_nome}`),
    ]),
  ].join('');
  $('employeeDetailDialog').showModal();
}

export function initEmployees(){
  $('newEmployee').addEventListener('click',()=>{resetEmployeeForm();$('employeePanel').classList.remove('hidden');$('employeePanel').scrollIntoView({behavior:'smooth',block:'start'})});
  $('closeEmployeePanel').addEventListener('click',resetEmployeeForm);$('cancelEmployeeEdit').addEventListener('click',resetEmployeeForm);
  $('employee_status').addEventListener('change',syncTerminationFields);
  $('employeeFilters').addEventListener('submit',event=>{event.preventDefault();loadEmployees().catch(showError)});
  $('clearEmployeeFilters').addEventListener('click',()=>{$('employeeFilters').reset();loadEmployees().catch(showError)});
  $('employeeForm').addEventListener('submit',async event=>{event.preventDefault();try{const id=$('employee_id').value;await api(id?`/funcionarios/${id}`:'/funcionarios/',{method:id?'PUT':'POST',body:JSON.stringify(employeePayload())});toast(id?'Cadastro do funcionário atualizado':'Funcionário cadastrado');resetEmployeeForm();await loadEmployees()}catch(error){showError(error)}});
  $('employeeList').addEventListener('click',async event=>{const view=event.target.closest('[data-view-employee]'),edit=event.target.closest('[data-edit-employee]'),terminate=event.target.closest('[data-terminate-employee]'),reactivate=event.target.closest('[data-reactivate-employee]'),remove=event.target.closest('[data-delete-employee]');try{if(view){await showEmployee(view.dataset.viewEmployee);return}if(edit){await editEmployee(edit.dataset.editEmployee);return}if(terminate){$('employee_status_id').value=terminate.dataset.terminateEmployee;$('employee_status_date').value=localToday();$('employee_status_reason').value='';$('employeeStatusDialog').showModal();return}if(reactivate&&confirm('Reativar este cadastro? A conta de acesso continuará bloqueada até um administrador reativá-la na aba Usuários.')){await api(`/funcionarios/${reactivate.dataset.reactivateEmployee}/status`,payload({status:'ATIVO'}));toast('Cadastro reativado; o acesso ao ERP não foi liberado automaticamente');await loadEmployees();return}if(remove){const confirmation=await criticalConfirmation('Excluir funcionário definitivamente','Use apenas para cadastro duplicado ou criado por engano. O histórico da ação será preservado e a conta de acesso não será excluída.');if(confirmation){await api(`/funcionarios/${remove.dataset.deleteEmployee}/excluir-definitivamente`,payload(confirmation));toast('Cadastro excluído definitivamente');await loadEmployees()}}}catch(error){showError(error)}});
  $('employeeStatusForm').addEventListener('submit',async event=>{event.preventDefault();try{await api(`/funcionarios/${$('employee_status_id').value}/status`,payload({status:'DESLIGADO',data_desligamento:$('employee_status_date').value,motivo:$('employee_status_reason').value}));$('employeeStatusDialog').close();toast('Funcionário desligado; histórico preservado e acesso bloqueado');await loadEmployees()}catch(error){showError(error)}});
  $('cancelEmployeeStatus').addEventListener('click',()=>$('employeeStatusDialog').close());
  $('closeEmployeeDetail').addEventListener('click',()=>$('employeeDetailDialog').close());
  $('editEmployeeFromDetail').addEventListener('click',()=>{const employee=state.selectedEmployee;if(!employee)return;$('employeeDetailDialog').close();fillEmployeeForm(employee)});
  syncTerminationFields();
}
