const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const paths = {
  book: '<path d="M12 5c-3-2-6-2-9-1v15c3-1 6-1 9 1 3-2 6-2 9-1V4c-3-1-6-1-9 1Z"/><path d="M12 5v15M6 8h3M6 11h3M15 8h3M15 11h3"/>',
  'book-open':
    '<path d="M12 5c-3-2-6-2-9-1v15c3-1 6-1 9 1 3-2 6-2 9-1V4c-3-1-6-1-9 1Z"/><path d="M12 5v15"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  search: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 4.5 4.5"/>',
  settings:
    '<path d="m9 3-.6 2.2-2 .9-2.1-.6-2 3.4 1.6 1.6v2.4L2.3 15l2 3.4 2.1-.6 2 .9L9 21h4l.6-2.3 2-.9 2.1.6 2-3.4-1.6-2.1v-2.4l1.6-1.6-2-3.4-2.1.6-2-.9L13 3Z"/><circle cx="11" cy="12" r="3"/>',
  panels: '<rect x="4" y="4" width="16" height="16" rx="3"/><path d="M15 4v16"/>',
  file: '<path d="M14 3H5v18h14V8Z"/><path d="M14 3v5h5M8 12h8M8 15h6"/>',
  files: '<path d="M14 2H6v16h14V8Z"/><path d="M14 2v6h6M9 12h7M9 15h4M3 6v16h13"/>',
  upload: '<path d="M12 16V3m-5 5 5-5 5 5M4 16v5h16v-5"/>',
  shield: '<path d="m12 2 8 3v6c0 5-4 8-8 11-4-3-8-6-8-11V5Z"/><path d="m8 11 3 3 5-5"/>',
  edit: '<path d="m14 5 5 5M4 20l5-1L21 7l-5-5L4 14Z"/>',
  sparkles:
    '<path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5ZM4 2v4M2 4h4M20 18v4M18 20h4"/>',
  messages: '<path d="M20 14V4H3v13l4-3Z"/><path d="M8 18h9l4 3V9"/>',
  layers: '<path d="m12 3 10 5-10 5L2 8Zm-9 9 9 5 9-5M3 16l9 5 9-5"/>',
  compass: '<circle cx="12" cy="12" r="9"/><path d="m16 8-3 5-5 3 3-5Z"/>',
  'arrow-up-right': '<path d="M6 18 18 6M6 6h12v12"/>',
  'arrow-right': '<path d="M4 12h16m-6-6 6 6-6 6"/>',
  'arrow-up': '<path d="M12 20V4m-6 6 6-6 6 6"/>',
  stack: '<rect x="4" y="3" width="12" height="15" rx="2"/><path d="M9 21h11V8M7 7h6M7 11h6"/>',
  'align-left': '<path d="M4 5h16M4 10h11M4 15h16M4 20h11"/>',
  'circle-help':
    '<circle cx="12" cy="12" r="9"/><path d="M9 8a3 3 0 1 1 5 2c-2 1-2 2-2 3M12 16v1"/>',
  sprout: '<path d="M12 22v-9C5 14 3 10 3 5c6 0 9 2 9 8Zm0 2C12 7 15 3 22 3c0 6-3 11-10 12Z"/>',
  cpu: '<rect x="5" y="5" width="14" height="14" rx="3"/><rect x="9" y="9" width="6" height="6" rx="1"/><path d="M9 2v3M15 2v3M9 19v3M15 19v3M2 9h3M2 15h3M19 9h3M19 15h3"/>',
  x: '<path d="m6 6 12 12M6 18 18 6"/>',
  check: '<path d="m4 12 5 5L20 6"/>',
  download: '<path d="M12 3v13m-5-5 5 5 5-5M4 16v5h16v-5"/>',
};
const icon = (name) =>
  `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name] || paths.file}</svg>`;
const escapeHTML = (text) =>
  String(text ?? '').replace(
    /[&<>"']/g,
    (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c],
  );
const storage = {
  get(key, fallback) {
    try {
      return JSON.parse(localStorage.getItem(`studybook.${key}`)) ?? fallback;
    } catch {
      return fallback;
    }
  },
  set(key, value) {
    try {
      localStorage.setItem(`studybook.${key}`, JSON.stringify(value));
    } catch {
      /* The app works without browser storage. */
    }
  },
};
const state = {
  documents: [],
  selected: new Set(),
  artifacts: [],
  history: [],
  messages: [],
  settings: null,
  busy: false,
  uploading: false,
  title: storage.get('title', 'My notebook'),
};
const names = {
  summary: 'Summary',
  study_guide: 'Study guide',
  flashcards: 'Flashcards',
  quiz: 'Practice quiz',
};
const kindIcons = {
  summary: 'align-left',
  study_guide: 'book-open',
  flashcards: 'layers',
  quiz: 'circle-help',
};
let toastTimer;

function drawIcons(root = document) {
  $$('[data-icon]', root).forEach((el) => {
    el.innerHTML = icon(el.dataset.icon);
  });
}
function toast(message, error = false) {
  const el = $('#toast');
  el.textContent = message;
  el.classList.toggle('error', error);
  el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(
    () => {
      el.hidden = true;
    },
    error ? 9000 : 4500,
  );
}
async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (options.body && !(options.body instanceof FormData))
    headers.set('Content-Type', 'application/json');
  let response;
  try {
    response = await fetch(`/api${path}`, { ...options, headers });
  } catch {
    throw new Error(
      'The local dashboard server is unavailable. Start Studybook and refresh this page.',
    );
  }
  const result = await response.json().catch(() => ({}));
  if (!response.ok)
    throw new Error(
      typeof result.error === 'string'
        ? result.error
        : typeof result.detail === 'string'
          ? result.detail
          : `This request couldn’t be completed (${response.status}).`,
    );
  return result;
}
function setTitle(title) {
  state.title = title.trim() || 'My notebook';
  storage.set('title', state.title);
  $('#notebook-title').textContent = state.title;
  $('#breadcrumb-title').textContent = state.title;
  document.title = `${state.title} — Studybook`;
}
function formatBytes(bytes) {
  return bytes < 1024
    ? `${bytes} B`
    : bytes < 1024 * 1024
      ? `${(bytes / 1024).toFixed(1)} KB`
      : `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}
function formatDate(value) {
  return new Date(value).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}
function renderSources() {
  const query = $('#source-search').value.toLowerCase();
  $('#source-list').innerHTML = state.documents
    .filter((d) => d.name.toLowerCase().includes(query))
    .map(
      (d) => `
    <div class="source-row"><span class="file-symbol ${escapeHTML(d.kind)}">${icon('file')}</span><button class="source-name" data-source="${escapeHTML(d.id)}" title="Read ${escapeHTML(d.name)}"><strong>${escapeHTML(d.name)}</strong><small>${d.kind === 'pdf' ? `${d.pages} page${d.pages === 1 ? '' : 's'}` : d.kind === 'markdown' ? 'Markdown' : 'Text document'} · ${formatBytes(d.size)}</small></button><input type="checkbox" aria-label="Include ${escapeHTML(d.name)}" data-select="${escapeHTML(d.id)}" ${state.selected.has(d.id) ? 'checked' : ''} ${state.busy ? 'disabled' : ''}></div>`,
    )
    .join('');
  const count = state.documents.length,
    selected = state.selected.size;
  $('#source-count').textContent = count;
  $('#mobile-source-count').textContent = count;
  $('#source-empty').hidden = count > 0;
  $('#selected-count').textContent = `${selected} selected`;
  $('#select-all').checked = count > 0 && selected === count;
  $('#select-all').indeterminate = selected > 0 && selected < count;
  $('#select-all').disabled = !count || state.busy;
  $('#intro-source-count').textContent = count
    ? `${count} source${count === 1 ? '' : 's'}`
    : 'No sources yet';
  $('#composer-sources').innerHTML =
    `${icon('stack')}<span>${selected} source${selected === 1 ? '' : 's'} selected</span>`;
  $('#welcome').hidden = count > 0;
  $('#ready-notice').hidden = count === 0 || state.messages.length > 0;
  $('#send-button').disabled = !selected || state.busy;
  $$('[data-generate]').forEach((button) => {
    button.disabled = state.busy;
  });
}
function selectionChanged() {
  storage.set('selection', [...state.selected]);
  if (state.messages.length) {
    state.history = [];
    state.messages = [];
    renderMessages();
    toast('Source selection updated. A fresh conversation keeps answers scoped to your choices.');
  }
  renderSources();
}
async function loadDocuments(first = false) {
  const { documents } = await api('/documents');
  state.documents = documents;
  if (first) {
    const saved = storage.get('selection', null);
    state.selected = new Set(
      saved === null
        ? documents.map((d) => d.id)
        : saved.filter((id) => documents.some((d) => d.id === id)),
    );
  } else
    state.selected = new Set(
      [...state.selected].filter((id) => documents.some((d) => d.id === id)),
    );
  renderSources();
}
async function uploadFiles(files) {
  if (state.uploading || state.busy) {
    toast('Let the current task finish before adding sources.');
    return;
  }
  if (!files.length) return;
  if (files.length > 20) {
    toast('Choose up to 20 files at a time.', true);
    return;
  }
  const valid = [...files].filter((file) => {
    if (!/\.(pdf|txt|md|markdown)$/i.test(file.name)) {
      toast(`${file.name}: choose a PDF, TXT, or Markdown file.`, true);
      return false;
    }
    if (file.size > 25 * 1024 * 1024) {
      toast(`${file.name}: files must be 25 MB or smaller.`, true);
      return false;
    }
    return true;
  });
  if (!valid.length) return;
  state.uploading = true;
  const button = $('.source-tools>.upload-trigger');
  button.disabled = true;
  button.innerHTML = '<span class="spinner"></span> Indexing sources…';
  const form = new FormData();
  valid.forEach((file) => form.append('files', file));
  try {
    const result = await api('/documents', { method: 'POST', body: form });
    result.documents.forEach((d) => state.selected.add(d.id));
    await loadDocuments();
    selectionChanged();
    const fresh = result.documents.filter((d) => !d.duplicate).length,
      duplicates = result.documents.length - fresh;
    const errors = result.errors.map((e) => `${e.name}: ${e.error}`);
    if (errors.length) toast(errors.join(' '), true);
    else
      toast(
        `${fresh ? `${fresh} source${fresh === 1 ? '' : 's'} added. ` : ''}${duplicates ? `${duplicates} already in your notebook.` : 'Ready to explore.'}`,
      );
  } catch (error) {
    toast(error.message, true);
  } finally {
    state.uploading = false;
    button.disabled = false;
    button.innerHTML = `${icon('plus')} Add sources`;
    $('#file-input').value = '';
  }
}
async function loadSamples() {
  const button = $('#sample-button');
  button.disabled = true;
  try {
    const filenames = [
      '01-learning-plan.md',
      '02-glossary-notebook.md',
      '03-interpreting-practice.md',
    ];
    const files = await Promise.all(
      filenames.map(async (name) => {
        const response = await fetch(`/examples/${name}`);
        if (!response.ok) throw new Error('The sample sources could not be loaded.');
        return new File([await response.text()], name, { type: 'text/markdown' });
      }),
    );
    await uploadFiles(files);
    if (state.documents.length && state.title === 'My notebook')
      setTitle('The language learning notebook');
  } catch (error) {
    toast(error.message, true);
  } finally {
    button.disabled = false;
  }
}

// This small renderer intentionally supports a safe subset of Markdown. Every
// character is escaped first; source/model text cannot insert HTML or load URLs.
function markdown(text, scope, citations = []) {
  const allowed = new Set(citations.map((c) => c.id));
  const inline = (value) =>
    escapeHTML(value)
      .replace(/`([^`\n]+)`/g, '<code>$1</code>')
      .replace(/\*\*([^*\n]+)\*\*/g, '<strong>$1</strong>')
      .replace(/\*([^*\n]+)\*/g, '<em>$1</em>')
      .replace(/\[(S\d+)\]/gi, (match, id) =>
        allowed.has(id.toUpperCase())
          ? `<button class="citation-inline" data-citation="${id.toUpperCase()}" data-scope="${escapeHTML(scope)}" aria-label="Read source ${id.toUpperCase()}">${id.toUpperCase()}</button>`
          : match,
      );
  let html = '',
    list = '',
    code = false,
    buffer = [];
  const closeList = () => {
    if (list) {
      html += `</${list}>`;
      list = '';
    }
  };
  for (const line of String(text).split('\n')) {
    if (/^\s*```/.test(line)) {
      closeList();
      if (code) {
        html += `<pre><code>${escapeHTML(buffer.join('\n'))}</code></pre>`;
        buffer = [];
      }
      code = !code;
      continue;
    }
    if (code) {
      buffer.push(line);
      continue;
    }
    const heading = /^(#{1,4})\s+(.+)$/.exec(line),
      item = /^\s*([-*]|\d+[.)])\s+(.+)$/.exec(line);
    if (heading) {
      closeList();
      const level = Math.min(4, heading[1].length + 1);
      html += `<h${level}>${inline(heading[2])}</h${level}>`;
    } else if (item) {
      const tag = /^\d/.test(item[1]) ? 'ol' : 'ul';
      if (tag !== list) {
        closeList();
        html += `<${tag}>`;
        list = tag;
      }
      html += `<li>${inline(item[2])}</li>`;
    } else {
      closeList();
      if (/^\s*---+\s*$/.test(line)) html += '<div class="intro-rule"></div>';
      else if (line.trim()) html += `<p>${inline(line)}</p>`;
    }
  }
  closeList();
  if (buffer.length) html += `<pre><code>${escapeHTML(buffer.join('\n'))}</code></pre>`;
  return html;
}
function citationList(citations, scope) {
  return citations.length
    ? `<div class="citation-list">${citations.map((c) => `<button class="citation-chip" data-citation="${escapeHTML(c.id)}" data-scope="${escapeHTML(scope)}" title="Read source excerpt">${escapeHTML(c.id)} · ${escapeHTML(c.document_name)} · p. ${c.page}</button>`).join('')}</div>`
    : '';
}
function renderMessages() {
  $('#messages').innerHTML = state.messages
    .map((m, i) => {
      if (m.role === 'user') return `<div class="message user">${escapeHTML(m.content)}</div>`;
      if (m.error)
        return `<div class="message error">${escapeHTML(m.content)} <button class="text-button" data-open-settings>Open settings ${icon('arrow-right')}</button></div>`;
      if (m.pending)
        return '<div class="message pending"><span class="spinner"></span> Reading between your sources…</div>';
      return `<div class="message assistant"><div class="message-label">${icon('sparkles')} Studybook</div><div class="markdown">${markdown(m.content, `message-${i}`, m.citations)}</div>${citationList(m.citations, `message-${i}`)}${m.warnings?.length ? `<p class="message-warnings">${m.warnings.map(escapeHTML).join(' ')}</p>` : ''}</div>`;
    })
    .join('');
  $('#ready-notice').hidden = !state.documents.length || state.messages.length > 0;
  $('#conversation-scroll').scrollTop = $('#conversation-scroll').scrollHeight;
}
async function sendMessage(event) {
  event.preventDefault();
  const input = $('#message-input'),
    message = input.value.trim();
  if (!message || state.busy) return;
  if (!state.selected.size) {
    toast('Add and select at least one source first.');
    return;
  }
  if (message.length > 8000) {
    toast('Keep your question under 8,000 characters.', true);
    return;
  }
  state.busy = true;
  state.messages.push({ role: 'user', content: message }, { role: 'assistant', pending: true });
  input.value = '';
  input.style.height = '';
  renderSources();
  renderMessages();
  try {
    const result = await api('/chat', {
      method: 'POST',
      body: JSON.stringify({
        message,
        document_ids: [...state.selected],
        history: state.history.slice(-12),
      }),
    });
    state.messages.pop();
    state.messages.push({
      role: 'assistant',
      content: result.answer,
      citations: result.citations,
      warnings: result.warnings,
    });
    state.history.push(
      { role: 'user', content: message },
      { role: 'assistant', content: result.answer.slice(0, 8000) },
    );
    refreshHealth();
  } catch (error) {
    state.messages.pop();
    state.messages.push({ role: 'assistant', error: true, content: error.message });
    if (!input.value) input.value = message;
  } finally {
    state.busy = false;
    renderSources();
    renderMessages();
    input.focus();
  }
}
function renderArtifacts() {
  $('#artifact-count').textContent = state.artifacts.length;
  $('#artifact-empty').hidden = state.artifacts.length > 0;
  $('#artifact-list').innerHTML = state.artifacts
    .map(
      (a) =>
        `<button class="artifact-row" data-artifact="${escapeHTML(a.id)}">${icon(kindIcons[a.kind])}<div><strong>${escapeHTML(a.title)}</strong><small>${escapeHTML(names[a.kind] || a.kind)} · ${formatDate(a.created_at)}</small></div></button>`,
    )
    .join('');
}
async function generate(kind) {
  if (state.busy) return;
  if (!state.selected.size) {
    toast('Add and select a source to create study materials.');
    return;
  }
  state.busy = true;
  renderSources();
  const button = $(`[data-generate="${kind}"]`),
    original = button.innerHTML;
  button.innerHTML = `<span class="spinner"></span><strong>Creating…</strong><small>This can take a moment</small>`;
  try {
    const artifact = await api('/studio', {
      method: 'POST',
      body: JSON.stringify({ kind, document_ids: [...state.selected] }),
    });
    state.artifacts.unshift(artifact);
    renderArtifacts();
    showArtifact(artifact);
    refreshHealth();
  } catch (error) {
    toast(error.message, true);
  } finally {
    state.busy = false;
    button.innerHTML = original;
    renderSources();
  }
}
function showDialog(dialog) {
  if (!dialog.open) dialog.showModal();
}
async function readSource(id, citation) {
  try {
    const result = await api(`/documents/${encodeURIComponent(id)}/content`);
    $('#reader-title').textContent = result.document.name;
    $('#reader-eyebrow').textContent = citation
      ? `SOURCE ${citation.id} · CITED EXCERPT`
      : 'SOURCE DOCUMENT';
    $('#reader-meta').textContent =
      `${result.document.pages} page${result.document.pages === 1 ? '' : 's'} · ${result.document.chunks} indexed excerpts · ${formatBytes(result.document.size)}`;
    $('#reader-content').innerHTML =
      `${citation ? `<div class="citation-excerpt"><strong>Page ${citation.page} · excerpt ${citation.chunk}</strong><p>${escapeHTML(citation.excerpt)}</p></div>` : ''}${result.pages.map((p) => `<section class="source-page ${citation?.page === p.page ? 'highlight-page' : ''}"><h3>Page ${p.page}</h3><pre>${escapeHTML(p.text || 'No extractable text on this page.')}</pre></section>`).join('')}`;
    $('#reader-actions').innerHTML =
      `<button class="button danger" data-remove-source="${escapeHTML(id)}">Remove source</button><a class="button secondary" href="/api/documents/${encodeURIComponent(id)}/file" download>${icon('download')} Download original</a>`;
    showDialog($('#reader-dialog'));
    $('#reader-dialog').scrollTop = 0;
  } catch (error) {
    toast(error.message, true);
  }
}
function showArtifact(artifact) {
  $('#reader-title').textContent = artifact.title;
  $('#reader-eyebrow').textContent = 'YOUR CREATIONS';
  $('#reader-meta').textContent =
    `${names[artifact.kind]} · Created ${formatDate(artifact.created_at)} · ${artifact.document_ids?.length || '?'} sources`;
  $('#reader-content').innerHTML =
    `<div class="markdown">${markdown(artifact.content, `artifact-${artifact.id}`, artifact.citations)}</div>${citationList(artifact.citations, `artifact-${artifact.id}`)}`;
  $('#reader-actions').innerHTML =
    `<button class="button danger" data-remove-artifact="${escapeHTML(artifact.id)}">Delete creation</button><a class="button secondary" href="/api/studio/${encodeURIComponent(artifact.id)}/export" download>${icon('download')} Export Markdown</a>`;
  showDialog($('#reader-dialog'));
  $('#reader-dialog').scrollTop = 0;
}
async function removeSource(id, button) {
  if (state.busy) {
    toast('Let the current generation finish first.');
    return;
  }
  if (button.dataset.confirmed !== 'true') {
    button.dataset.confirmed = 'true';
    button.textContent = 'Remove from this notebook?';
    return;
  }
  button.disabled = true;
  try {
    await api(`/documents/${encodeURIComponent(id)}`, { method: 'DELETE' });
    state.selected.delete(id);
    await loadDocuments();
    selectionChanged();
    $('#reader-dialog').close();
    toast('Source removed from this notebook.');
  } catch (error) {
    toast(error.message, true);
    button.disabled = false;
  }
}
async function removeArtifact(id, button) {
  if (button.dataset.confirmed !== 'true') {
    button.dataset.confirmed = 'true';
    button.textContent = 'Permanently delete creation?';
    return;
  }
  button.disabled = true;
  try {
    await api(`/studio/${encodeURIComponent(id)}`, { method: 'DELETE' });
    state.artifacts = state.artifacts.filter((a) => a.id !== id);
    renderArtifacts();
    $('#reader-dialog').close();
    toast('Creation deleted.');
  } catch (error) {
    toast(error.message, true);
    button.disabled = false;
  }
}
async function openSettings() {
  try {
    const settings = await api('/settings');
    state.settings = settings;
    $('#endpoint-input').value = settings.base_url;
    $('#model-input').value = settings.model;
    $('#embedding-select').value = settings.embedding_mode;
    $('#embedding-input').value = settings.embedding_model;
    $('#embedding-model-field').hidden = settings.embedding_mode !== 'local_openai';
    $('#api-key-input').value = '';
    $('#connection-result').hidden = true;
    showDialog($('#settings-dialog'));
  } catch (error) {
    toast(error.message, true);
  }
}
async function saveSettings(event) {
  event.preventDefault();
  const button = $('button[type=submit]', event.target);
  button.disabled = true;
  const data = {
    base_url: $('#endpoint-input').value.trim(),
    model: $('#model-input').value.trim(),
    embedding_mode: $('#embedding-select').value,
    embedding_model: $('#embedding-input').value.trim() || 'local-embedding-model',
  };
  if ($('#api-key-input').value) data.api_key = $('#api-key-input').value;
  try {
    state.settings = await api('/settings', { method: 'PUT', body: JSON.stringify(data) });
    $('#settings-dialog').close();
    toast('Settings saved. Your model was not contacted.');
    refreshHealth();
  } catch (error) {
    const result = $('#connection-result');
    result.hidden = false;
    result.classList.add('error');
    result.textContent = error.message;
  } finally {
    button.disabled = false;
  }
}
async function testConnection() {
  const button = $('#test-connection'),
    result = $('#connection-result');
  button.disabled = true;
  result.hidden = false;
  result.classList.remove('error');
  result.textContent = 'Checking the saved local endpoint…';
  try {
    const data = await api('/connection', { method: 'POST' });
    result.textContent = `${data.message || 'Local endpoint connected.'}${data.models?.length ? ` Available model IDs: ${data.models.join(', ')}` : ''}`;
  } catch (error) {
    result.classList.add('error');
    result.textContent = error.message;
  } finally {
    button.disabled = false;
    refreshHealth();
  }
}
async function refreshHealth() {
  try {
    const health = await api('/health');
    $('#model-status').textContent = health.model_connected
      ? 'Local API connected'
      : 'Model not connected';
    $('#model-dot').classList.toggle('connected', !!health.model_connected);
  } catch {
    $('#model-status').textContent = 'Dashboard server unavailable';
    $('#model-dot').classList.remove('connected');
  }
}

drawIcons();
setTitle(state.title);
$$('.upload-trigger').forEach((button) =>
  button.addEventListener('click', () => $('#file-input').click()),
);
$('#file-input').addEventListener('change', (event) => uploadFiles(event.target.files));
$('#source-search').addEventListener('input', renderSources);
$('#select-all').addEventListener('change', (event) => {
  state.selected = new Set(event.target.checked ? state.documents.map((d) => d.id) : []);
  selectionChanged();
});
$('#source-list').addEventListener('change', (event) => {
  const id = event.target.dataset.select;
  if (!id) return;
  event.target.checked ? state.selected.add(id) : state.selected.delete(id);
  selectionChanged();
});
$('#sample-button').addEventListener('click', loadSamples);
$('#chat-form').addEventListener('submit', sendMessage);
$('#message-input').addEventListener('keydown', (event) => {
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    $('#chat-form').requestSubmit();
  }
});
$('#message-input').addEventListener('input', (event) => {
  event.target.style.height = 'auto';
  event.target.style.height = `${Math.min(135, event.target.scrollHeight)}px`;
});
$('#settings-button').addEventListener('click', openSettings);
$('#configure-button').addEventListener('click', openSettings);
$('#settings-form').addEventListener('submit', saveSettings);
$('#test-connection').addEventListener('click', testConnection);
$('#embedding-select').addEventListener('change', (event) => {
  $('#embedding-model-field').hidden = event.target.value !== 'local_openai';
});
$('#rename-button').addEventListener('click', () => {
  $('#notebook-name-input').value = state.title;
  showDialog($('#rename-dialog'));
  $('#notebook-name-input').select();
});
$('#rename-form').addEventListener('submit', (event) => {
  event.preventDefault();
  setTitle($('#notebook-name-input').value);
  $('#rename-dialog').close();
});
$$('.close-dialog').forEach((button) =>
  button.addEventListener('click', () => button.closest('dialog').close()),
);
$$('dialog').forEach((dialog) =>
  dialog.addEventListener('click', (event) => {
    const bounds = dialog.getBoundingClientRect();
    if (
      event.target === dialog &&
      (event.clientX < bounds.left ||
        event.clientX > bounds.right ||
        event.clientY < bounds.top ||
        event.clientY > bounds.bottom)
    )
      dialog.close();
  }),
);
document.addEventListener('click', (event) => {
  const source = event.target.closest('[data-source]'),
    prompt = event.target.closest('[data-prompt]'),
    generator = event.target.closest('[data-generate]'),
    artifact = event.target.closest('[data-artifact]'),
    citation = event.target.closest('[data-citation]');
  if (source) readSource(source.dataset.source);
  if (prompt) {
    $('#message-input').value = prompt.dataset.prompt;
    $('#message-input').focus();
  }
  if (generator) generate(generator.dataset.generate);
  if (artifact) showArtifact(state.artifacts.find((a) => a.id === artifact.dataset.artifact));
  if (citation) {
    const scope = citation.dataset.scope,
      item = scope.startsWith('message-')
        ? state.messages[Number(scope.slice(8))]
        : state.artifacts.find((a) => a.id === scope.slice(9));
    const ref = item?.citations.find((c) => c.id === citation.dataset.citation);
    if (ref) readSource(ref.document_id, ref);
  }
  const remove = event.target.closest('[data-remove-source]');
  if (remove) removeSource(remove.dataset.removeSource, remove);
  const removeCreation = event.target.closest('[data-remove-artifact]');
  if (removeCreation) removeArtifact(removeCreation.dataset.removeArtifact, removeCreation);
  if (event.target.closest('[data-open-settings]')) openSettings();
  const tab = event.target.closest('[data-panel]');
  if (tab) {
    $('.workspace').dataset.tab = tab.dataset.panel;
    $$('[data-panel]').forEach((b) => b.classList.toggle('active', b === tab));
  }
});
document.addEventListener('keydown', (event) => {
  if (
    event.key === '/' &&
    !/INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName) &&
    !document.querySelector('dialog[open]')
  ) {
    event.preventDefault();
    $('#source-search').focus();
  }
});
let dragDepth = 0;
document.addEventListener('dragenter', (event) => {
  if (event.dataTransfer.types.includes('Files')) {
    event.preventDefault();
    dragDepth++;
    $('#global-drop').hidden = false;
  }
});
document.addEventListener('dragover', (event) => {
  if (event.dataTransfer.types.includes('Files')) event.preventDefault();
});
document.addEventListener('dragleave', (event) => {
  event.preventDefault();
  if (--dragDepth <= 0) {
    dragDepth = 0;
    $('#global-drop').hidden = true;
  }
});
document.addEventListener('drop', (event) => {
  event.preventDefault();
  dragDepth = 0;
  $('#global-drop').hidden = true;
  if (event.dataTransfer.files.length) uploadFiles(event.dataTransfer.files);
});
window.addEventListener('blur', () => {
  dragDepth = 0;
  $('#global-drop').hidden = true;
});

async function initialize() {
  renderSources();
  const results = await Promise.allSettled([
    loadDocuments(true),
    api('/studio').then((result) => {
      state.artifacts = result.artifacts;
      renderArtifacts();
    }),
    refreshHealth(),
  ]);
  const failure = results.find((r) => r.status === 'rejected');
  if (failure) toast(failure.reason.message, true);
}
initialize();
