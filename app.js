let rawData = [];
let filteredData = [];
let rawChats = [];
let filteredChats = [];
let charts = {};
let chartMeta = {};
let latestScope = { agent: '', project: '' };
let hasUserFilterInteraction = false;

const formatNumber = (num) => new Intl.NumberFormat('en-US').format(Math.round(num || 0));
const formatTokens = (num) => {
    num = Number(num || 0);
    if (num >= 1000000) return (num / 1000000).toFixed(2) + 'M';
    if (num >= 1000) return (num / 1000).toFixed(1) + 'k';
    return String(Math.round(num));
};
const formatDate = (isoStr) => {
    if (!isoStr) return 'N/A';
    const d = new Date(isoStr);
    if (isNaN(d)) return 'N/A';
    return d.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
};

document.addEventListener('DOMContentLoaded', () => {
    setupNavigation();
    setupBrandModal();
    setupFilters();
    setupSettings();
    setupResizeRedraw();
    document.getElementById('date-from').value = '';
    document.getElementById('date-to').value = '';
    fetchData();
});

function setupNavigation() {
    const navItems = document.querySelectorAll('.nav-item');
    const views = document.querySelectorAll('.view-section');

    navItems.forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            showView(item.dataset.view);
        });
    });
}

function showView(viewName) {
    const navItems = document.querySelectorAll('.nav-item');
    const views = document.querySelectorAll('.view-section');
    navItems.forEach(nav => nav.classList.toggle('active', nav.dataset.view === viewName));
    views.forEach(view => view.classList.toggle('active', view.id === `view-${viewName}`));
}

function setupBrandModal() {
    const trigger = document.getElementById('stacksolvers-info-btn');
    const modal = document.getElementById('stacksolvers-modal');
    const panel = modal ? modal.querySelector('.brand-modal-panel') : null;
    const closers = modal ? modal.querySelectorAll('[data-brand-modal-close]') : [];
    if (!trigger || !modal || !panel) return;

    const openModal = () => {
        modal.classList.remove('hidden');
        document.body.classList.add('modal-open');
        panel.focus({ preventScroll: true });
    };

    const closeModal = () => {
        modal.classList.add('hidden');
        document.body.classList.remove('modal-open');
        trigger.focus({ preventScroll: true });
    };

    trigger.addEventListener('click', openModal);
    closers.forEach(el => el.addEventListener('click', closeModal));
    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && !modal.classList.contains('hidden')) closeModal();
    });
}

function setupFilters() {
    document.getElementById('global-search').addEventListener('input', () => {
        hasUserFilterInteraction = true;
        applyFilters();
    });
    document.getElementById('date-from').addEventListener('change', () => {
        hasUserFilterInteraction = true;
        clearQuickFilters();
        applyFilters();
    });
    document.getElementById('date-to').addEventListener('change', () => {
        hasUserFilterInteraction = true;
        clearQuickFilters();
        applyFilters();
    });
    document.getElementById('project-filter').addEventListener('change', () => {
        hasUserFilterInteraction = true;
        applyFilters();
    });
    document.getElementById('agent-filter').addEventListener('change', () => {
        hasUserFilterInteraction = true;
        applyFilters();
    });

    document.querySelectorAll('.quick-filter-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            hasUserFilterInteraction = true;
            document.querySelectorAll('.quick-filter-btn').forEach(b => b.classList.remove('active'));
            e.target.classList.add('active');
            applyQuickFilter(e.target.dataset.range);
        });
    });
}

function clearQuickFilters() {
    document.querySelectorAll('.quick-filter-btn').forEach(b => b.classList.remove('active'));
}

function applyQuickFilter(range) {
    const today = new Date();
    let fromDate = new Date();
    let toDate = new Date();

    if (range === 'yesterday') {
        fromDate.setDate(today.getDate() - 1);
        toDate.setDate(today.getDate() - 1);
    } else if (range === 'week') {
        const day = today.getDay() || 7;
        if (day !== 1) fromDate.setDate(today.getDate() - (day - 1));
    } else if (range === 'month') {
        fromDate.setDate(1);
    } else if (range === 'all') {
        fromDate = new Date(0);
    }

    if (range === 'all') {
        document.getElementById('date-from').value = '';
        document.getElementById('date-to').value = '';
    } else {
        const offset = fromDate.getTimezoneOffset() * 60000;
        const localFrom = new Date(fromDate.getTime() - offset);
        const localTo = new Date(toDate.getTime() - offset);
        document.getElementById('date-from').value = localFrom.toISOString().split('T')[0];
        document.getElementById('date-to').value = localTo.toISOString().split('T')[0];
    }
    applyFilters();
}

function setupSettings() {
    document.getElementById('save-path-btn').addEventListener('click', () => {
        const path = document.getElementById('custom-path').value;
        fetchData(path);
    });

    document.getElementById('resolve-error-btn').addEventListener('click', () => {
        document.querySelector('.nav-item[data-view="settings"]').click();
        document.getElementById('custom-path').focus();
    });
}

async function fetchData(customPath = null) {
    const statusEl = document.getElementById('connection-status');
    const dotEl = document.querySelector('.status-indicator .dot');

    setLoading(true, customPath ? 'Scanning selected data directory...' : 'Scanning local agent usage...');
    statusEl.textContent = 'Connecting...';
    dotEl.classList.remove('active');

    try {
        let url = '/api/usage';
        if (customPath) url += `?dir=${encodeURIComponent(customPath)}`;

        const res = await fetch(url);
        if (!res.ok) throw new Error(`Server returned ${res.status}`);
        const data = await res.json();

        rawData = processRawData(data.sessions || []);
        rawChats = processRawChats(rawData);

        populateProjectFilter();
        populateAgentFilter();
        captureLatestScope(data.summary || null);
        renderAgentTable();
        applyFilters();

        document.getElementById('error-banner').classList.add('hidden');
        statusEl.textContent = 'Connected';
        dotEl.classList.add('active');
    } catch (err) {
        console.error(err);
        document.getElementById('error-banner').classList.remove('hidden');
        document.getElementById('error-message').textContent = 'Cannot reach local server. Ensure server.py is running.';
        statusEl.textContent = 'Error';
    } finally {
        setLoading(false);
    }
}

function setLoading(active, message = 'Scanning local agent usage...') {
    const overlay = document.getElementById('loading-overlay');
    const messageEl = document.getElementById('loading-message');
    if (!overlay) return;
    if (messageEl) messageEl.textContent = message;
    overlay.classList.toggle('hidden', !active);
}

function setupResizeRedraw() {
    let resizeTimer = null;
    window.addEventListener('resize', () => {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(() => {
            Object.keys(charts).forEach(renderChart);
        }, 120);
    });
}

function processRawData(sessions) {
    return sessions.map(s => {
        const gens = s.generations || [];
        let totals = s.totals || {};
        let inTokens = totals.input_tokens ?? sum(gens, 'input_tokens');
        let cachedTokens = totals.cached_tokens ?? sum(gens, 'cached_tokens');
        let cacheWriteTokens = totals.cache_write_tokens ?? sum(gens, 'cache_write_tokens');
        let outTokens = totals.output_tokens ?? sum(gens, 'output_tokens');
        let reasoningTokens = totals.reasoning_tokens ?? sum(gens, 'reasoning_tokens');
        let totalTokens = totals.total_tokens ?? gens.reduce((acc, g) => acc + generationTotal(g), 0);
        let activeTokens = totals.active_tokens ?? gens.reduce((acc, g) => acc + generationActive(g), 0);
        let model = gens.length > 0 ? (gens[0].model || 'Unknown Model') : 'Unknown Model';

        return {
            id: s.session_id || s.conversation_id,
            title: s.title || 'Untitled',
            project: s.project || 'Unknown Project',
            agent: s.agent || 'unknown',
            agentName: s.agent_name || s.agent || 'Unknown Agent',
            time: s.start_time || s.end_time,
            endTime: s.end_time || s.start_time,
            model,
            inTokens,
            cachedTokens,
            cacheWriteTokens,
            outTokens,
            reasoningTokens,
            totalTokens,
            activeTokens,
            generations: gens
        };
    }).sort((a, b) => new Date(b.endTime || b.time || 0) - new Date(a.endTime || a.time || 0));
}

function processRawChats(sessions) {
    let chats = [];
    sessions.forEach(s => {
        (s.generations || []).forEach(g => {
            chats.push({
                agent: s.agent,
                agentName: s.agentName,
                project: s.project,
                sessionId: s.id,
                sessionTitle: s.title,
                chatId: g.chat_id,
                time: g.timestamp || s.time,
                model: g.model || s.model,
                inTokens: g.input_tokens || 0,
                cachedTokens: g.cached_tokens || 0,
                cacheWriteTokens: g.cache_write_tokens || 0,
                outTokens: g.output_tokens || 0,
                reasoningTokens: g.reasoning_tokens || 0,
                totalTokens: generationTotal(g),
                activeTokens: generationActive(g),
                confidence: g.confidence || 'exact'
            });
        });
    });
    return chats.sort((a, b) => new Date(b.time || 0) - new Date(a.time || 0));
}

function generationTotal(g) {
    return g.total_tokens ?? ((g.input_tokens || 0) + (g.cached_tokens || 0) + (g.cache_write_tokens || 0) + (g.output_tokens || 0) + (g.reasoning_tokens || 0));
}

function generationActive(g) {
    return g.active_tokens ?? ((g.input_tokens || 0) + (g.cache_write_tokens || 0) + (g.output_tokens || 0) + (g.reasoning_tokens || 0));
}

function sum(rows, key) {
    return rows.reduce((acc, row) => acc + (row[key] || 0), 0);
}

function populateProjectFilter() {
    const select = document.getElementById('project-filter');
    const current = select.value;
    const projects = new Set();
    rawData.forEach(s => { if (s.project) projects.add(s.project); });
    resetSelect(select, 'All Projects');
    Array.from(projects).sort().forEach(p => appendOption(select, p, p));
    select.value = Array.from(projects).includes(current) ? current : '';
}

function populateAgentFilter() {
    const select = document.getElementById('agent-filter');
    const current = select.value;
    const agents = new Map();
    rawData.forEach(s => { if (s.agent) agents.set(s.agent, s.agentName); });
    resetSelect(select, 'All Agents');
    Array.from(agents.entries()).sort((a, b) => a[1].localeCompare(b[1])).forEach(([id, name]) => appendOption(select, id, name));
    select.value = agents.has(current) ? current : '';
}

function captureLatestScope(summary) {
    const current = summary && summary.current_session ? summary.current_session : {};
    latestScope = {
        agent: current.agent || '',
        project: current.project && current.project !== 'Unknown Project' ? current.project : '',
    };
}

function resetSelect(select, label) {
    while (select.options.length) select.remove(0);
    appendOption(select, '', label);
}

function appendOption(select, value, label) {
    const opt = document.createElement('option');
    opt.value = value;
    opt.textContent = label;
    select.appendChild(opt);
}

function applyFilters() {
    const q = document.getElementById('global-search').value.toLowerCase();
    const project = document.getElementById('project-filter').value;
    const agent = document.getElementById('agent-filter').value;
    const fromValue = document.getElementById('date-from').value;
    const toValue = document.getElementById('date-to').value;
    const dateFrom = fromValue ? new Date(fromValue) : null;
    const dateTo = toValue ? new Date(toValue) : null;
    if (dateTo) dateTo.setHours(23, 59, 59, 999);

    filteredData = rawData.filter(s => {
        if (q && !matchesSearch(s, q)) return false;
        if (project && s.project !== project) return false;
        if (agent && s.agent !== agent) return false;
        return matchesDate(s.endTime || s.time, dateFrom, dateTo);
    });

    filteredChats = rawChats.filter(c => {
        if (q && !matchesSearch(c, q)) return false;
        if (project && c.project !== project) return false;
        if (agent && c.agent !== agent) return false;
        return matchesDate(c.time, dateFrom, dateTo);
    });

    updateMetrics();
    updateRollingUsageUIFromChats();
    updateCharts();
    renderTable();
    renderProjectsTable();
    renderAgentTable();
    renderChatTable();
}

function matchesSearch(row, q) {
    return [row.title, row.sessionTitle, row.project, row.agentName, row.model, row.sessionId]
        .some(value => String(value || '').toLowerCase().includes(q));
}

function matchesDate(value, dateFrom, dateTo) {
    if (!dateFrom && !dateTo) return true;
    if (!value) return false;
    const d = new Date(value);
    if (isNaN(d)) return false;
    if (dateFrom && d < dateFrom) return false;
    if (dateTo && d > dateTo) return false;
    return true;
}

function updateRollingUsageUIFromChats() {
    const now = new Date();
    const fiveHoursAgo = new Date(now.getTime() - (5 * 60 * 60 * 1000));
    const twentyFourHoursAgo = new Date(now.getTime() - (24 * 60 * 60 * 1000));
    const sevenDaysAgo = new Date(now.getTime() - (7 * 24 * 60 * 60 * 1000));
    const thirtyDaysAgo = new Date(now.getTime() - (30 * 24 * 60 * 60 * 1000));

    let tokens5Hr = 0;
    let tokens24Hr = 0;
    let tokensWeek = 0;
    let tokensMonth = 0;
    const sourceChats = rollingUsageSourceChats();
    sourceChats.forEach(c => {
        const d = new Date(c.time);
        if (isNaN(d)) return;
        if (d >= fiveHoursAgo) tokens5Hr += c.activeTokens;
        if (d >= twentyFourHoursAgo) tokens24Hr += c.activeTokens;
        if (d >= sevenDaysAgo) tokensWeek += c.activeTokens;
        if (d >= thirtyDaysAgo) tokensMonth += c.activeTokens;
    });

    updateRollingUsageUI('usage-5hr', tokens5Hr);
    updateRollingUsageUI('usage-24hr', tokens24Hr);
    updateRollingUsageUI('usage-week', tokensWeek);
    updateRollingUsageUI('usage-month', tokensMonth);
}

function rollingUsageSourceChats() {
    if (hasUserFilterInteraction || !latestScope.agent) return filteredChats;
    return rawChats.filter(c => {
        if (latestScope.agent && c.agent !== latestScope.agent) return false;
        if (latestScope.project && c.project !== latestScope.project) return false;
        return true;
    });
}

function updateRollingUsageUI(prefix, used) {
    const text = document.getElementById(`${prefix}-text`);
    const bar = document.getElementById(`${prefix}-bar`);
    bar.className = 'progress-bar';
    used = Number(used || 0);
    text.innerText = formatTokens(used);
    bar.style.width = used ? '100%' : '0%';
    bar.classList.add('usage-only');
}

function renderProjectsTable() {
    const projMap = {};
    filteredData.forEach(s => {
        const key = `${s.agent}::${s.project}`;
        if (!projMap[key]) {
            projMap[key] = { name: s.project, agent: s.agent, agentName: s.agentName, sessions: 0, chats: 0, input: 0, cached: 0, cacheWrites: 0, output: 0, active: 0, total: 0 };
        }
        const bucket = projMap[key];
        bucket.sessions += 1;
        bucket.chats += s.generations.length;
        bucket.input += s.inTokens;
        bucket.cached += s.cachedTokens;
        bucket.cacheWrites += s.cacheWriteTokens;
        bucket.output += s.outTokens;
        bucket.active += s.activeTokens;
        bucket.total += s.totalTokens;
    });

    const tbody = document.getElementById('projects-table-body');
    clearRows(tbody);
    Object.values(projMap).sort((a, b) => b.active - a.active).forEach(p => {
        const tr = document.createElement('tr');
        tr.style.cursor = 'pointer';
        addCell(tr, p.name);
        addCell(tr, p.agentName);
        addCell(tr, p.sessions);
        addCell(tr, p.chats);
        addCell(tr, formatNumber(p.input));
        addCell(tr, formatNumber(p.cached), 'success-cell');
        addCell(tr, formatNumber(p.cacheWrites), 'success-cell');
        addCell(tr, formatNumber(p.output));
        addCell(tr, formatNumber(p.active), 'strong-cell');
        tr.addEventListener('click', () => {
            hasUserFilterInteraction = true;
            document.getElementById('project-filter').value = p.name;
            document.getElementById('agent-filter').value = p.agent;
            applyFilters();
            showView('chats');
        });
        tbody.appendChild(tr);
    });
}

function renderAgentTable() {
    const map = {};
    filteredData.forEach(s => {
        if (!map[s.agent]) {
            map[s.agent] = { agent: s.agent, agentName: s.agentName, sessions: 0, chats: 0, input: 0, cached: 0, cacheWrites: 0, output: 0, active: 0, total: 0 };
        }
        const bucket = map[s.agent];
        bucket.sessions += 1;
        bucket.chats += s.generations.length;
        bucket.input += s.inTokens;
        bucket.cached += s.cachedTokens;
        bucket.cacheWrites += s.cacheWriteTokens;
        bucket.output += s.outTokens;
        bucket.active += s.activeTokens;
        bucket.total += s.totalTokens;
    });

    const rows = Object.values(map).sort((a, b) => b.active - a.active);
    document.getElementById('agent-count').textContent = `${rows.length} agents found`;
    const tbody = document.getElementById('agents-table-body');
    clearRows(tbody);
    rows.forEach(a => {
        const tr = document.createElement('tr');
        tr.style.cursor = 'pointer';
        addCell(tr, a.agentName);
        addCell(tr, a.sessions);
        addCell(tr, a.chats);
        addCell(tr, formatNumber(a.input));
        addCell(tr, formatNumber(a.cached), 'success-cell');
        addCell(tr, formatNumber(a.cacheWrites), 'success-cell');
        addCell(tr, formatNumber(a.output));
        addCell(tr, formatNumber(a.active), 'strong-cell');
        tr.addEventListener('click', () => {
            hasUserFilterInteraction = true;
            document.getElementById('agent-filter').value = a.agent;
            document.getElementById('project-filter').value = '';
            applyFilters();
            showView('projects');
        });
        tbody.appendChild(tr);
    });
}

function updateMetrics() {
    let totIn = 0;
    let totCached = 0;
    let totCacheWrites = 0;
    let totOut = 0;

    filteredData.forEach(s => {
        totIn += s.inTokens;
        totCached += s.cachedTokens;
        totCacheWrites += s.cacheWriteTokens;
        totOut += s.outTokens;
    });

    const tot = filteredData.reduce((acc, s) => acc + s.activeTokens, 0);
    setText("val-input-tokens", formatNumber(totIn));
    setText("val-cached-tokens", formatNumber(totCached + totCacheWrites));
    setText("val-output-tokens", formatNumber(totOut));
    setText("val-total-tokens", formatNumber(tot));
}

function updateCharts() {
    const dailyData = {};
    filteredChats.forEach(c => {
        if (!c.time) return;
        const dStr = c.time.split('T')[0];
        if (!dailyData[dStr]) dailyData[dStr] = { active: 0, in: 0, out: 0 };
        dailyData[dStr].active += c.activeTokens;
        dailyData[dStr].in += c.inTokens;
        dailyData[dStr].out += c.outTokens;
    });

    const sortedDates = Object.keys(dailyData).sort();
    createOrUpdateChart('trendChart', 'line', {
        labels: sortedDates,
        datasets: [
            { label: 'Active Tokens', data: sortedDates.map(d => dailyData[d].active), borderColor: '#84fab0', backgroundColor: 'rgba(132, 250, 176, 0.12)', fill: true, tension: 0.4 },
            { label: 'Output Tokens', data: sortedDates.map(d => dailyData[d].out), borderColor: '#00f2fe', backgroundColor: 'rgba(0, 242, 254, 0.1)', fill: true, tension: 0.4 },
            { label: 'Input Tokens', data: sortedDates.map(d => dailyData[d].in), borderColor: '#a18cd1', backgroundColor: 'rgba(161, 140, 209, 0.1)', fill: true, tension: 0.4 }
        ]
    }, chartOptions());

    const projData = {};
    filteredData.forEach(s => {
        if (!projData[s.project]) projData[s.project] = 0;
        projData[s.project] += s.activeTokens;
    });
    const projLabels = Object.keys(projData).sort((a, b) => projData[b] - projData[a]).slice(0, 5);
    createOrUpdateChart('projectChart', 'doughnut', {
        labels: projLabels.length ? projLabels : ['No Data'],
        datasets: [{ data: projLabels.length ? projLabels.map(l => projData[l]) : [1], backgroundColor: ['#4facfe', '#00f2fe', '#a18cd1', '#fbc2eb', '#84fab0'], borderWidth: 0, hoverOffset: 4 }]
    }, doughnutOptions());

    const modData = {};
    filteredChats.forEach(c => {
        const m = c.model || 'Unknown Model';
        if (!modData[m]) modData[m] = 0;
        modData[m] += c.activeTokens;
    });
    const modLabels = Object.keys(modData).sort((a, b) => modData[b] - modData[a]).slice(0, 8);
    createOrUpdateChart('modelChart', 'doughnut', {
        labels: modLabels.length ? modLabels : ['No Data'],
        datasets: [{ data: modLabels.length ? modLabels.map(l => modData[l]) : [1], backgroundColor: ['#f6d365', '#fda085', '#8fd3f4', '#fbc2eb', '#84fab0', '#4facfe', '#a18cd1', '#00f2fe'], borderWidth: 0, hoverOffset: 4 }]
    }, doughnutOptions());
}

function chartOptions() {
    return {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { labels: { color: '#f8f9fa' } } },
        scales: {
            x: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#9ba1a6' } },
            y: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#9ba1a6' } }
        }
    };
}

function doughnutOptions() {
    return {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { position: 'bottom', labels: { color: '#f8f9fa', padding: 20 } } },
        cutout: '70%'
    };
}

function createOrUpdateChart(id, type, data, options) {
    charts[id] = { type, data, options, hover: charts[id]?.hover || null };
    renderChart(id);
}

function renderChart(id) {
    const chart = charts[id];
    if (!chart) return;
    const canvas = document.getElementById(id);
    const ctx = prepareCanvas(canvas);
    if (!ctx) return;
    chartMeta[id] = chart.type === 'line'
        ? drawLineChart(ctx, canvas, chart.data, chart.hover)
        : drawDoughnutChart(ctx, canvas, chart.data, chart.hover);
    bindChartInteractions(canvas, id, chart.type);
}

function prepareCanvas(canvas) {
    if (!canvas) return null;
    const parentRect = canvas.parentElement ? canvas.parentElement.getBoundingClientRect() : null;
    const rect = canvas.getBoundingClientRect();
    const width = Math.max(320, Math.floor((parentRect && parentRect.width) || rect.width || 320));
    const height = Math.max(220, Math.floor((parentRect && parentRect.height) || rect.height || 220));
    const ratio = window.devicePixelRatio || 1;
    canvas.width = width * ratio;
    canvas.height = height * ratio;
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
    const ctx = canvas.getContext('2d');
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    ctx.clearRect(0, 0, width, height);
    return ctx;
}

function bindChartInteractions(canvas, id, type) {
    if (!canvas || canvas.dataset.boundInteractive === '1') return;
    canvas.dataset.boundInteractive = '1';
    canvas.addEventListener('mousemove', event => {
        const hover = findChartHover(canvas, id, type, event);
        const chart = charts[id];
        if (!chart) return;
        const changed = JSON.stringify(chart.hover || null) !== JSON.stringify(hover || null);
        if (changed) {
            chart.hover = hover;
            renderChart(id);
        }
        canvas.style.cursor = hover ? 'crosshair' : 'default';
    });
    canvas.addEventListener('mouseleave', () => {
        const chart = charts[id];
        if (!chart || !chart.hover) return;
        chart.hover = null;
        canvas.style.cursor = 'default';
        renderChart(id);
    });
}

function findChartHover(canvas, id, type, event) {
    const meta = chartMeta[id];
    if (!meta) return null;
    const rect = canvas.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    if (type === 'line') {
        const points = meta.points || [];
        if (!points.length) return null;
        let nearest = null;
        points.forEach(point => {
            const d = Math.hypot(point.x - x, point.y - y);
            if (!nearest || d < nearest.distance) nearest = { ...point, distance: d };
        });
        return nearest && nearest.distance <= 28 ? { kind: 'point', point: nearest } : null;
    }
    const slices = meta.slices || [];
    const dx = x - meta.cx;
    const dy = y - meta.cy;
    const dist = Math.hypot(dx, dy);
    if (dist < meta.inner || dist > meta.outer + 10) return null;
    let angle = Math.atan2(dy, dx);
    if (angle < -Math.PI / 2) angle += Math.PI * 2;
    return slices.find(slice => angle >= slice.start && angle <= slice.end)
        ? { kind: 'slice', index: slices.findIndex(slice => angle >= slice.start && angle <= slice.end) }
        : null;
}

function drawLineChart(ctx, canvas, data, hover = null) {
    const width = canvas.width / (window.devicePixelRatio || 1);
    const height = canvas.height / (window.devicePixelRatio || 1);
    const pad = { left: 62, right: 24, top: 22, bottom: 52 };
    const chartW = width - pad.left - pad.right;
    const chartH = height - pad.top - pad.bottom;
    const datasets = data.datasets || [];
    const labels = data.labels || [];
    const allValues = datasets.flatMap(ds => ds.data || []);
    const maxValue = Math.max(1, ...allValues);
    const meta = { points: [] };

    ctx.strokeStyle = 'rgba(255,255,255,0.08)';
    ctx.lineWidth = 1;
    ctx.font = '12px system-ui, sans-serif';
    ctx.fillStyle = '#9ba1a6';
    for (let i = 0; i <= 4; i++) {
        const y = pad.top + (chartH * i / 4);
        ctx.beginPath();
        ctx.moveTo(pad.left, y);
        ctx.lineTo(width - pad.right, y);
        ctx.stroke();
        const value = maxValue - (maxValue * i / 4);
        ctx.fillText(formatTokens(value), 8, y + 4);
    }

    if (!labels.length) {
        ctx.fillText('No data', pad.left + chartW / 2 - 24, pad.top + chartH / 2);
        return meta;
    }

    datasets.forEach(ds => {
        const values = ds.data || [];
        const points = values.map((value, idx) => ({
            x: pad.left + (labels.length === 1 ? chartW / 2 : (chartW * idx / (labels.length - 1))),
            y: pad.top + chartH - ((value || 0) / maxValue * chartH),
            value: value || 0,
            label: labels[idx],
            series: ds.label,
            color: ds.borderColor || '#4facfe'
        }));
        meta.points.push(...points);

        if (points.length > 1) {
            const fill = ctx.createLinearGradient(0, pad.top, 0, pad.top + chartH);
            fill.addColorStop(0, colorWithAlpha(ds.borderColor || '#4facfe', 0.18));
            fill.addColorStop(1, colorWithAlpha(ds.borderColor || '#4facfe', 0.02));
            ctx.beginPath();
            points.forEach((point, idx) => {
                if (idx === 0) ctx.moveTo(point.x, point.y);
                else ctx.lineTo(point.x, point.y);
            });
            ctx.lineTo(points[points.length - 1].x, pad.top + chartH);
            ctx.lineTo(points[0].x, pad.top + chartH);
            ctx.closePath();
            ctx.fillStyle = fill;
            ctx.fill();
        }

        ctx.strokeStyle = ds.borderColor || '#4facfe';
        ctx.lineWidth = 3;
        ctx.lineJoin = 'round';
        ctx.lineCap = 'round';
        ctx.shadowColor = colorWithAlpha(ds.borderColor || '#4facfe', 0.28);
        ctx.shadowBlur = 10;
        ctx.beginPath();
        points.forEach((point, idx) => {
            if (idx === 0) ctx.moveTo(point.x, point.y);
            else ctx.lineTo(point.x, point.y);
        });
        ctx.stroke();
        ctx.shadowBlur = 0;
    });

    const step = Math.max(1, Math.ceil(labels.length / 5));
    labels.forEach((label, idx) => {
        if (idx % step !== 0 && idx !== labels.length - 1) return;
        const x = pad.left + (labels.length === 1 ? chartW / 2 : (chartW * idx / (labels.length - 1)));
        ctx.fillStyle = '#9ba1a6';
        ctx.fillText(label, Math.max(pad.left, x - 34), height - 14);
    });

    drawLegend(ctx, datasets.map(ds => ({ label: ds.label, color: ds.borderColor })), pad.left, 8);
    if (hover && hover.kind === 'point' && hover.point) {
        drawLineHover(ctx, hover.point, pad, chartH, width);
    }
    return meta;
}

function drawLineHover(ctx, point, pad, chartH, width) {
    ctx.save();
    ctx.strokeStyle = colorWithAlpha(point.color, 0.5);
    ctx.lineWidth = 1;
    ctx.setLineDash([4, 6]);
    ctx.beginPath();
    ctx.moveTo(point.x, pad.top);
    ctx.lineTo(point.x, pad.top + chartH);
    ctx.stroke();
    ctx.setLineDash([]);

    ctx.fillStyle = point.color;
    ctx.beginPath();
    ctx.arc(point.x, point.y, 5, 0, Math.PI * 2);
    ctx.fill();
    ctx.strokeStyle = '#0b0c10';
    ctx.lineWidth = 3;
    ctx.stroke();

    const title = String(point.label || '');
    const value = `${point.series}: ${formatTokens(point.value)}`;
    ctx.font = '600 12px system-ui, sans-serif';
    const boxW = Math.max(ctx.measureText(title).width, ctx.measureText(value).width) + 28;
    const boxH = 54;
    const boxX = Math.min(width - boxW - 12, Math.max(12, point.x + 14));
    const boxY = Math.max(12, point.y - boxH - 14);
    drawTooltipBox(ctx, boxX, boxY, boxW, boxH);
    ctx.fillStyle = '#f8f9fa';
    ctx.fillText(title, boxX + 14, boxY + 21);
    ctx.fillStyle = '#9ba1a6';
    ctx.font = '12px system-ui, sans-serif';
    ctx.fillText(value, boxX + 14, boxY + 39);
    ctx.restore();
}

function drawDoughnutChart(ctx, canvas, data, hover = null) {
    const width = canvas.width / (window.devicePixelRatio || 1);
    const height = canvas.height / (window.devicePixelRatio || 1);
    const labels = data.labels || [];
    const dataset = (data.datasets || [])[0] || {};
    const values = dataset.data || [];
    const colors = dataset.backgroundColor || ['#4facfe'];
    const total = values.reduce((acc, value) => acc + (value || 0), 0) || 1;
    const cx = width / 2;
    const cy = Math.max(80, height / 2 - 18);
    const outer = Math.min(width, height) * 0.28;
    const inner = outer * 0.62;
    const hoverIndex = hover && hover.kind === 'slice' ? hover.index : -1;
    const meta = { slices: [], cx, cy, inner, outer };
    let start = -Math.PI / 2;

    values.forEach((value, idx) => {
        const slice = (value || 0) / total * Math.PI * 2;
        const end = start + slice;
        const isHover = idx === hoverIndex;
        const drawOuter = isHover ? outer + 8 : outer;
        const mid = start + slice / 2;
        const lift = isHover ? 5 : 0;
        const offsetX = Math.cos(mid) * lift;
        const offsetY = Math.sin(mid) * lift;
        meta.slices.push({ start, end, label: labels[idx], value: value || 0, color: colors[idx % colors.length] });

        ctx.save();
        ctx.translate(offsetX, offsetY);
        if (isHover) {
            ctx.shadowColor = colorWithAlpha(colors[idx % colors.length], 0.38);
            ctx.shadowBlur = 18;
        }
        ctx.beginPath();
        ctx.arc(cx, cy, drawOuter, start, end);
        ctx.arc(cx, cy, inner, end, start, true);
        ctx.closePath();
        ctx.fillStyle = colors[idx % colors.length];
        ctx.fill();
        ctx.restore();
        start = end;
    });

    const centerLabel = hoverIndex >= 0 ? labels[hoverIndex] : '';
    const centerValue = hoverIndex >= 0 ? values[hoverIndex] : total;
    ctx.fillStyle = '#f8f9fa';
    ctx.font = '600 16px system-ui, sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(formatTokens(centerValue), cx, cy + (centerLabel ? 0 : 5));
    if (centerLabel) {
        ctx.fillStyle = '#9ba1a6';
        ctx.font = '11px system-ui, sans-serif';
        ctx.fillText(String(centerLabel).slice(0, 18), cx, cy + 18);
    }
    ctx.textAlign = 'start';
    drawLegend(ctx, labels.map((label, idx) => ({ label, color: colors[idx % colors.length] })), 16, height - 54);
    return meta;
}

function colorWithAlpha(color, alpha) {
    if (!color) return `rgba(79, 172, 254, ${alpha})`;
    if (color.startsWith('#')) {
        const hex = color.slice(1);
        const full = hex.length === 3 ? hex.split('').map(ch => ch + ch).join('') : hex;
        const intValue = parseInt(full, 16);
        const r = (intValue >> 16) & 255;
        const g = (intValue >> 8) & 255;
        const b = intValue & 255;
        return `rgba(${r}, ${g}, ${b}, ${alpha})`;
    }
    const rgba = color.match(/rgba?\(([^)]+)\)/);
    if (rgba) {
        const parts = rgba[1].split(',').slice(0, 3).map(part => part.trim());
        return `rgba(${parts.join(', ')}, ${alpha})`;
    }
    return color;
}

function drawTooltipBox(ctx, x, y, width, height) {
    const radius = 10;
    ctx.save();
    ctx.fillStyle = 'rgba(12, 15, 24, 0.94)';
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.12)';
    ctx.lineWidth = 1;
    ctx.shadowColor = 'rgba(0, 0, 0, 0.36)';
    ctx.shadowBlur = 18;
    ctx.beginPath();
    ctx.moveTo(x + radius, y);
    ctx.lineTo(x + width - radius, y);
    ctx.quadraticCurveTo(x + width, y, x + width, y + radius);
    ctx.lineTo(x + width, y + height - radius);
    ctx.quadraticCurveTo(x + width, y + height, x + width - radius, y + height);
    ctx.lineTo(x + radius, y + height);
    ctx.quadraticCurveTo(x, y + height, x, y + height - radius);
    ctx.lineTo(x, y + radius);
    ctx.quadraticCurveTo(x, y, x + radius, y);
    ctx.closePath();
    ctx.fill();
    ctx.shadowBlur = 0;
    ctx.stroke();
    ctx.restore();
}

function drawLegend(ctx, items, x, y) {
    ctx.font = '12px system-ui, sans-serif';
    let cursorX = x;
    let cursorY = y;
    items.slice(0, 6).forEach(item => {
        const label = String(item.label || 'Unknown');
        const width = Math.min(160, ctx.measureText(label).width + 28);
        if (cursorX + width > ctx.canvas.width / (window.devicePixelRatio || 1) - 12) {
            cursorX = x;
            cursorY += 18;
        }
        ctx.fillStyle = item.color || '#4facfe';
        ctx.fillRect(cursorX, cursorY, 10, 10);
        ctx.fillStyle = '#9ba1a6';
        ctx.fillText(label.length > 18 ? label.slice(0, 17) + '...' : label, cursorX + 16, cursorY + 10);
        cursorX += width;
    });
}

function renderTable() {
    const tbody = document.getElementById('sessions-table-body');
    clearRows(tbody);
    document.getElementById('session-count').textContent = `${filteredData.length} sessions found`;

    filteredData.slice(0, 100).forEach(s => {
        const tr = document.createElement('tr');
        addCell(tr, formatDate(s.endTime || s.time));
        addBadgeCell(tr, s.agentName);
        addCell(tr, s.title, 'title-cell', s.title);
        addBadgeCell(tr, s.project);
        addCell(tr, s.model);
        addCell(tr, formatNumber(s.inTokens));
        addCell(tr, formatNumber(s.cachedTokens + s.cacheWriteTokens), 'success-cell');
        addCell(tr, formatNumber(s.outTokens));
        addCell(tr, formatNumber(s.activeTokens), 'strong-cell');
        tbody.appendChild(tr);
    });
}

function renderChatTable() {
    const tbody = document.getElementById('chats-table-body');
    clearRows(tbody);
    document.getElementById('chat-count').textContent = `${filteredChats.length} chats found`;

    filteredChats.slice(0, 500).forEach(c => {
        const tr = document.createElement('tr');
        addCell(tr, formatDate(c.time));
        addBadgeCell(tr, c.agentName);
        addBadgeCell(tr, c.project);
        addCell(tr, c.sessionTitle, 'title-cell', c.sessionTitle);
        addCell(tr, c.model);
        addCell(tr, formatNumber(c.inTokens));
        addCell(tr, formatNumber(c.cachedTokens), 'success-cell');
        addCell(tr, formatNumber(c.cacheWriteTokens), 'success-cell');
        addCell(tr, formatNumber(c.outTokens));
        addCell(tr, formatNumber(c.activeTokens), 'strong-cell');
        tbody.appendChild(tr);
    });
}

function clearRows(tbody) {
    while (tbody.firstChild) tbody.removeChild(tbody.firstChild);
}

function addCell(tr, value, className = '', title = '') {
    const td = document.createElement('td');
    td.textContent = value === null || value === undefined ? '' : String(value);
    if (className) td.className = className;
    if (title) td.title = title;
    tr.appendChild(td);
    return td;
}

function addBadgeCell(tr, value) {
    const td = document.createElement('td');
    const span = document.createElement('span');
    span.className = 'project-badge';
    span.textContent = value || 'Unknown';
    td.appendChild(span);
    tr.appendChild(td);
    return td;
}

function setText(id, value) {
    document.getElementById(id).textContent = value;
}
