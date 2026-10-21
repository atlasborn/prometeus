const $ = selector => document.querySelector(selector);
let format = 'mp3', info = null, analyzedUrl = '', selected = new Set(), submitting = false;
const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const message = text => { $('#notice').textContent = text; };
async function api(path, data) {
  const response = await fetch(path, data ? {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(data)} : {});
  const body = await response.json();
  if (!response.ok) throw new Error(body.error || (typeof body.detail === 'string' ? body.detail : '') || 'Não foi possível acessar o servidor.');
  return body;
}
function view(name) {
  for (const id of ['converter','downloads','guide']) $('#' + id).hidden = id !== name;
  document.querySelectorAll('.nav').forEach(button => button.classList.toggle('active',button.dataset.view === name));
  $('#page-name').textContent = {converter:'Conversor',downloads:'Meus downloads',guide:'Como funciona'}[name];
  if(name === 'downloads') loadJobs();
}
document.querySelectorAll('.nav').forEach(button => button.onclick = () => view(button.dataset.view));
document.querySelectorAll('.format').forEach(button => button.onclick = () => {
  format = button.dataset.format;
  document.querySelectorAll('.format').forEach(el => {el.classList.toggle('selected',el === button); el.setAttribute('aria-pressed',String(el === button));});
  $('#quality').innerHTML = format === 'mp3' ? '<option value="320">320 kbps · Alta qualidade</option><option value="192">192 kbps · Equilibrada</option><option value="128">128 kbps · Arquivo menor</option>' : '<option value="1080">1080p · Full HD</option><option value="720">720p · HD</option><option value="360">360p · Arquivo menor</option>';
});
$('#paste').onclick = async () => {try {$('#url').value = await navigator.clipboard.readText(); invalidate(); $('#url').focus();} catch {message('Use Ctrl + V para colar o link no campo acima.'); $('#url').focus();}};
function invalidate(){ info = null; selected.clear(); $('#results').hidden = true; }
$('#url').addEventListener('input', invalidate);
$('#link-form').onsubmit = async event => {
  event.preventDefault(); invalidate(); message('Carregando informações do YouTube…'); $('#inspect').disabled = true;
  const url = $('#url').value.trim();
  try {
    const result = await api('/api/inspect', {url});
    if ($('#url').value.trim() !== url) return;
    info = result; analyzedUrl = url;
    selected = new Set(info.items.filter(item => item.available).map(item => item.index));
    $('#playlist-title').textContent = info.title || 'Vídeo';
    $('#items').innerHTML = info.items.map(item => `<label class="item"><input type="checkbox" data-index="${item.index}" ${item.available ? 'checked' : 'disabled'}><span>${escapeHtml(item.title)}<small>${escapeHtml(item.channel || '')}${item.duration ? ' · '+Math.floor(item.duration/60)+':'+String(Math.floor(item.duration%60)).padStart(2,'0') : ''}${!item.available ? ' · Indisponível' : ''}</small></span></label>`).join('');
    $('#items').querySelectorAll('input').forEach(input => input.onchange = () => {input.checked ? selected.add(Number(input.dataset.index)) : selected.delete(Number(input.dataset.index)); updateSelection();});
    $('#limit-warning').hidden = !info.limited; $('#results').hidden = false; updateSelection(); message('');
  } catch(error){message(error.message);} finally {$('#inspect').disabled = false;}
};
function updateSelection(){ $('#selection-count').textContent = `${selected.size} de ${info.items.length} itens selecionados`; $('#convert').disabled = !selected.size || submitting; $('#select-all').textContent = selected.size === info.items.filter(item=>item.available).length ? 'Desmarcar todos' : 'Selecionar todos'; }
$('#select-all').onclick = () => {const available = info.items.filter(item=>item.available); selected = selected.size === available.length ? new Set() : new Set(available.map(item=>item.index)); $('#items').querySelectorAll('input').forEach(input=> input.checked=selected.has(Number(input.dataset.index))); updateSelection();};
$('#convert').onclick = async () => {
  if (!info || !selected.size || submitting) return;
  submitting = true; updateSelection();
  try {await runtimeReady; const data={url:analyzedUrl,title:info.title,format,quality:$('#quality').value,items:[...selected].sort((a,b)=>a-b)}; if(cloudMode) await queueCloud(data,info.items.filter(item=>selected.has(item.index))); else await api('/api/jobs',data); view('downloads');}
  catch(error){message(error.message);} finally {submitting=false;updateSelection();}
};
async function loadJobs(){
  try {
    await runtimeReady; const jobs = cloudMode ? cloudJobs : await api('/api/jobs'); $('#count').textContent = jobs.length;
    $('#jobs').innerHTML = jobs.length ? jobs.slice().reverse().map(job=>`<article class="job"><div class="job-head"><h3>${escapeHtml(job.title)}</h3><span class="tag">${escapeHtml(job.format.toUpperCase())}</span></div><p>${{queued:'Na fila',processing:'Convertendo',completed:'Pronto para baixar',error:'Falha na conversão'}[job.status]} · ${job.count} ${job.count === 1 ? 'item' : 'itens'}${job.status === 'processing' ? (job.current ? ' · item '+job.current+'/'+job.count : '')+' · arquivo atual: '+Math.round(job.progress)+'%' : ''}</p>${job.status==='processing' ? `<progress max="100" value="${job.progress}"></progress>` : ''}${job.status === 'completed' ? `<a class="primary" href="${job.downloadUrl || '/api/download/'+job.id}" download="${escapeHtml(job.filename || 'Prometeus')}">↓ Baixar ${job.count > 1 ? 'ZIP' : job.format.toUpperCase()}</a>` : ''}${job.error ? `<p role="alert">${escapeHtml(job.error)}</p>` : ''}</article>`).join('') : '<div class="empty"><strong>O próximo play começa aqui.</strong>Suas conversões aparecerão nesta área.<br><br><button class="primary" id="start-conversion">＋ Nova conversão</button></div>';
    if($('#start-conversion')) $('#start-conversion').onclick=()=>view('converter');
  } catch {$('#jobs').innerHTML='<div class="empty">Não foi possível conectar ao servidor. Verifique se ele está em execução.</div>';}
}
$('#year').textContent = new Date().getFullYear();
api('/api/health').then(health=>{$('#engine').textContent = !health.ytdlp ? 'YT-DLP NÃO INSTALADO' : health.ffmpeg ? 'PRONTO PARA CONVERTER' : 'FFMPEG NÃO INSTALADO';}).catch(()=>$('#engine').textContent='SERVIDOR OFFLINE');
loadJobs(); setInterval(()=>{if(!$('#downloads').hidden)loadJobs();},2500);
