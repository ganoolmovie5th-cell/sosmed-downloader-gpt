'use strict';
const $ = (selector) => document.querySelector(selector);
const names = {instagram:'Instagram',tiktok:'TikTok',facebook:'Facebook',x:'X / Twitter',threads:'Threads'};
const hostPlatforms = {'instagram.com':'instagram','tiktok.com':'tiktok','facebook.com':'facebook','m.facebook.com':'facebook','x.com':'x','twitter.com':'x','threads.com':'threads','threads.net':'threads'};
let activeRequest = null;
let media = [];
let currentFilter = 'all';
function status(message, state = '') { $('#status').textContent = message; $('#status').className = `status ${state}`; }
function detect(value) { try { return hostPlatforms[new URL(value).hostname.replace(/^www\./, '')]; } catch { return null; } }
$('#url').addEventListener('input', () => { const platform = detect($('#url').value); $('#detected').replaceChildren(platform ? platformLogo(platform) : document.createTextNode('Deteksi otomatis')); });
$('#paste').addEventListener('click', async () => {
  try { $('#url').value = await navigator.clipboard.readText(); $('#url').dispatchEvent(new Event('input')); $('#url').focus(); }
  catch { status('Akses clipboard tidak tersedia. Tempel manual dengan Ctrl+V atau Cmd+V.', 'error'); $('#url').focus(); }
});
function busy(value) {
  $('#submit').disabled = value;
  $('#url').readOnly = value;
  $('#paste').disabled = value;
  $('#cancel').hidden = !value;
  $('#results-section').setAttribute('aria-busy', String(value));
}
$('#cancel').addEventListener('click', () => activeRequest?.abort());
$('#resolve-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  if (activeRequest) return;
  media = []; render();
  $('#warnings').hidden = true; $('#result-caption').hidden = true;
  if (!detect($('#url').value.trim())) { status('Gunakan URL postingan Instagram, TikTok, Facebook, X, atau Threads.', 'error'); return; }
  const controller = new AbortController(); activeRequest = controller;
  const timeout = setTimeout(() => controller.abort('timeout'), 28000);
  busy(true); status('Mencari media di sumber. Proses dapat memerlukan hingga 23 detik…', 'loading');
  try {
    const response = await fetch('/api/resolve', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({url:$('#url').value.trim()}), signal:controller.signal});
    let data;
    try { data = await response.json(); } catch { throw new Error('Server tidak memberikan hasil yang valid. Coba lagi nanti.'); }
    if (!response.ok || !data.ok) throw new Error(data.error || 'Media tidak dapat diproses.');
    media = data.items; currentFilter = 'all';
    $('#warnings').replaceChildren();
    for (const warning of data.warnings) { const p = document.createElement('p'); p.textContent = warning; $('#warnings').append(p); }
    $('#warnings').hidden = !data.warnings.length;
    $('#result-caption').replaceChildren(platformLogo(data.platform), document.createTextNode(data.title)); $('#result-caption').hidden = false;
    render(); status(`${media.length} berkas ditemukan. Pilih media yang ingin disimpan.`);
  } catch (error) { status(controller.signal.aborted ? (controller.signal.reason === 'timeout' ? 'Waktu tunggu habis. Coba lagi dengan postingan lain.' : 'Pencarian dibatalkan. Anda bisa memasukkan tautan lain.') : error.message, 'error'); }
  finally { clearTimeout(timeout); activeRequest = null; busy(false); }
});
function element(tag, className, text) { const node = document.createElement(tag); if (className) node.className = className; if (text) node.textContent = text; return node; }
function platformLogo(key) { const image = document.createElement('img'); image.src = `/icons/${key}.svg`; image.alt = names[key]; image.title = names[key]; image.width = 24; image.height = 24; image.className = 'platform-icon'; return image; }
function safeMediaURL(value) { try { const url = new URL(value); return url.protocol === 'https:' && !url.username && !url.password; } catch { return false; } }
function render() {
  $('#count').textContent = media.length; $('#filters').hidden = !media.length; $('#download-note').hidden = !media.length;
  $('#empty').hidden = !!media.length; $('#media-grid').replaceChildren();
  document.querySelectorAll('[data-filter]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.filter === currentFilter)));
  const visible = media.filter(item => currentFilter === 'all' || item.type === currentFilter);
  if (media.length && !visible.length) { $('#media-grid').append(element('p', 'result-caption', 'Tidak ada media dengan jenis ini. Pilih filter lainnya.')); return; }
  visible.forEach(item => {
    if (!safeMediaURL(item.url)) return;
    const index = media.indexOf(item) + 1;
    const card = element('article', 'media-card'), preview = element('div', 'media-preview');
    const visual = document.createElement(item.type === 'image' ? 'img' : item.type);
    visual.src = item.url;
    if (item.type === 'image') { visual.alt = `Foto ${index} dari postingan`; visual.loading = 'lazy'; visual.referrerPolicy = 'no-referrer'; }
    else { visual.controls = true; visual.preload = 'none'; visual.setAttribute('aria-label', `${item.label} ${index}`); if (item.type === 'video') visual.playsInline = true; }
    visual.addEventListener('error', () => preview.replaceChildren(element('p', 'result-caption', 'Pratinjau tidak tersedia. Coba buka berkas.')), {once:true});
    preview.append(visual); card.append(preview);
    const info = element('div', 'media-info'); info.append(element('h3', '', `${String(index).padStart(2,'0')} / ${item.label}`));
    info.append(element('p', '', (item.width && item.height ? `${item.width} × ${item.height} · ` : '') + 'Tanpa kompresi ulang'));
    const download = element('button', 'primary', 'Unduh berkas'); download.type = 'button'; download.setAttribute('aria-label', `Unduh ${item.label} ${index}`);
    const message = element('p', 'media-message'); message.setAttribute('role','status');
    download.addEventListener('click', () => downloadMedia(item, index, download, message));
    const links = element('div', 'media-links'), open = element('a', '', 'Buka berkas'); open.href = item.url; open.target = '_blank'; open.rel = 'noopener noreferrer';
    const copy = element('button', '', 'Salin tautan'); copy.type = 'button'; copy.setAttribute('aria-label', `Salin tautan media ${index}`);
    copy.addEventListener('click', async () => { try { await navigator.clipboard.writeText(item.url); message.textContent = 'Tautan media disalin.'; } catch { message.textContent = 'Clipboard diblokir. Klik kanan atau tekan lama “Buka berkas” untuk menyalin tautan.'; } });
    links.append(open, copy); info.append(download, links, message); card.append(info); $('#media-grid').append(card);
  });
}
async function downloadMedia(item, index, button, message) {
  button.disabled = true; message.textContent = 'Menghubungkan ke sumber…';
  const controller = new AbortController(); const timer = setTimeout(() => controller.abort(), 90000);
  try {
    const response = await fetch(item.url, {signal:controller.signal, credentials:'omit', referrerPolicy:'no-referrer'});
    if (!response.ok) throw new Error('Sumber menolak unduhan.');
    const mime = response.headers.get('content-type')?.split(';')[0] || '';
    if (!/^(image|video|audio)\//.test(mime)) throw new Error('Sumber tidak mengembalikan berkas media.');
    const limit = 150 * 1024 * 1024;
    if (Number(response.headers.get('content-length')) > limit) throw new Error('Berkas lebih dari 150 MB.');
    const reader = response.body.getReader(), chunks = []; let bytes = 0;
    while (true) { const {done, value} = await reader.read(); if (done) break; bytes += value.length; if (bytes > limit) { await reader.cancel(); throw new Error('Berkas lebih dari 150 MB.'); } chunks.push(value); message.textContent = `Mengunduh ${(bytes / 1048576).toFixed(1)} MB…`; }
    const blobURL = URL.createObjectURL(new Blob(chunks, {type:mime}));
    const extensions = {'image/jpeg':'jpg','image/png':'png','image/webp':'webp','image/avif':'avif','image/gif':'gif','video/mp4':'mp4','video/webm':'webm','audio/mp4':'m4a','audio/mpeg':'mp3'};
    const link = document.createElement('a'); link.href = blobURL; link.download = `sosmed-${index}.${(item.type === 'audio' && mime === 'video/mp4' ? 'm4a' : extensions[mime]) || 'bin'}`; document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(blobURL), 60000);
    message.textContent = 'Berkas dikirim ke pengelola unduhan browser.';
  } catch { controller.abort(); message.textContent = 'Unduhan langsung dibatasi atau berkas terlalu besar. Pilih “Buka berkas”, lalu simpan lewat menu browser.'; }
  finally { clearTimeout(timer); button.disabled = false; }
}
$('#filters').addEventListener('click', event => { const button = event.target.closest('[data-filter]'); if (button) { currentFilter = button.dataset.filter; render(); } });
fetch('/support.json').then(response => { if (!response.ok) throw new Error(); return response.json(); }).then(data => {
  $('#support-list').replaceChildren();
  for (const platform of data.platforms) {
    const item = element('div','support-item'); const heading = element('h3'); heading.append(platformLogo(Object.keys(names).find(key => names[key] === platform.name))); item.append(heading, element('span',`badge ${platform.verified ? 'verified' : ''}`,platform.status), element('p','',platform.note)); $('#support-list').append(item);
  }
}).catch(() => { $('#support-list').textContent = 'Status pengujian tidak dapat dimuat. Seluruh platform dianggap eksperimental.'; });
