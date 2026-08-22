import {$,api,date,esc,showError,toast} from './api.js?v=5.2.0';

let sheetType='NOTA_FISCAL';
let rows=[];

const editable=[
  ['data_venda','date'],['numero_documento','text'],['cliente_nome','text'],
  ['cliente_codigo','text'],['contato','text'],['quantidade','number'],
  ['descricao_original','text'],['descricao_padronizada','text'],['familia','text'],
  ['valor_unitario','number'],['valor_total','number'],['desconto','number'],
  ['percentual_desconto','number'],['observacoes','text'],
];
const params=values=>{const query=new URLSearchParams();Object.entries(values).forEach(([key,value])=>{if(value!==''&&value!==null&&value!==undefined)query.set(key,value)});return query.toString()};
const input=(row,field,type)=>`<input class="sheet-cell" data-sheet-field="${field}" data-record-id="${row.id}" type="${type}" ${type==='number'?'step="0.01"':''} value="${esc(row[field]??'')}">`;

function rowHtml(row,index){
  const trash=$('sheetTrash').value==='true';
  return `<tr data-sheet-row="${row.id}"><td class="sheet-row-number">${index+1}</td>${editable.map(([field,type])=>`<td>${input(row,field,type)}</td>`).join('')}<td><div class="actions">${trash?`<button class="btn-primary" data-sheet-restore="${row.id}">Restaurar</button>`:`<button class="btn-danger" data-sheet-delete="${row.id}" title="Mover para a lixeira"><i class="fa-solid fa-trash"></i></button>`}<button class="btn-secondary" data-sheet-history="${row.id}" title="Ver histórico"><i class="fa-solid fa-clock-rotate-left"></i></button></div></td></tr>`;
}

function newRowHtml(){
  const today=new Date().toISOString().slice(0,10);
  const blank={id:'new',data_venda:today,quantidade:'1',valor_unitario:'0',valor_total:'',desconto:'0',percentual_desconto:'0'};
  return `<tr class="sheet-new-row" data-sheet-row="new"><td class="sheet-row-number">Nova</td>${editable.map(([field,type])=>`<td><input class="sheet-cell" data-new-field="${field}" type="${type}" ${type==='number'?'step="0.01"':''} value="${esc(blank[field]??'')}"></td>`).join('')}<td><div class="actions"><button class="btn-primary" data-sheet-save-new><i class="fa-solid fa-check"></i> Salvar</button><button class="btn-secondary" data-sheet-cancel-new>Cancelar</button></div></td></tr>`;
}

function updateExport(){
  const query=params({ano:$('sheetYear').value,mes:$('sheetMonth').value});
  $('sheetExport').href=`/planilhas-vendas/exportar/${sheetType}.xlsx${query?`?${query}`:''}`;
}

export async function loadSalesSheet(){
  const query=params({
    tipo_documento:sheetType,busca:$('sheetSearch').value,ano:$('sheetYear').value,
    mes:$('sheetMonth').value,ordenar_por:$('sheetSort').value,
    ordem:$('sheetOrder').value,lixeira:$('sheetTrash').value,limite:1000,
  });
  rows=await api(`/planilhas-vendas/registros?${query}`);
  $('salesSheetTable').innerHTML=rows.map(rowHtml).join('')||'<tr><td colspan="16">Nenhuma linha encontrada nesta planilha.</td></tr>';
  updateExport();
}

function saveState(message,saving=false){
  $('sheetSaveState').innerHTML=saving?`<i class="fa-solid fa-spinner fa-spin"></i> ${message}`:`<i class="fa-solid fa-cloud-check"></i> ${message}`;
}

async function saveCell(inputElement){
  const recordId=inputElement.dataset.recordId,field=inputElement.dataset.sheetField;
  const original=rows.find(row=>row.id===Number(recordId));
  if(!original||String(original[field]??'')===inputElement.value)return;
  saveState('Salvando...',true);
  inputElement.classList.add('saving');
  try{
    const updated=await api(`/planilhas-vendas/registros/${recordId}`,{method:'PATCH',body:JSON.stringify({[field]:inputElement.value||null})});
    rows=rows.map(row=>row.id===updated.id?updated:row);
    inputElement.classList.remove('saving');inputElement.classList.add('saved');
    setTimeout(()=>inputElement.classList.remove('saved'),900);
    saveState(`Salvo agora por ${updated.atualizado_por_nome||'usuário'}`);
  }catch(error){inputElement.classList.remove('saving');inputElement.classList.add('invalid');saveState('Não foi possível salvar');showError(error)}
}

async function saveNewRow(){
  const tr=document.querySelector('[data-sheet-row="new"]');
  if(!tr)return;
  const data={tipo_documento:sheetType};
  tr.querySelectorAll('[data-new-field]').forEach(item=>data[item.dataset.newField]=item.value||null);
  try{
    await api('/planilhas-vendas/registros',{method:'POST',body:JSON.stringify(data)});
    toast('Nova linha adicionada e salva');
    await loadSalesSheet();
  }catch(error){showError(error)}
}

async function loadHistory(recordId=null){
  const query=recordId?`?registro_id=${recordId}`:'?limite=100';
  const history=await api(`/planilhas-vendas/historico${query}`);
  $('sheetHistoryList').innerHTML=history.map(item=>`<article class="list-card"><div><b>${esc(item.acao.replaceAll('_',' '))}</b><p>Linha ${item.registro_id} · ${esc(item.usuario_nome)}</p><small>${date(item.criado_em)} ${new Date(item.criado_em).toLocaleTimeString('pt-BR',{hour:'2-digit',minute:'2-digit'})}</small></div>${item.dados_anteriores?`<button class="btn-secondary" data-restore-version="${item.id}">Restaurar esta versão</button>`:''}</article>`).join('')||'<p class="help-text">Nenhuma alteração registrada.</p>';
  $('sheetHistoryPanel').classList.remove('hidden');
  $('sheetHistoryPanel').scrollIntoView({behavior:'smooth',block:'start'});
}

export function initSalesSheets(){
  document.querySelectorAll('[data-sheet-type]').forEach(button=>button.addEventListener('click',async()=>{sheetType=button.dataset.sheetType;document.querySelectorAll('[data-sheet-type]').forEach(item=>item.classList.toggle('active',item===button));await loadSalesSheet()}));
  $('sheetAddRow').addEventListener('click',()=>{if($('sheetTrash').value==='true'){toast('Volte para Linhas ativas para adicionar uma linha',true);return}if(document.querySelector('[data-sheet-row="new"]'))return;$('salesSheetTable').insertAdjacentHTML('afterbegin',newRowHtml());document.querySelector('[data-new-field="cliente_nome"]').focus()});
  $('sheetHistoryButton').addEventListener('click',()=>loadHistory().catch(showError));
  $('closeSheetHistory').addEventListener('click',()=>$('sheetHistoryPanel').classList.add('hidden'));
  ['sheetYear','sheetMonth','sheetSort','sheetOrder','sheetTrash'].forEach(id=>$(id).addEventListener('change',()=>loadSalesSheet().catch(showError)));
  let searchTimer;$('sheetSearch').addEventListener('input',()=>{clearTimeout(searchTimer);searchTimer=setTimeout(()=>loadSalesSheet().catch(showError),250)});
  $('planilhasVendasTab').addEventListener('focusout',event=>{const cell=event.target.closest('[data-sheet-field]');if(cell)saveCell(cell)});
  $('planilhasVendasTab').addEventListener('click',async event=>{
    const del=event.target.closest('[data-sheet-delete]'),restore=event.target.closest('[data-sheet-restore]'),history=event.target.closest('[data-sheet-history]'),version=event.target.closest('[data-restore-version]');
    try{
      if(event.target.closest('[data-sheet-save-new]'))await saveNewRow();
      if(event.target.closest('[data-sheet-cancel-new]'))document.querySelector('[data-sheet-row="new"]')?.remove();
      if(del&&confirm('Mover esta linha para a lixeira? Ela poderá ser restaurada.')){await api(`/planilhas-vendas/registros/${del.dataset.sheetDelete}`,{method:'DELETE'});toast('Linha movida para a lixeira');await loadSalesSheet()}
      if(restore){await api(`/planilhas-vendas/registros/${restore.dataset.sheetRestore}/restaurar`,{method:'POST'});toast('Linha restaurada');await loadSalesSheet()}
      if(history)await loadHistory(history.dataset.sheetHistory);
      if(version&&confirm('Restaurar os dados desta versão? A situação atual também ficará registrada no histórico.')){await api(`/planilhas-vendas/historico/${version.dataset.restoreVersion}/restaurar`,{method:'POST'});toast('Versão restaurada');await Promise.all([loadSalesSheet(),loadHistory()])}
    }catch(error){showError(error)}
  });
}
