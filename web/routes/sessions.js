import { api, fmt } from '/web/app.js';

export default async function (root) {
  const id = decodeURIComponent(location.hash.split('/')[2] || '');
  if (!id) return renderList(root);
  return renderSession(root, id);
}

const PAGE_SIZES = [25, 50, 100, 200];

async function renderList(root) {
  const list = await api('/api/sessions?limit=1000');
  let sortCol = 'started', sortDir = -1;
  let page = 1, pageSize = 25;

  function render() {
    const sorted = [...list].sort((a, b) => {
      const av = a[sortCol], bv = b[sortCol];
      if (av == null) return 1; if (bv == null) return -1;
      return (av < bv ? -1 : av > bv ? 1 : 0) * sortDir;
    });
    const total = sorted.length;
    const pages = Math.max(1, Math.ceil(total / pageSize));
    if (page > pages) page = pages;
    const start = (page - 1) * pageSize;
    const pageRows = sorted.slice(start, start + pageSize);
    const th = (col, label, cls = '') =>
      `<th class="${cls}sortable" data-col="${col}">${label}${col === sortCol ? (sortDir > 0 ? ' ↑' : ' ↓') : ''}</th>`;

    root.innerHTML = `
      <div class="card">
        <h2>Sessions</h2>
        <table>
          <thead><tr>
            ${th('started', 'started')}
            <th>project</th>
            ${th('title', 'title')}
            ${th('turns', 'turns', 'num ')}
            ${th('input_tokens', 'input', 'num ')}
            ${th('output_tokens', 'output', 'num ')}
            <th class="num" title="Cache reads: tokens re-used from cache (~10× cheaper than input)">cache reads</th>
            <th class="num" title="Cache writes: tokens newly stored in cache (5m or 1h TTL)">cache writes</th>
            ${th('total_tokens', 'total tokens', 'num ')}
            ${th('estimated_cost_usd', 'est. cost', 'num ')}
            <th>session</th>
          </tr></thead>
          <tbody>
            ${pageRows.map(s => `
              <tr>
                <td class="mono">${fmt.ts(s.started)}</td>
                <td class="blur-sensitive" title="${fmt.htmlSafe(s.project_slug)}">${fmt.htmlSafe(s.project_name || s.project_slug)}</td>
                <td class="blur-sensitive" title="${fmt.htmlSafe(s.title || '')}">${s.title ? fmt.htmlSafe(fmt.short(s.title, 60)) : '<span class="muted">—</span>'}</td>
                <td class="num">${fmt.int(s.turns)}</td>
                <td class="num">${fmt.int(s.input_tokens)}</td>
                <td class="num">${fmt.int(s.output_tokens)}</td>
                <td class="num">${fmt.int(s.cache_read_tokens)}</td>
                <td class="num" title="5m: ${fmt.int(s.cache_create_5m_tokens)} · 1h: ${fmt.int(s.cache_create_1h_tokens)}">${fmt.int(s.cache_write_tokens)}</td>
                <td class="num">${fmt.int(s.total_tokens)}</td>
                <td class="num mono">${fmt.usd(s.estimated_cost_usd)}</td>
                <td><a href="#/sessions/${encodeURIComponent(s.session_id)}" class="mono">${fmt.htmlSafe(s.session_id.slice(0,8))}…</a></td>
              </tr>`).join('') || '<tr><td colspan="11" class="muted">no sessions</td></tr>'}
          </tbody>
        </table>
        <div class="pager">
          <span class="count">${total ? `Showing ${start + 1}–${Math.min(start + pageSize, total)} of ${total}` : '0 sessions'}</span>
          <span class="spacer"></span>
          <label class="count">Rows
            <select id="page-size">${PAGE_SIZES.map(n => `<option value="${n}" ${n === pageSize ? 'selected' : ''}>${n}</option>`).join('')}</select>
          </label>
          <button data-page="prev" ${page <= 1 ? 'disabled' : ''}>← Prev</button>
          <span class="count">Page ${page} / ${pages}</span>
          <button data-page="next" ${page >= pages ? 'disabled' : ''}>Next →</button>
        </div>
      </div>`;

    root.querySelectorAll('th.sortable').forEach(el => {
      el.addEventListener('click', () => {
        if (sortCol === el.dataset.col) sortDir *= -1;
        else { sortCol = el.dataset.col; sortDir = -1; }
        page = 1;
        render();
      });
    });

    root.querySelectorAll('button[data-page]').forEach(btn => {
      btn.addEventListener('click', () => {
        page += btn.dataset.page === 'next' ? 1 : -1;
        if (page < 1) page = 1;
        render();
      });
    });

    const sizeSel = root.querySelector('#page-size');
    if (sizeSel) sizeSel.addEventListener('change', () => {
      pageSize = Number(sizeSel.value) || 25;
      page = 1;
      render();
    });
  }

  render();
}

async function renderSession(root, id) {
  const turns = await api('/api/sessions/' + encodeURIComponent(id));
  let totalIn = 0, totalOut = 0, totalCacheRd = 0, totalCache5m = 0, totalCache1h = 0;
  let costIn = 0, costOut = 0, costCacheRd = 0, costCache5m = 0, costCache1h = 0, costTotal = 0;
  let modelCounts = {};
  for (const t of turns) {
    if (t.type !== 'assistant') continue;
    totalIn += t.input_tokens || 0;
    totalOut += t.output_tokens || 0;
    totalCacheRd += t.cache_read_tokens || 0;
    totalCache5m += t.cache_create_5m_tokens || 0;
    totalCache1h += t.cache_create_1h_tokens || 0;
    costIn += t.cost_input_usd || 0;
    costOut += t.cost_output_usd || 0;
    costCacheRd += t.cost_cache_read_usd || 0;
    costCache5m += t.cost_cache_create_5m_usd || 0;
    costCache1h += t.cost_cache_create_1h_usd || 0;
    costTotal += t.estimated_cost_usd || 0;
    const m = t.model || 'unknown';
    modelCounts[m] = (modelCounts[m] || 0) + 1;
  }
  const slug = (turns[0] && turns[0].project_slug) || '';
  const cwd = (turns.find(t => t.cwd) || {}).cwd || '';
  const base = cwd ? cwd.replace(/\\/g, '/').replace(/\/+$/, '').split('/').pop() : '';
  const project = base || slug;
  const started = (turns[0] && turns[0].timestamp) || '';
  const ended = (turns[turns.length-1] && turns[turns.length-1].timestamp) || '';
  const title = (turns.find(t => t.title) || {}).title || '';

  const kpi = (label, val, full, sub = '') => `
    <div class="card kpi">
      <div class="label">${label}</div>
      <div class="value" title="${full}">${val}</div>
      ${sub ? `<div class="sub">${sub}</div>` : ''}
    </div>`;

  root.innerHTML = `
    <div class="card">
      <h2 style="display:flex;align-items:center">
        <span class="blur-sensitive">${title ? fmt.htmlSafe(title) : `Session ${fmt.htmlSafe(id.slice(0,8))}…`}</span>
        <span class="spacer"></span>
        <a href="#/sessions" class="muted">← all sessions</a>
      </h2>
      <div class="flex muted" style="font-family:var(--mono);font-size:12px;flex-wrap:wrap;gap:14px">
        <span class="blur-sensitive">${fmt.htmlSafe(project)}</span>
        ${title ? `<span title="session id">${fmt.htmlSafe(id.slice(0,8))}…</span>` : ''}
      </div>
    </div>

    <div class="row cols-4" style="margin-top:16px">
      ${kpi('Started', fmt.ts(started), fmt.htmlSafe(started))}
      ${kpi('Ended', fmt.ts(ended), fmt.htmlSafe(ended))}
      ${kpi('Records', fmt.int(turns.length), fmt.int(turns.length))}
      <div class="card kpi cost">
        <div class="label">Total est. cost</div>
        <div class="value" title="${fmt.usd(costTotal)}">${fmt.usd(costTotal)}</div>
      </div>
    </div>
    <div class="row cols-4" style="margin-top:16px">
      ${kpi('Input', fmt.compact(totalIn), fmt.int(totalIn) + ' tokens', fmt.usd(costIn))}
      ${kpi('Output', fmt.compact(totalOut), fmt.int(totalOut) + ' tokens', fmt.usd(costOut))}
      ${kpi('Cache reads', fmt.compact(totalCacheRd), fmt.int(totalCacheRd) + ' tokens', fmt.usd(costCacheRd))}
      ${kpi('Cache writes', fmt.compact(totalCache5m + totalCache1h), fmt.int(totalCache5m + totalCache1h) + ' tokens', fmt.usd(costCache5m + costCache1h))}
    </div>
    <div class="row cols-2" style="margin-top:16px">
      ${kpi('Cache create (5m)', fmt.compact(totalCache5m), fmt.int(totalCache5m) + ' tokens', fmt.usd(costCache5m))}
      ${kpi('Cache create (1h)', fmt.compact(totalCache1h), fmt.int(totalCache1h) + ' tokens', fmt.usd(costCache1h))}
    </div>

    <div class="card" style="margin-top:16px">
      <h3>Turn-by-turn</h3>
      <table>
        <thead><tr><th>time</th><th>type</th><th>model</th><th class="blur-sensitive">prompt / tools</th><th class="num">in</th><th class="num">out</th><th class="num">cache rd</th><th class="num" title="Cache write, 5-minute TTL">cache wr (5m)</th><th class="num" title="Cache write, 1-hour TTL">cache wr (1h)</th></tr></thead>
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
              <td class="num">${fmt.int(t.cache_create_5m_tokens)}</td>
              <td class="num">${fmt.int(t.cache_create_1h_tokens)}</td>
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
