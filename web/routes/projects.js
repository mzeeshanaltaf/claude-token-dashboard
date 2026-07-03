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
            ${th('estimated_cost_usd', 'est. cost', 'num ')}
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
                <td class="num mono">${fmt.usd(r.estimated_cost_usd)}</td>
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
  const [sessions, projects] = await Promise.all([
    api('/api/projects/' + encodeURIComponent(slug) + '/sessions'),
    api('/api/projects'),
  ]);
  const summary = projects.find(p => p.project_slug === slug) || {};
  const name = (sessions[0] && sessions[0].project_name) || summary.project_name || slug;

  const kpi = (label, val, full, cls = '') => `
    <div class="card kpi ${cls}">
      <div class="label">${label}</div>
      <div class="value" title="${full}">${val}</div>
    </div>`;

  root.innerHTML = `
    <div class="card">
      <h2 style="display:flex;align-items:center">
        <span>${fmt.htmlSafe(name)}</span>
        <span class="spacer"></span>
        <a href="#/projects" class="muted">← all projects</a>
      </h2>
      <div class="muted" style="font-family:var(--mono);font-size:12px" title="project slug">${fmt.htmlSafe(slug)}</div>
    </div>

    <div class="row cols-5" style="margin-top:16px">
      ${kpi('Sessions',        fmt.int(summary.sessions),                fmt.int(summary.sessions))}
      ${kpi('Turns',           fmt.int(summary.turns),                   fmt.int(summary.turns))}
      ${kpi('Billable tokens', fmt.compact(summary.billable_tokens),     fmt.int(summary.billable_tokens) + ' tokens')}
      ${kpi('Cache reads',     fmt.compact(summary.cache_read_tokens),   fmt.int(summary.cache_read_tokens) + ' tokens')}
      <div class="card kpi cost">
        <div class="label">Est. cost</div>
        <div class="value" title="${fmt.usd(summary.estimated_cost_usd)}">${fmt.usd(summary.estimated_cost_usd)}</div>
      </div>
    </div>

    <div class="card" style="margin-top:16px">
      <h3>Sessions</h3>
      ${sessions.length === 0
        ? `<p class="muted">No sessions found for this project.</p>`
        : `<table>
          <thead><tr><th>started</th><th>ended</th><th class="num">turns</th><th class="num">tokens</th><th class="num">est. cost</th><th>session</th></tr></thead>
          <tbody>
            ${sessions.map(s => `
              <tr>
                <td class="mono">${fmt.ts(s.started)}</td>
                <td class="mono">${fmt.ts(s.ended)}</td>
                <td class="num">${fmt.int(s.turns)}</td>
                <td class="num">${fmt.int(s.tokens)}</td>
                <td class="num mono">${fmt.usd(s.estimated_cost_usd)}</td>
                <td><a href="#/sessions/${encodeURIComponent(s.session_id)}" class="mono">${fmt.htmlSafe(s.session_id.slice(0,8))}…</a></td>
              </tr>`).join('')}
          </tbody>
        </table>`}
    </div>`;
}
