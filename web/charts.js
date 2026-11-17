// charts.js — themed ECharts wrappers

const PALETTE = ['#4A9EFF', '#7C5CFF', '#3FB68B', '#E8A23B', '#E5484D', '#5BCEDA', '#F472B6'];

const BASE = {
  textStyle: { color: '#E6EDF3', fontFamily: 'Inter' },
  color: PALETTE,
  grid: { left: 36, right: 12, top: 24, bottom: 24, containLabel: true },
};

const X_AXIS = {
  axisLine:  { lineStyle: { color: '#1F2630' } },
  axisLabel: { color: '#8B98A6' },
  axisTick:  { show: false },
};

const Y_AXIS = {
  axisLine:  { show: false },
  axisTick:  { show: false },
  splitLine: { lineStyle: { color: '#1F2630' } },
  axisLabel: { color: '#8B98A6' },
};

const TOOLTIP = {
  trigger: 'axis',
  backgroundColor: '#0F1419',
  borderColor: '#283040',
  borderWidth: 1,
  textStyle: { color: '#E6EDF3', fontFamily: 'Inter', fontSize: 12 },
  padding: [8, 12],
};

function mount(el) {
  const c = echarts.init(el, null, { renderer: 'svg' });
  window.addEventListener('resize', () => c.resize());
  return c;
}

export function lineChart(el, { x, series }) {
  const c = mount(el);
  c.setOption({
    ...BASE,
    tooltip: TOOLTIP,
    legend: { textStyle: { color: '#8B98A6' }, top: 0, right: 0, icon: 'roundRect', itemWidth: 8, itemHeight: 8 },
    xAxis: { ...X_AXIS, type: 'category', data: x, boundaryGap: false },
    yAxis: { ...Y_AXIS, type: 'value' },
    series: series.map(s => ({
      ...s, type: 'line', smooth: true, showSymbol: false,
      areaStyle: { opacity: 0.12 }, lineStyle: { width: 2 },
    })),
  });
  return c;
}

export function barChart(el, { categories, values, color }) {
  const c = mount(el);
  c.setOption({
    ...BASE,
    tooltip: { ...TOOLTIP, axisPointer: { type: 'shadow' } },
    xAxis: { ...X_AXIS, type: 'category', data: categories, axisLabel: { ...X_AXIS.axisLabel, interval: 0, rotate: categories.length > 5 ? 25 : 0 } },
    yAxis: { ...Y_AXIS, type: 'value' },
    series: [{
      type: 'bar', data: values,
      itemStyle: { color: color || PALETTE[0], borderRadius: [4, 4, 0, 0] },
      barMaxWidth: 32,
    }],
  });
  return c;
}

export function stackedBarChart(el, { categories, series, formatter }) {
  const c = mount(el);
  c.setOption({
    ...BASE,
    tooltip: {
      ...TOOLTIP,
      axisPointer: { type: 'shadow' },
      valueFormatter: formatter || (v => Number(v).toLocaleString()),
    },
    legend: {
      textStyle: { color: '#8B98A6' },
      top: 0, right: 0, icon: 'roundRect',
      itemWidth: 8, itemHeight: 8,
    },
    xAxis: {
      ...X_AXIS, type: 'category', data: categories,
      axisLabel: { ...X_AXIS.axisLabel, interval: categories.length > 20 ? 'auto' : 0, rotate: categories.length > 12 ? 45 : 0 },
    },
    yAxis: { ...Y_AXIS, type: 'value' },
    series: series.map((s, i) => ({
      name: s.name,
      type: 'bar',
      stack: 'total',
      data: s.values,
      itemStyle: { color: s.color || PALETTE[i % PALETTE.length] },
      barMaxWidth: 24,
      emphasis: { focus: 'series' },
    })),
  });
  return c;
}

export function groupedBarChart(el, { categories, series, formatter }) {
  const c = mount(el);
  c.setOption({
    ...BASE,
    tooltip: {
      ...TOOLTIP,
      axisPointer: { type: 'shadow' },
      valueFormatter: formatter || (v => Number(v).toLocaleString()),
    },
    legend: {
      textStyle: { color: '#8B98A6' },
      top: 0, right: 0, icon: 'roundRect',
      itemWidth: 8, itemHeight: 8,
    },
    xAxis: {
      ...X_AXIS, type: 'category', data: categories,
      axisLabel: { ...X_AXIS.axisLabel, interval: 0, rotate: categories.length > 5 ? 25 : 0 },
    },
    yAxis: { ...Y_AXIS, type: 'value' },
    series: series.map((s, i) => ({
      name: s.name,
      type: 'bar',
      data: s.values,
      itemStyle: { color: s.color || PALETTE[i % PALETTE.length], borderRadius: [4, 4, 0, 0] },
      barMaxWidth: 24,
      emphasis: { focus: 'series' },
    })),
  });
  return c;
}

// Horizontal bars, largest at the top. Long category labels (project names)
// read far better on a vertical axis than rotated under a column chart.
export function hBarChart(el, { categories, values, color, formatter = v => v, axisFormatter, tooltip }) {
  const c = mount(el);
  c.setOption({
    ...BASE,
    grid: { left: 8, right: 64, top: 8, bottom: 4, containLabel: true },
    tooltip: { ...TOOLTIP, axisPointer: { type: 'shadow' }, formatter: tooltip },
    xAxis: {
      ...Y_AXIS, type: 'value',
      axisLabel: { ...Y_AXIS.axisLabel, formatter: axisFormatter || formatter },
    },
    yAxis: {
      ...X_AXIS, type: 'category', data: categories, inverse: true,
      axisLabel: { ...X_AXIS.axisLabel, interval: 0 },
    },
    series: [{
      type: 'bar', data: values,
      itemStyle: { color: color || PALETTE[0], borderRadius: [0, 4, 4, 0] },
      barMaxWidth: 18,
      label: {
        show: true, position: 'right', color: '#8B98A6', fontSize: 11,
        formatter: p => formatter(p.value),
      },
    }],
  });
  return c;
}

const SUNBURST_HOLE = 0.17;   // inner-ring r0, as a fraction of the chart radius

// Two-ring sunburst: inner ring = groups, outer ring = members.
// Each node: { name, value, itemStyle, children?, label? }. Outer-ring labels sit
// outside the ring (radial) so small slices stay readable; `outerLabel(node)`
// returns their text (hide one with `label: { show: false }` on the node —
// an empty string makes ECharts fall back to the node name).
// Hovering a node highlights its ancestors and descendants. Returns
// { chart, update(view) }; a view is { data, centerTitle, centerSub, centerLink }
// and swapping views animates between them. `centerLink` (optional) is shown
// under the centre text and makes the hole clickable via `onCenterClick`.
export function sunburstChart(el, { outerLabel, tooltip, onCenterClick, ...view }) {
  const c = mount(el);
  c.setOption({
    tooltip: {
      trigger: 'item',
      backgroundColor: '#0F1419', borderColor: '#283040', borderWidth: 1,
      textStyle: { color: '#E6EDF3', fontFamily: 'Inter', fontSize: 12 },
      padding: [8, 12],
      formatter: p => (p.data && tooltip ? tooltip(p.data) : ''),
    },
    series: [{
      type: 'sunburst',
      center: ['50%', '50%'],
      sort: null,            // caller decides order (families by size, versions newest-first)
      nodeClick: false,      // caller handles clicks (built-in drill-down shifts ring depths)
      animationDurationUpdate: 600,
      itemStyle: { borderColor: '#0F1419', borderWidth: 2, borderRadius: 3 },
      // Sunburst only knows 'ancestor'/'descendant' ('relative' is tree-only):
      // groups highlight their members here, members their group (set per leaf in update).
      emphasis: { focus: 'descendant' },
      levels: [
        {},
        {
          r0: SUNBURST_HOLE * 100 + '%', r: '35%',
          label: {
            rotate: 0, minAngle: 14, color: '#fff', fontSize: 12, fontWeight: 600,
            textBorderColor: 'rgba(15,20,25,0.6)', textBorderWidth: 2,
          },
        },
        {
          r0: '35%', r: '54%',
          label: {
            position: 'outside', rotate: 'radial', distance: 6,
            color: '#8B98A6', fontSize: 11,
            rich: { b: { color: '#E6EDF3', fontSize: 11, fontWeight: 700 } },
            formatter: p => (outerLabel ? outerLabel(p.data) : p.name),
          },
        },
      ],
      data: [],
    }],
  });

  const update = ({ data, centerTitle, centerSub, centerLink }) => {
    const r = SUNBURST_HOLE * Math.min(c.getWidth(), c.getHeight()) / 2;
    const clickable = !!(centerLink && onCenterClick);
    const withFocus = n => (n.children
      ? { ...n, children: n.children.map(withFocus) }
      : { ...n, emphasis: { focus: 'ancestor' } });
    c.setOption({
      graphic: [{
        id: 'center',          // merged by id ($action 'replace' drops the text on re-render)
        type: 'group', left: 'center', top: 'middle',
        cursor: clickable ? 'pointer' : 'default',
        silent: !clickable,
        onclick: clickable ? onCenterClick : null,
        children: [
          { type: 'circle', shape: { cx: 0, cy: 0, r }, style: { fill: 'rgba(0,0,0,0)' } },
          {
            type: 'text', x: 0, y: 0,
            style: {
              text: `{t|${centerTitle}}\n{s|${centerSub}}` + (centerLink ? `\n{l|${centerLink}}` : ''),
              align: 'center', verticalAlign: 'middle',
              rich: {
                t: { fill: '#E6EDF3', fontFamily: 'Inter', fontSize: 15, fontWeight: 700, lineHeight: 20, align: 'center' },
                s: { fill: '#8B98A6', fontFamily: 'Inter', fontSize: 10, lineHeight: 14, align: 'center' },
                l: { fill: '#4A9EFF', fontFamily: 'Inter', fontSize: 10, lineHeight: 16, align: 'center' },
              },
            },
          },
        ],
      }],
      series: [{ data: data.map(withFocus) }],
    });
  };
  update(view);
  return { chart: c, update };
}
