import { api, fmt } from '/web/app.js';

export default async function (root) {
  const id = decodeURIComponent(location.hash.split('/')[2] || '');
  if (!id) return renderList(root);
  return renderSession(root, id);
}

async function renderList(root) {
  const list = await api('/api/sessions?limit=100');
  let sortCol = 'started', sortDir = -1;

  function render() {
    const sorted = [...list].sort((a, b) => {
      const av = a[sortCol], bv = b[sortCol];
      if (av == null) return 1; if (bv == null) return -1;
      return (av < bv ? -1 : av > bv ? 1 : 0) * sortDir;
    });
    const th = (col, label, cls = '') =>
      `<th class="${cls}sortable" data-col="${col}">${label}${col === sortCol ? (sortDir > 0 ? ' ↑' : ' ↓') : ''}</th>`;

    root.innerHTML = `
      <div class="card">
        <h2>Sessions</h2>
        <table>
          <thead><tr>
            ${th('started', 'started')}
            <th>project</th>
            ${th('turns', 'turns', 'num ')}
            ${th('tokens', 'tokens', 'num ')}
            <th>session</th>
          </tr></thead>
          <tbody>
            ${sorted.map(s => `
              <tr>
                <td class="mono">${fmt.ts(s.started)}</td>
                <td title="${fmt.htmlSafe(s.project_slug)}">${fmt.htmlSafe(s.project_name || s.project_slug)}</td>
                <td class="num">${fmt.int(s.turns)}</td>
                <td class="num">${fmt.int(s.tokens)}</td>
                <td><a href="#/sessions/${encodeURIComponent(s.session_id)}" class="mono">${fmt.htmlSafe(s.session_id.slice(0,8))}…</a></td>
              </tr>`).join('')}
          </tbody>
        </table>
      </div>`;

    root.querySelectorAll('th.sortable').forEach(el => {
      el.addEventListener('click', () => {
        if (sortCol === el.dataset.col) sortDir *= -1;
        else { sortCol = el.dataset.col; sortDir = -1; }
        render();
      });
    });
  }

  render();
}

async function renderSession(root, id) {
  const turns = await api('/api/sessions/' + encodeURIComponent(id));
  let totalIn = 0, totalOut = 0, totalCacheRd = 0;
  let modelCounts = {};
  for (const t of turns) {
    if (t.type !== 'assistant') continue;
    totalIn += t.input_tokens || 0;
    totalOut += t.output_tokens || 0;
    totalCacheRd += t.cache_read_tokens || 0;
    const m = t.model || 'unknown';
    modelCounts[m] = (modelCounts[m] || 0) + 1;
  }
  const slug = (turns[0] && turns[0].project_slug) || '';
  const cwd = (turns.find(t => t.cwd) || {}).cwd || '';
  const base = cwd ? cwd.replace(/\\/g, '/').replace(/\/+$/, '').split('/').pop() : '';
  const project = base || slug;
  const started = (turns[0] && turns[0].timestamp) || '';
  const ended = (turns[turns.length-1] && turns[turns.length-1].timestamp) || '';

  root.innerHTML = `
    <div class="card">
      <h2 style="display:flex;align-items:center">
        <span>Session ${fmt.htmlSafe(id.slice(0,8))}…</span>
        <span class="spacer"></span>
        <a href="#/sessions" class="muted">← all sessions</a>
      </h2>
      <div class="flex muted" style="font-family:var(--mono);font-size:12px;flex-wrap:wrap;gap:14px">
        <span>${fmt.htmlSafe(project)}</span>
        <span>${fmt.ts(started)} → ${fmt.ts(ended)}</span>
        <span>${turns.length} records</span>
        <span>${fmt.int(totalIn)} in · ${fmt.int(totalOut)} out · ${fmt.int(totalCacheRd)} cache rd</span>
      </div>
    </div>

    <div class="card" style="margin-top:16px">
      <h3>Turn-by-turn</h3>
      <table>
        <thead><tr><th>time</th><th>type</th><th>model</th><th class="blur-sensitive">prompt / tools</th><th class="num">in</th><th class="num">out</th><th class="num">cache rd</th></tr></thead>
        <tbody>
          ${turns.map((t, i) => {
            const tools = t.tool_calls_json ? JSON.parse(t.tool_calls_json) : [];
            const hasDetail = !!(t.prompt_text || tools.length);
            const summary = t.prompt_text ? fmt.short(t.prompt_text, 110)
              : tools.length ? tools.map(x => x.name).join(' · ')
              : '';
            const tdAttrs = hasDetail
              ? `data-idx="${i}" class="blur-sensitive expandable" title="Click to view full text"`
              : `class="blur-sensitive"`;
            return `<tr>
              <td class="mono">${fmt.tsTime(t.timestamp)}</td>
              <td>${t.type}${t.is_sidechain ? ' <span class="badge">side</span>' : ''}</td>
              <td>${t.model ? `<span class="badge ${fmt.modelClass(t.model)}">${fmt.htmlSafe(fmt.modelShort(t.model))}</span>` : ''}</td>
              <td ${tdAttrs}>${fmt.htmlSafe(summary)}</td>
              <td class="num">${fmt.int(t.input_tokens)}</td>
              <td class="num">${fmt.int(t.output_tokens)}</td>
              <td class="num">${fmt.int(t.cache_read_tokens)}</td>
            </tr>`;
          }).join('')}
        </tbody>
      </table>
    </div>`;

  root.querySelector('tbody').addEventListener('click', e => {
    const td = e.target.closest('td[data-idx]');
    if (!td) return;
    const t = turns[parseInt(td.dataset.idx, 10)];
    const tools = t.tool_calls_json ? JSON.parse(t.tool_calls_json) : [];
    const content = t.prompt_text
      || tools.map(x => `${x.name}(\n${JSON.stringify(x.input || {}, null, 2)}\n)`).join('\n\n');
    if (!content) return;

    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.innerHTML = `
      <div class="modal blur-sensitive" style="max-width:680px;width:90vw">
        <h3 style="margin:0 0 12px">${t.prompt_text ? 'Prompt' : 'Tool calls'}</h3>
        <pre class="text-modal-pre">${fmt.htmlSafe(content)}</pre>
        <div class="actions"><button class="primary" id="txt-modal-close">Close</button></div>
      </div>`;
    overlay.addEventListener('click', e => { if (e.target === overlay) overlay.remove(); });
    overlay.querySelector('#txt-modal-close').addEventListener('click', () => overlay.remove());
    document.addEventListener('keydown', function esc(e) {
      if (e.key === 'Escape') { overlay.remove(); document.removeEventListener('keydown', esc); }
    });
    document.body.appendChild(overlay);
  });
}
