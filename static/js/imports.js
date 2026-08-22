import {$,api,state,date,esc,money,qty,toast,showError} from './api.js?v=5.4.0';

let activeImport=null;
let displayedRecords=[];

const params=values=>{const search=new URLSearchParams();Object.entries(values).forEach(([key,value])=>{if(value!==''&&value!==null&&value!==undefined)search.set(key,value)});return search.toString()};
const origin=value=>value==='NOTA_FISCAL'?'Nota fiscal':'Recibo';
const months=['Janeiro','Fevereiro','Março','Abril','Maio','Junho','Julho','Agosto','Setembro','Outubro','Novembro','Dezembro'];

function importStatus(row){
  if(row.status_importacao==='NOVO')return '<span class="badge status-standard">Novo · aceito</span>';
  const source=row.origem_duplicidade==='JA_IMPORTADO'?'já existe no sistema':'repetida nesta planilha';
  if(row.decisao_duplicidade==='IMPORTAR')return `<span class="badge status-standard">Cópia · importar</span><small class="block mt-1">${source}</small>`;
  if(row.decisao_duplicidade==='IGNORAR')return `<span class="badge status-ignored">Cópia · ignorar</span><small class="block mt-1">${source}</small>`;
  return `<span class="badge status-review">Cópia · revisar</span><small class="block mt-1">${source}</small>`;
}

function duplicateActions(row){
  if(row.status_importacao!=='DUPLICADO')return '<span class="badge status-standard">Aceito automaticamente</span>';
  return `<div class="actions"><button class="btn-secondary" data-duplicate-decision="IGNORAR" data-record-id="${row.id}">Ignorar</button><button class="btn-primary" data-duplicate-decision="IMPORTAR" data-record-id="${row.id}">Importar mesmo</button></div>`;
}

function recordRow(row,preview=false){
  return `<tr class="${row.status_importacao==='DUPLICADO'&&row.decisao_duplicidade==='PENDENTE'?'row-review':''}">${preview?`<td>${row.linha_origem}</td>`:''}<td>${date(row.data_venda)}</td>${preview?'':`<td>${origin(row.tipo_documento)}</td><td>${esc(row.numero_documento||'—')}</td>`}<td>${esc(row.cliente_nome)}</td>${preview?`<td title="${esc(row.descricao_original)}">${esc(row.descricao_original)}</td>`:''}<td>${esc(row.descricao_padronizada)}</td>${preview?'':`<td>${esc(row.familia||'—')}</td>`}<td>${qty(row.quantidade)}</td><td>${money(row.valor_total)}</td><td>${importStatus(row)}</td>${preview?`<td>${duplicateActions(row)}</td>`:''}</tr>`;
}

async function showPreview(batch){
  activeImport=batch;
  $('importPreview').classList.remove('hidden');
  $('importPreviewMessage').textContent=`${batch.nome_arquivo} · aba ${batch.aba_origem}`;
  const cards=[['Linhas lidas',batch.total_linhas],['Novas aceitas',batch.linhas_novas],['Possíveis cópias',batch.linhas_duplicadas],['Cópias pendentes',batch.linhas_revisao]];
  $('importPreviewCards').innerHTML=cards.map(([label,value])=>`<div class="card stat"><b>${value}</b><span>${label}</span></div>`).join('');
  await loadPreviewRecords();
  $('ignoreAllDuplicates').classList.toggle('hidden',!batch.linhas_revisao);
  $('confirmImport').disabled=Boolean(batch.linhas_revisao);
  $('confirmImport').title=batch.linhas_revisao?'Decida primeiro o que fazer com as possíveis cópias':'';
  $('importPreview').scrollIntoView({behavior:'smooth',block:'start'});
}

async function loadPreviewRecords(){
  if(!activeImport)return;
  const query=params({
    importacao_id:activeImport.id,
    situacao:$('previewSituation').value,
    ordenar_por:$('previewSort').value,
    ordem:$('previewOrder').value,
    limite:2000,
  });
  displayedRecords=await api(`/importacoes/registros?${query}`);
  $('importPreviewTable').innerHTML=displayedRecords.map(row=>recordRow(row,true)).join('')||'<tr><td colspan="9">Nenhum registro corresponde aos filtros.</td></tr>';
}

async function decideDuplicate(id,decision){
  await api(`/importacoes/registros/${id}/duplicidade`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({decisao:decision})});
  const batches=await api('/importacoes/');
  const batch=batches.find(item=>item.id===activeImport.id);
  await showPreview(batch);
}

async function loadHistory(){
  const batches=await api('/importacoes/');
  $('importHistory').innerHTML=batches.map(item=>`<article class="list-card"><div><b>${esc(item.nome_arquivo)}</b><p>${origin(item.tipo_documento)} · ${item.linhas_novas} nova(s) · ${item.linhas_duplicadas} possível(is) cópia(s)</p><small>${date(item.criado_em)} · ${item.status==='CONFIRMADA'?'Confirmada':item.linhas_revisao?`${item.linhas_revisao} cópia(s) pendente(s)`:'Pronta para confirmar'}</small></div>${item.status==='PREVIA'?`<button class="btn-secondary" data-open-import="${item.id}">Continuar</button>`:''}</article>`).join('')||'<p class="help-text">Nenhuma planilha importada ainda.</p>';
}

async function loadAnalysis(){
  const query=params({ano:$('analysis_year').value,mes:$('analysis_month').value,tipo_documento:$('analysis_type').value});
  const [products,revenue]=await Promise.all([api(`/importacoes/analise/resumo?${query}`),api(`/relatorios/faturamento?${query}`)]);
  const cards=[['Faturamento total',money(revenue.total)],['Notas fiscais',money(revenue.nota_fiscal)],['Recibos',money(revenue.recibo)],['Quantidade vendida',qty(products.quantidade)]];
  $('importAnalysisCards').innerHTML=cards.map(([label,value])=>`<div class="card stat"><b>${value}</b><span>${label}</span></div>`).join('');
  $('importProductAnalysis').innerHTML=products.produtos.map(item=>`<tr><td>${esc(item.produto)}</td><td>${qty(item.quantidade)}</td><td>${money(item.faturamento)}</td></tr>`).join('')||'<tr><td colspan="3">Sem vendas confirmadas neste período.</td></tr>';
  $('monthlyRevenueTable').innerHTML=revenue.mensal.map(item=>`<tr><td>${months[item.mes-1]} de ${item.ano}</td><td>${money(item.nota_fiscal)}</td><td>${money(item.recibo)}</td><td><b>${money(item.total)}</b></td></tr>`).join('')||'<tr><td colspan="4">Sem faturamento neste período.</td></tr>';
  $('yearlyRevenueTable').innerHTML=revenue.anual.map(item=>`<tr><td>${item.ano}</td><td>${money(item.nota_fiscal)}</td><td>${money(item.recibo)}</td><td><b>${money(item.total)}</b></td></tr>`).join('')||'<tr><td colspan="4">Sem faturamento neste período.</td></tr>';
  updateExportLink();
}

function updateExportLink(){
  const query=params({ano:$('analysis_year').value,mes:$('analysis_month').value,tipo_documento:$('importRecordType').value});
  $('exportImportedSales').href=`/importacoes/exportar.csv${query?`?${query}`:''}`;
}

async function loadRecords(){
  activeImport=null;
  const query=params({
    busca:$('importSearch').value,
    tipo_documento:$('importRecordType').value,
    situacao:$('recordSituation').value,
    ordenar_por:$('recordSort').value,
    ordem:$('recordOrder').value,
    ano:$('analysis_year').value,
    mes:$('analysis_month').value,
    limite:500,
  });
  displayedRecords=await api(`/importacoes/registros?${query}`);
  $('importRecordsTable').innerHTML=displayedRecords.map(row=>recordRow(row)).join('')||'<tr><td colspan="9">Nenhum registro encontrado.</td></tr>';
  updateExportLink();
}

export async function loadImports(){
  const financial=state.user.pode_ver_faturamento;
  $('runAnalysis').classList.toggle('hidden',!financial);
  $('exportImportedSales').classList.toggle('hidden',!financial);
  $('importAnalysisCards').classList.toggle('hidden',!financial);
  $('monthlyRevenueTable').closest('.grid').classList.toggle('hidden',!financial);
  $('importProductAnalysis').closest('.grid').classList.toggle('hidden',!financial);
  const tasks=[loadHistory(),loadRecords()];
  if(financial)tasks.push(loadAnalysis());
  await Promise.all(tasks);
}

export function initImports(){
  $('importForm').addEventListener('submit',async event=>{event.preventDefault();const button=$('importPreviewButton');button.disabled=true;button.textContent='Analisando planilha...';try{const form=new FormData();form.append('arquivo',$('import_file').files[0]);const batch=await api(`/importacoes/previsualizar?tipo_documento=${$('import_tipo').value}`,{method:'POST',body:form});$('previewSituation').value='';$('previewSort').value='data';$('previewOrder').value='desc';await showPreview(batch);await loadHistory()}catch(error){showError(error)}finally{button.disabled=false;button.innerHTML='<i class="fa-solid fa-magnifying-glass"></i> Analisar e mostrar prévia'}});
  $('confirmImport').addEventListener('click',async()=>{if(!activeImport)return;try{await api(`/importacoes/${activeImport.id}/confirmar`,{method:'POST'});toast('Importação confirmada');activeImport=null;$('importPreview').classList.add('hidden');$('importForm').reset();await loadImports()}catch(error){showError(error)}});
  $('ignoreAllDuplicates').addEventListener('click',async()=>{if(!activeImport||!confirm('Ignorar todas as possíveis cópias desta planilha?'))return;try{const batch=await api(`/importacoes/${activeImport.id}/duplicidades/ignorar`,{method:'POST'});await showPreview(batch);toast('Todas as cópias foram marcadas para ignorar')}catch(error){showError(error)}});
  $('cancelImport').addEventListener('click',async()=>{if(!activeImport)return;if(!confirm('Cancelar esta prévia? Nenhum dado será incorporado aos relatórios.'))return;try{await api(`/importacoes/${activeImport.id}`,{method:'DELETE'});activeImport=null;$('importPreview').classList.add('hidden');await loadHistory()}catch(error){showError(error)}});
  $('runAnalysis').addEventListener('click',()=>Promise.all([loadAnalysis(),loadRecords()]).catch(showError));
  $('importSearch').addEventListener('input',()=>loadRecords().catch(showError));
  $('importRecordType').addEventListener('change',()=>loadRecords().catch(showError));
  ['previewSituation','previewSort','previewOrder'].forEach(id=>$(id).addEventListener('change',()=>loadPreviewRecords().catch(showError)));
  ['recordSituation','recordSort','recordOrder'].forEach(id=>$(id).addEventListener('change',()=>loadRecords().catch(showError)));
  $('importacoesTab').addEventListener('click',async event=>{const open=event.target.closest('[data-open-import]'),decision=event.target.closest('[data-duplicate-decision]');try{if(open){const batches=await api('/importacoes/');const batch=batches.find(item=>item.id===Number(open.dataset.openImport));if(batch)await showPreview(batch)}if(decision)await decideDuplicate(decision.dataset.recordId,decision.dataset.duplicateDecision)}catch(error){showError(error)}});
}
