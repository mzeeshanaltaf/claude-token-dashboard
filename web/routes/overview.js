import { api, fmt, state, loadRange, saveRange } from '/web/app.js';
import { barChart, groupedBarChart, hBarChart, stackedBarChart, sunburstChart } from '/web/charts.js';

// Claude model families for the sunburst's inner ring. Hues come from the
// dashboard palette; Mythos uses burnt orange because pink failed colour-blind
// separation against Haiku's green.
const FAMILIES = {
  opus:   { label: 'Opus',   color: '#7C5CFF' },
  sonnet: { label: 'Sonnet', color: '#4A9EFF' },
  fable:  { label: 'Fable',  color: '#E8A23B' },
  haiku:  { label: 'Haiku',  color: '#3FB68B' },
  mythos: { label: 'Mythos', color: '#C2410C' },
};

// "claude-opus-5-5" → { family: 'opus', version: '5.5' }. Handles dated ids
// ("claude-haiku-4-5-20251001") and the legacy order ("claude-3-5-sonnet-…").
// Non-Claude models (e.g. a local gemma) and "<synthetic>" return null.
function parseClaudeModel(id) {
  if (!id || !id.startsWith('claude-')) return null;
  const parts = id.slice('claude-'.length).split('-').filter(p => !/^\d{8}$/.test(p));
  const family = parts.find(p => FAMILIES[p]);
  if (!family) return null;
  return { family, version: parts.filter(p => /^\d+$/.test(p)).join('.') };
}

const coreTokens = m =>
  (m.input_tokens || 0) + (m.output_tokens || 0) +
  (m.cache_create_5m_tokens || 0) + (m.cache_create_1h_tokens || 0);

// Mix a hex colour toward the card surface (#0F1419) by t ∈ [0, 1].
function shade(hex, t) {
  const a = parseInt(hex.slice(1), 16), b = 0x0F1419;
  const ch = s => Math.round(((a >> s) & 255) * (1 - t) + ((b >> s) & 255) * t);
  return '#' + [16, 8, 0].map(s => ch(s).toString(16).padStart(2, '0')).join('');
}

function cmpVersionDesc(a, b) {
  const x = a.split('.').map(Number), y = b.split('.').map(Number);
  for (let i = 0; i < Math.max(x.length, y.length); i++) {
    const d = (y[i] || 0) - (x[i] || 0);
    if (d) return d;
  }
  return 0;
}

// Family → version tree of core tokens. Families are ordered by size, versions
// newest-first; within a family the newest version gets the full hue and older
// ones step toward the surface, so a colour always means the same model.
function modelTree(byModel) {
  const fams = {};
  for (const m of byModel) {
    const p = parseClaudeModel(m.model);
    const value = coreTokens(m);
    if (!p || value <= 0) continue;
    const f = fams[p.family] ??= { key: p.family, value: 0, cost: 0, versions: {} };
    const v = f.versions[p.version] ??= { version: p.version, value: 0, cost: 0, ids: [] };
    v.value += value; v.cost += m.cost_usd || 0; v.ids.push(m.model);
    f.value += value; f.cost += m.cost_usd || 0;
  }
  const total = Object.values(fams).reduce((s, f) => s + f.value, 0);
  const tree = Object.values(fams).sort((a, b) => b.value - a.value).map(f => {
    const meta = FAMILIES[f.key];
    const vs = Object.values(f.versions).sort((a, b) => cmpVersionDesc(a.version, b.version));
    return {
      name: meta.label, value: f.value, cost: f.cost, share: f.value / total, models: vs.length,
      itemStyle: { color: shade(meta.color, 0.3) },
      children: vs.map((v, i) => ({
        name: `${meta.label} ${v.version}`.trim(), family: meta.label,
        value: v.value, cost: v.cost, share: v.value / total, familyShare: v.value / f.value, ids: v.ids,
        itemStyle: { color: shade(meta.color, vs.length > 1 ? (i / (vs.length - 1)) * 0.5 : 0) },
      })),
    };
  });
  return { tree, total };
}

// Sunburst data for the full tree, or for one family when `focus` names it
// (that family then fills the whole circle). Each version gets `pct` — its
// share of what is on screen — for its outside label.
// Outer labels sit side by side around the ring, so keep the biggest ones and
// drop any whose centre is closer than minGap° to a label already kept; the
// dropped ones come back as `unlabelled` for the caller to list.
function sunburstView(tree, focus) {
  const fams = focus ? tree.filter(f => f.name === focus) : tree;
  const denom = fams.reduce((s, f) => s + f.value, 0);
  const leaves = [];
  let angle = 0;
  const data = fams.map(f => ({
    ...f,
    children: f.children.map(v => {
      const node = { ...v, pct: v.value / denom };
      const deg = node.pct * 360;
      leaves.push({ node, mid: angle + deg / 2 });
      angle += deg;
      return node;
    }),
  }));
  const minGap = 5;
  const kept = [];
  for (const l of [...leaves].sort((a, b) => b.node.value - a.node.value)) {
    if (kept.every(k => { const d = Math.abs(k.mid - l.mid); return Math.min(d, 360 - d) >= minGap; })) {
      kept.push(l);
    } else {
      l.node.label = { show: false };
    }
  }
  return { data, denom, unlabelled: leaves.filter(l => l.node.label).map(l => l.node) };
}

const sharePct = s => (s * 100).toFixed(s >= 0.1 ? 0 : 1) + '%';

// Tag a chart's SVG axis labels so the Cmd/Ctrl+B privacy blur hides them.
// The SVG renderer emits each label as a <text> node holding the label string.
function blurAxisLabels(chart, el, labels) {
  const names = new Set(labels);
  const mark = () => {
    const svg = el.querySelector('svg');
    if (!svg) return;
    svg.querySelectorAll('text').forEach(t => {
      if (names.has(t.textContent)) t.classList.add('blur-sensitive');
    });
  };
  chart.on('finished', mark);
  mark();
}

const RANGES = [
  { key: '7d',  label: '7d',  days: 7 },
  { key: '30d', label: '30d', days: 30 },
  { key: '90d', label: '90d', days: 90 },
  { key: 'all', label: 'All', days: null },
];

function readRange() {
  const q = (location.hash.split('?')[1] || '');
  const m = /(?:^|&)range=([^&]+)/.exec(q);
  const k = (m && decodeURIComponent(m[1])) || loadRange();
  return RANGES.find(r => r.key === k) || RANGES.find(r => r.key === 'all');
}

function writeRange(key) {
  saveRange(key);
  const base = (location.hash.replace(/^#/, '').split('?')[0]) || '/overview';
  location.hash = '#' + base + '?range=' + encodeURIComponent(key);
}

function sinceIso(range) {
  if (!range.days) return null;
  return new Date(Date.now() - range.days * 86400 * 1000).toISOString();
}

function withSince(url, since) {
  if (!since) return url;
  return url + (url.includes('?') ? '&' : '?') + 'since=' + encodeURIComponent(since);
}

export default async function (root) {
  const range = readRange();
  const since = sinceIso(range);

  const [totals, projects, sessions, tools, daily, byModel] = await Promise.all([
    api(withSince('/api/overview', since)),
    api(withSince('/api/projects', since)),
    api(withSince('/api/sessions?limit=10', since)),
    api(withSince('/api/tools', since)),
    api(withSince('/api/daily', since)),
    api(withSince('/api/by-model', since)),
  ]);

  const cacheCreate =
    (totals.cache_create_5m_tokens || 0) +
    (totals.cache_create_1h_tokens || 0);
  const totalTokens =
    (totals.input_tokens || 0) +
    (totals.output_tokens || 0) +
    (totals.cache_read_tokens || 0) +
    cacheCreate;

  const kpi = (label, compactVal, fullVal, cls = '', sub = '', detail = '') => `
    <div class="card kpi ${cls}">
      <div class="label">${label}</div>
      <div class="value" title="${fullVal}">${compactVal}</div>
      ${sub ? `<div class="sub" title="estimated cost">${sub}</div>` : ''}
      ${detail ? `<div class="sub">${detail}</div>` : ''}
    </div>`;

  const rangeTabs = `
    <div class="range-tabs" role="tablist">
      ${RANGES.map(r => `<button data-range="${r.key}" class="${r.key === range.key ? 'active' : ''}">${r.label}</button>`).join('')}
    </div>`;

  root.innerHTML = `
    <div class="flex" style="margin-bottom:14px">
      <h2 style="margin:0;font-size:16px;letter-spacing:-0.01em">Overview</h2>
      <span class="muted" style="font-size:12px">${range.days ? `last ${range.days} days` : 'all time'}</span>
      <div class="spacer"></div>
      ${rangeTabs}
    </div>

    <div class="row cols-4">
      ${kpi('Projects',     fmt.int(totals.projects),       fmt.int(totals.projects))}
      ${kpi('Sessions',     fmt.int(totals.sessions),       fmt.int(totals.sessions))}
      ${kpi('Turns',        fmt.int(totals.turns),          fmt.int(totals.turns))}
      <div class="card kpi cost">
        <div class="label">Est. cost</div>
        <div class="value" title="${fmt.usd(totals.cost_usd)}">${fmt.usd(totals.cost_usd)}</div>
        ${planSubtitle()}
      </div>
    </div>
    <div class="row cols-5" style="margin-top:16px">
      ${kpi('Total tokens', fmt.compact(totalTokens),               fmt.int(totalTokens) + ' tokens (input + output + cache read + cache create)', '', fmt.usd(totals.cost_usd))}
      ${kpi('Input',        fmt.compact(totals.input_tokens),       fmt.int(totals.input_tokens) + ' tokens', '', fmt.usd(totals.cost_input_usd))}
      ${kpi('Output',       fmt.compact(totals.output_tokens),      fmt.int(totals.output_tokens) + ' tokens', '', fmt.usd(totals.cost_output_usd))}
      ${kpi('Cache read',   fmt.compact(totals.cache_read_tokens),  fmt.int(totals.cache_read_tokens) + ' tokens', '', fmt.usd(totals.cost_cache_read_usd))}
      ${kpi('Cache create', fmt.compact(cacheCreate),               fmt.int(cacheCreate) + ' tokens', '', fmt.usd(totals.cost_cache_create_usd),
            `5m: ${fmt.compact(totals.cache_create_5m_tokens)} (${fmt.usd(totals.cost_cache_create_5m_usd)}) · 1h: ${fmt.compact(totals.cache_create_1h_tokens)} (${fmt.usd(totals.cost_cache_create_1h_usd)})`)}
    </div>

    <details class="card glossary" style="margin-top:16px">
      <summary><h3 style="display:inline-block;margin:0">What do these numbers mean?</h3><span class="muted" style="font-size:12px">— click to expand</span></summary>
      <dl>
        <dt>Session</dt><dd>One run of Claude Code (from <code>claude</code> to exit). Each session is a single <code>.jsonl</code> file.</dd>
        <dt>Turn</dt><dd>One message you sent to Claude. Each turn triggers a response (possibly with tool calls in between).</dd>
        <dt>Input tokens</dt><dd>The new text you (and tool results) sent to Claude this turn. Billed at the full input rate.</dd>
        <dt>Output tokens</dt><dd>The text Claude wrote back. Billed at the highest rate — usually the biggest cost driver per turn.</dd>
        <dt>Cache read</dt><dd>Tokens Claude re-used from a cache (your CLAUDE.md, previously-read files, the conversation so far). ~10× cheaper than fresh input. High cache-read counts = good cost hygiene.</dd>
        <dt>Cache create</dt><dd>Writing something into the cache for the first time. One-time cost; pays off on the next turn.</dd>
        <dt>Total tokens</dt><dd>Every token that moved: Input + Output + Cache read + Cache create. This <b>includes cache reads</b>, so it's much larger than core tokens (cache reads usually dominate). Useful as a raw volume measure, not a cost measure.</dd>
        <dt>Core tokens</dt><dd>Input + Output + Cache create — a proxy for where your spend concentrates. Cache reads <b>are</b> billed too (about 10× cheaper), but they're excluded from this count because their sheer volume would swamp it. For actual spend see <b>Est. cost</b>; for raw volume see <b>Total tokens</b>.</dd>
      </dl>
    </details>

    <div class="row cols-2" style="margin-top:16px">
      <div class="card">
        <h3>Your daily work</h3>
        <p class="muted" style="margin:-4px 0 10px;font-size:12px">Tokens you paid for: what you sent (<b>input</b>), what Claude wrote (<b>output</b>), and what got stored for re-use (<b>cache create</b>).</p>
        <div id="ch-daily-billable" style="height:260px"></div>
      </div>
      <div class="card">
        <h3>Daily cache reads</h3>
        <p class="muted" style="margin:-4px 0 10px;font-size:12px"><b>Cache reads</b> are cheap re-uses of things Claude already saw (like your CLAUDE.md). They cost ~10× less than regular input tokens — high numbers here are a good thing.</p>
        <div id="ch-daily-cache" style="height:260px"></div>
      </div>
    </div>

    <div class="row cols-2" style="margin-top:16px">
      <div class="card"><h3>Tokens by project</h3><div id="ch-projects" style="height:340px"></div></div>
      <div class="card">
        <h3>Cost by project</h3>
        <p class="muted" style="margin:-4px 0 4px;font-size:12px">Top 10 projects by estimated API cost. Click a bar to open the project.</p>
        <div id="ch-project-cost" style="height:320px"></div>
      </div>
    </div>

    <div class="row cols-2" style="margin-top:16px">
      <div class="card">
        <h3>Token usage by model</h3>
        <p class="muted" style="margin:-4px 0 4px;font-size:12px">Share of core tokens across Claude models — inner ring is the family, outer ring the version. Hover a family to highlight its models; click one to zoom in.</p>
        <div id="ch-model" style="height:440px"></div>
        <p id="ch-model-small" class="muted" style="margin:4px 0 0;font-size:12px"></p>
      </div>
      <div class="card"><h3>Top tools (by call count)</h3><div id="ch-tools" style="height:460px"></div></div>
    </div>

    <div class="row" style="margin-top:16px">
      <div class="card">
        <h3 style="display:flex;align-items:center"><span>Recent sessions</span><span class="spacer"></span><a href="#/sessions" style="font-weight:400;font-size:12px">all →</a></h3>
        <table>
          <thead><tr><th>started</th><th>project</th><th class="num">tokens</th></tr></thead>
          <tbody>
            ${sessions.map(s => `
              <tr>
                <td class="mono">${fmt.ts(s.started)}</td>
                <td class="blur-sensitive"><a href="#/sessions/${encodeURIComponent(s.session_id)}">${fmt.htmlSafe(s.project_name || s.project_slug)}</a></td>
                <td class="num">${fmt.compact(s.tokens)}</td>
              </tr>`).join('') || '<tr><td colspan="3" class="muted">no sessions in this range</td></tr>'}
          </tbody>
        </table>
      </div>
    </div>
  `;

  // range buttons
  root.querySelectorAll('.range-tabs button').forEach(btn => {
    btn.addEventListener('click', () => writeRange(btn.dataset.range));
  });

  // Your daily work — core tokens (input + output + cache create)
  stackedBarChart(document.getElementById('ch-daily-billable'), {
    categories: daily.map(d => d.day),
    series: [
      { name: 'input',        values: daily.map(d => d.input_tokens),        color: '#4A9EFF' },
      { name: 'output',       values: daily.map(d => d.output_tokens),       color: '#7C5CFF' },
      { name: 'cache create', values: daily.map(d => d.cache_create_tokens), color: '#E8A23B' },
    ],
  });

  // Daily cache reads (separate — scale is 100× larger)
  stackedBarChart(document.getElementById('ch-daily-cache'), {
    categories: daily.map(d => d.day),
    series: [
      { name: 'cache read', values: daily.map(d => d.cache_read_tokens), color: '#3FB68B' },
    ],
  });

  // Token usage by model — family → version sunburst (Claude models only)
  // Click a family (or one of its versions) to zoom into it; click the centre
  // or the family ring to zoom back out.
  const { tree: modelData } = modelTree(byModel);
  const modelEl = document.getElementById('ch-model');
  const smallEl = document.getElementById('ch-model-small');
  if (!modelData.length) {
    modelEl.innerHTML = '<p class="muted" style="padding:16px 0">no Claude model usage in this range</p>';
  } else {
    let focus = null;
    const viewFor = f => {
      const v = sunburstView(modelData, f);
      smallEl.innerHTML = v.unlabelled.length
        ? 'Smaller slices: ' + v.unlabelled
            .map(n => `${fmt.htmlSafe(n.name)} <b style="color:var(--text)">${sharePct(n.pct)}</b>`)
            .join(' · ')
        : '';
      return {
        data: v.data,
        centerTitle: fmt.compact(v.denom),
        centerSub: f ? `${f} tokens` : 'core tokens',
        centerLink: f ? '← all models' : '',
      };
    };
    const zoom = f => { focus = f; sunburst.update(viewFor(f)); };
    const hint = t => `<br/><span style="color:#5A6573;font-size:11px">${t}</span>`;
    const sunburst = sunburstChart(modelEl, {
      ...viewFor(null),
      onCenterClick: () => zoom(null),
      outerLabel: d => `{b|${sharePct(d.pct)}}  ${d.name}`,
      tooltip: d => d.children
        ? `<b>${fmt.htmlSafe(d.name)}</b> <span style="color:#8B98A6">· ${d.models} model${d.models === 1 ? '' : 's'}</span><br/>`
          + `${fmt.compact(d.value)} core tokens · <b>${sharePct(d.share)}</b> of Claude usage<br/>`
          + `Est. cost ${fmt.usd(d.cost)}`
          + hint(focus ? 'click to zoom out' : 'click to zoom in')
        : `<b>${fmt.htmlSafe(d.name)}</b> <span style="color:#8B98A6">${fmt.htmlSafe(d.ids.join(', '))}</span><br/>`
          + `${fmt.compact(d.value)} core tokens · <b>${sharePct(d.share)}</b> of Claude`
          + (d.familyShare < 1 ? ` · ${sharePct(d.familyShare)} of ${fmt.htmlSafe(d.family)}` : '') + '<br/>'
          + `Est. cost ${fmt.usd(d.cost)}`
          + (focus ? '' : hint(`click to zoom into ${fmt.htmlSafe(d.family)}`)),
    });
    sunburst.chart.on('click', p => {
      if (!p.data) return;
      if (focus) { if (p.data.children) zoom(null); }
      else zoom(p.data.children ? p.data.name : p.data.family);
    });
  }

  // Cost by project — top 10 by estimated API cost
  const costProjects = projects
    .filter(p => p.estimated_cost_usd > 0)
    .sort((a, b) => b.estimated_cost_usd - a.estimated_cost_usd)
    .slice(0, 10);
  const totalCost = projects.reduce((s, p) => s + (p.estimated_cost_usd || 0), 0);
  const costLabels = costProjects.map(p => {
    const name = p.project_name || p.project_slug;
    return name.length > 24 ? name.slice(0, 23) + '…' : name;
  });
  const costEl = document.getElementById('ch-project-cost');
  if (!costProjects.length) {
    costEl.innerHTML = '<p class="muted" style="padding:16px 0">no project costs in this range</p>';
  } else {
    const costChart = hBarChart(costEl, {
      categories: costLabels,
      values: costProjects.map(p => p.estimated_cost_usd),
      color: '#3FB68B',
      formatter: v => '$' + Math.round(v).toLocaleString(),
      axisFormatter: v => '$' + fmt.compact(v),
      tooltip: ps => {
        const p = costProjects[ps[0].dataIndex];
        return `<b class="blur-sensitive">${fmt.htmlSafe(p.project_name || p.project_slug)}</b><br/>`
          + `Est. cost <b>${fmt.usd(p.estimated_cost_usd)}</b>`
          + (totalCost ? ` · ${sharePct(p.estimated_cost_usd / totalCost)} of spend` : '') + '<br/>'
          + `${fmt.int(p.sessions)} sessions · ${fmt.int(p.turns)} turns`;
      },
    });
    costChart.on('click', p => {
      const proj = costProjects[p.dataIndex];
      if (proj) location.hash = '#/projects/' + encodeURIComponent(proj.project_slug);
    });
    blurAxisLabels(costChart, costEl, costLabels);
  }

  // tokens by project — input vs output
  const topProjects = projects.slice(0, 8);
  const projectLabels = topProjects.map(p => {
    const name = p.project_name || p.project_slug;
    return name.length > 20 ? name.slice(0, 19) + '…' : name;
  });
  const projChartEl = document.getElementById('ch-projects');
  const projChart = groupedBarChart(projChartEl, {
    categories: projectLabels,
    series: [
      { name: 'input',  values: topProjects.map(p => p.input_tokens  || 0), color: '#4A9EFF' },
      { name: 'output', values: topProjects.map(p => p.output_tokens || 0), color: '#7C5CFF' },
    ],
  });

  // Blur only the project-name axis labels under Cmd/Ctrl+B, not the whole chart.
  blurAxisLabels(projChart, projChartEl, projectLabels);

  // top tools
  const topTools = tools.slice(0, 8);
  barChart(document.getElementById('ch-tools'), {
    categories: topTools.map(t => t.tool_name),
    values: topTools.map(t => t.calls),
    color: '#7C5CFF',
  });
}

function planSubtitle() {
  if (!state.pricing || state.plan === 'api') return '';
  const p = state.pricing.plans[state.plan];
  if (!p || !p.monthly) return '';
  return `<div class="sub">pay $${p.monthly}/mo on ${fmt.htmlSafe(p.label)}</div>`;
}
