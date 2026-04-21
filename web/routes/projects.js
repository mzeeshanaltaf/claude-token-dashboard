import { api, fmt } from '/web/app.js';

export default async function (root) {
  const slug = decodeURIComponent(location.hash.split('/')[2] || '');
  if (!slug) return renderList(root);
  return renderProject(root, slug);
}

async function renderList(root) {
  const rows = await api('/api/projects');
  let sortCol = 'billable_tokens', sortDir = -1;

  function render() {
    const sorted = [...rows].sort((a, b) => {
      const av = a[sortCol], bv = b[sortCol];
      if (av == null) return 1; if (bv == null) return -1;
      return (av < bv ? -1 : av > bv ? 1 : 0) * sortDir;
    });
    const th = (col, label, cls = '') =>
      `<th class="${cls}sortable" data-col="${col}">${label}${col === sortCol ? (sortDir > 0 ? ' ↑' : ' ↓') : ''}</th>`;

    root.innerHTML = `
      <div class="card">
        <h2>Projects</h2>
        <p class="muted" style="margin:-8px 0 14px">Click a project to view its sessions. Click column headers to sort.</p>
        <table>
          <thead><tr>
            <th>project</th>
            ${th('sessions', 'sessions', 'num ')}
            ${th('turns', 'turns', 'num ')}
            ${th('billable_tokens', 'billable tokens', 'num ')}
            <th class="num">cache reads</th>
          </tr></thead>
          <tbody>
            ${sorted.map(r => `
              <tr>
                <td title="${fmt.htmlSafe(r.project_slug)}">
                  <a href="#/projects/${encodeURIComponent(r.project_slug)}">${fmt.htmlSafe(r.project_name || r.project_slug)}</a>
                </td>
                <td class="num">${fmt.int(r.sessions)}</td>
                <td class="num">${fmt.int(r.turns)}</td>
                <td class="num">${fmt.int(r.billable_tokens)}</td>
                <td class="num">${fmt.int(r.cache_read_tokens)}</td>
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

async function renderProject(root, slug) {
  const sessions = await api('/api/projects/' + encodeURIComponent(slug) + '/sessions');
  const name = (sessions[0] && sessions[0].project_name) || slug;
  const totalTurns  = sessions.reduce((s, r) => s + (r.turns  || 0), 0);
  const totalTokens = sessions.reduce((s, r) => s + (r.tokens || 0), 0);

  root.innerHTML = `
    <div class="card">
      <h2 style="display:flex;align-items:center">
        <span>${fmt.htmlSafe(name)}</span>
        <span class="spacer"></span>
        <a href="#/projects" class="muted">← all projects</a>
      </h2>
      <div class="flex muted" style="font-family:var(--mono);font-size:12px;flex-wrap:wrap;gap:14px">
        <span title="project slug">${fmt.htmlSafe(slug)}</span>
        <span>${fmt.int(sessions.length)} session${sessions.length !== 1 ? 's' : ''}</span>
        <span>${fmt.int(totalTurns)} turns</span>
        <span>${fmt.int(totalTokens)} tokens</span>
      </div>
    </div>

    <div class="card" style="margin-top:16px">
      <h3>Sessions</h3>
      ${sessions.length === 0
        ? `<p class="muted">No sessions found for this project.</p>`
        : `<table>
          <thead><tr><th>started</th><th>ended</th><th class="num">turns</th><th class="num">tokens</th><th>session</th></tr></thead>
          <tbody>
            ${sessions.map(s => `
              <tr>
                <td class="mono">${fmt.ts(s.started)}</td>
                <td class="mono">${fmt.ts(s.ended)}</td>
                <td class="num">${fmt.int(s.turns)}</td>
                <td class="num">${fmt.int(s.tokens)}</td>
                <td><a href="#/sessions/${encodeURIComponent(s.session_id)}" class="mono">${fmt.htmlSafe(s.session_id.slice(0,8))}…</a></td>
              </tr>`).join('')}
          </tbody>
        </table>`}
    </div>`;
}
