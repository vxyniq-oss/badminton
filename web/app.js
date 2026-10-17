/* PSAL Badminton — web app (phone-first). Plain JavaScript, no frameworks.
   Everything shown on screen goes through html`` which escapes text, so names
   or notes can never inject code. */
'use strict';
(() => {
  // ------------------------------------------------------------------ basics
  const app = document.getElementById('app');
  const sheetRoot = document.getElementById('sheet-root');
  const toastsEl = document.getElementById('toasts');
  class Raw { constructor(s) { this.s = s; } toString() { return this.s; } }
  const raw = (s) => new Raw(s);
  const ESC = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ESC[c]);
  const rv = (v) => (v == null || v === false || v === true) ? '' : v instanceof Raw ? v.s
    : Array.isArray(v) ? v.map(rv).join('') : esc(v);
  function html(str, ...vals) { let o = str[0]; for (let i = 0; i < vals.length; i++) o += rv(vals[i]) + str[i + 1]; return new Raw(o); }
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => Array.from(el.querySelectorAll(s));
  const store = { get(k, d) { try { const v = localStorage.getItem('psal.' + k); return v == null ? d : v; } catch { return d; } },
    set(k, v) { try { localStorage.setItem('psal.' + k, v); } catch { /* private mode */ } } };
  const pad = (n) => String(n).padStart(2, '0');
  const today = () => { const d = new Date(); return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`; };
  const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  function niceDate(iso) { const m = /^(\d{4})-(\d\d)-(\d\d)/.exec(iso || ''); return m ? `${MON[+m[2] - 1]} ${+m[3]}, ${m[1]}` : (iso || ''); }
  function niceTs(iso) {
    const d = new Date(iso); if (isNaN(d)) return iso || '';
    let h = d.getHours(); const ap = h >= 12 ? 'PM' : 'AM'; h = h % 12 || 12;
    return `${MON[d.getMonth()]} ${d.getDate()} · ${h}:${pad(d.getMinutes())} ${ap}`;
  }
  const initials = (n) => { const p = String(n || '').split(/\s+/).filter(Boolean); return p.length ? (p[0][0] + (p.length > 1 ? p[p.length - 1][0] : '')).toUpperCase() : '?'; };
  function ytId(url) {
    const m = /(?:youtu\.be\/|v=|\/embed\/|\/shorts\/|\/live\/)([A-Za-z0-9_-]{11})/.exec(url || '');
    return m ? m[1] : (/^[A-Za-z0-9_-]{11}$/.test(url || '') ? url : null);
  }

  // ------------------------------------------------------------------- icons
  const P = {
    home: '<path d="M3 11l9-7 9 7"/><path d="M5 10v10h14V10"/>',
    users: '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c.8-3.6 3.4-5.5 6.5-5.5s5.7 1.9 6.5 5.5"/><path d="M16 4.6a3.5 3.5 0 0 1 0 6.8"/><path d="M18.5 14.8c1.6.7 2.6 2.4 3 5.2"/>',
    grid: '<rect x="3" y="3" width="7.5" height="7.5" rx="1.5"/><rect x="13.5" y="3" width="7.5" height="7.5" rx="1.5"/><rect x="3" y="13.5" width="7.5" height="7.5" rx="1.5"/><rect x="13.5" y="13.5" width="7.5" height="7.5" rx="1.5"/>',
    flag: '<path d="M5 21V4"/><path d="M5 4h11l-2 4 2 4H5"/>',
    check: '<rect x="3" y="3" width="18" height="18" rx="4"/><path d="M8 12.5l3 3 5-6"/>',
    quiz: '<circle cx="12" cy="12" r="9"/><path d="M9.6 9.4a2.5 2.5 0 1 1 3.4 2.4c-.7.3-1 .8-1 1.5v.4"/><circle cx="12" cy="17" r=".7" fill="currentColor"/>',
    play: '<rect x="2.5" y="5" width="19" height="14" rx="3"/><path d="M10 9l5 3-5 3z" fill="currentColor"/>',
    star: '<path d="M12 3.5l2.6 5.3 5.9.9-4.3 4.1 1 5.8-5.2-2.8-5.2 2.8 1-5.8-4.3-4.1 5.9-.9z"/>',
    target: '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1.2" fill="currentColor"/>',
    edit: '<path d="M4 20h4L19 9l-4-4L4 16z"/><path d="M13.5 6.5l4 4"/>',
    clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    gear: '<circle cx="12" cy="12" r="3.2"/><path d="M12 2.8v2.4M12 18.8v2.4M2.8 12h2.4M18.8 12h2.4M5.5 5.5l1.7 1.7M16.8 16.8l1.7 1.7M5.5 18.5l1.7-1.7M16.8 7.2l1.7-1.7"/>',
    up: '<path d="M12 19V5"/><path d="M6 11l6-6 6 6"/><path d="M5 21h14"/>',
    more: '<circle cx="5" cy="12" r="1.7" fill="currentColor"/><circle cx="12" cy="12" r="1.7" fill="currentColor"/><circle cx="19" cy="12" r="1.7" fill="currentColor"/>',
    out: '<path d="M14 4h4a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-4"/><path d="M9 16l-4-4 4-4"/><path d="M5 12h11"/>',
    moon: '<path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5z"/>',
    sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    key: '<circle cx="8" cy="15" r="4"/><path d="M11 12l9-9M17 6l3 3"/>',
  };
  const icon = (n) => raw(`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${P[n] || ''}</svg>`);

  // ------------------------------------------------------------------- theme
  const mq = window.matchMedia ? window.matchMedia('(prefers-color-scheme: light)') : null;
  function applyTheme() {
    const pref = store.get('theme', 'auto');
    const t = pref === 'auto' ? (mq && mq.matches ? 'light' : 'dark') : pref;
    document.documentElement.dataset.theme = t;
    return t;
  }
  applyTheme();
  if (mq && mq.addEventListener) mq.addEventListener('change', applyTheme);

  // ------------------------------------------------------------------- state
  let S = null;            // everything the server sent (filtered for this person)
  let LOGIN = null;        // shown when signed out
  let PMAP = {};
  const UI = {
    route: '', roster: { q: '', f: 'All' }, lb: { f: 'All' }, matches: { tab: null, res: {}, home: 'Home' },
    prac: { tab: 'Attendance', date: today(), status: {}, reasons: {}, loaded: null, saved: false, scrType: 'Singles', scrWin: 'A', recent: 'Practices' },
    lib: { quiz: { level: 'All', cat: 'All' }, optional: { level: 'All', cat: 'All' }, who: '', status: {} },
    notes: { f: 'Open', prio: 'Medium' }, ru: { f: 'Open' }, act: { n: 60 }, tr: { effort: '4', pointsTouched: false },
    login: { tab: null, mode: 'login', step: 'code', players: [], code: '' }, ch: { win: 'challenger' },
  };
  const DIRTY = new Set();
  const POS_COLORS = { S1: '#F5B83D', S2: '#60A5FA', S3: '#2DD4BF', D1: '#A78BFA', D2: '#F472B6' };
  const PRIO_COLORS = { High: '#EF4444', Medium: '#F5B83D', Low: '#22C55E' };
  const STATUS_COLORS = { pending: '#F5B83D', scheduled: '#4F8CFF', passed: '#22C55E', failed: '#EF4444', cancelled: '#8B94A5' };
  const LEVEL_BLURB = { Beginner: 'Start here — the basics every player needs.', Intermediate: 'Sharpen technique once the basics feel easy.', Expert: 'Advanced skills — worth the most points.' };

  function setState(st) {
    S = st; PMAP = {};
    for (const p of S.players) PMAP[p.id] = p;
    document.body.classList.toggle('mgr', S.me.role === 'manager');
    store.set('hello', S.me.greeting);
    paint();
  }
  const can = (perm) => !!S && S.me.perms.includes(perm);
  const staff = () => S && (S.me.role === 'coach' || S.me.role === 'manager');
  const isCoach = () => S && S.me.role === 'coach';
  const me = () => (S && S.me.pid ? PMAP[S.me.pid] : null);
  const pname = (id) => (PMAP[id] ? PMAP[id].name : '(removed player)');
  const roster = () => S.players.filter((p) => p.active && p.role !== 'manager');
  const byName = (a, b) => a.name.localeCompare(b.name);
  const L = (pos) => S.consts.labels[pos];
  const levelName = (lvl) => { const r = S.consts.ranks; return lvl < r.length ? r[lvl].name : `Legend ${lvl - r.length + 2}`; };

  // --------------------------------------------------------------- network
  async function req(path, opts = {}) {
    const headers = { 'X-PSAL': '1', ...(opts.headers || {}) };
    if (opts.body && !(opts.body instanceof FormData)) headers['Content-Type'] = 'application/json';
    let r;
    try { r = await fetch(path, { credentials: 'same-origin', ...opts, headers }); }
    catch { throw new Error("Can't reach the team website. Check your internet connection."); }
    let data = {};
    try { data = await r.json(); } catch { /* not json */ }
    if (r.status === 401 && data.signin) { signedOut(); throw new Error(data.error || 'Please sign in again.'); }
    if (!r.ok) throw new Error(data.error || `Something went wrong (${r.status}).`);
    return data;
  }
  async function act(name, body = {}, { quiet = false, keepForm = false } = {}) {
    const data = await req('/api/do/' + name, { method: 'POST', body: JSON.stringify(body) });
    if (data.state) { if (!keepForm) DIRTY.clear(); setState(data.state); }
    if (data.msg && !quiet) toast(data.msg, 'success');
    for (const e of data.events || []) toast(e, / moved down to /.test(e) ? 'error' : / qualified for /.test(e) ? 'qual' : 'rank', 6500);
    return data.result;
  }
  // run an action from a button: shows busy state, reports errors
  async function run(btn, fn) {
    if (btn) btn.classList.add('busy');
    try { return await fn(); }
    catch (e) { toast(e.message, 'error', 6000); return undefined; }
    finally { if (btn && btn.isConnected) btn.classList.remove('busy'); }
  }
  let polling = false;
  async function poll() {
    if (!S || polling || document.visibilityState !== 'visible') return;
    polling = true;
    try {
      const d = await req(`/api/state?v=${encodeURIComponent(S.v)}&u=${encodeURIComponent(S.me.username || '')}`);
      if (d.signin) { signedOut(); return; }
      if (!d.same) setState(d);
    } catch { /* offline for a moment — try again next time */ }
    finally { polling = false; }
  }
  setInterval(poll, 20000);
  document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible') poll(); });
  window.addEventListener('focus', poll);

  function signedOut() { S = null; closeAllSheets(); boot(); }

  // ----------------------------------------------------------------- toasts
  function toast(msg, kind = 'info', ms = 4000) {
    const t = document.createElement('div');
    t.className = 'toast ' + kind;
    t.textContent = ({ rank: 'RANK UP  ', qual: 'QUALIFIED  ' }[kind] || '') + msg;
    toastsEl.appendChild(t);
    setTimeout(() => t.remove(), ms);
    while (toastsEl.children.length > 4) toastsEl.firstChild.remove();
  }

  // ------------------------------------------------------------------ sheets
  const sheets = [];
  function openSheet(content, { wide = false, onClose = null } = {}) {
    const veil = document.createElement('div');
    veil.className = 'veil';
    veil.innerHTML = `<div class="sheet ${wide ? 'wide' : ''}" role="dialog" aria-modal="true"><div class="grab"></div><div class="sheet-body"></div></div>`;
    const body = $('.sheet-body', veil);
    body.innerHTML = rv(content);
    veil.addEventListener('mousedown', (e) => { if (e.target === veil) closeSheet(); });
    sheetRoot.appendChild(veil);
    sheets.push({ veil, onClose });
    document.body.style.overflow = 'hidden';
    const first = $('input:not([type=hidden]):not([type=radio]):not([type=checkbox]), textarea', body);
    if (first && window.innerWidth > 700) setTimeout(() => first.focus(), 60);
    return body;
  }
  function closeSheet() {
    const s = sheets.pop(); if (!s) return;
    s.veil.remove();
    if (!sheets.length) document.body.style.overflow = '';
    if (s.onClose) s.onClose();
  }
  function closeAllSheets() { while (sheets.length) closeSheet(); }
  const topSheet = () => (sheets.length ? $('.sheet-body', sheets[sheets.length - 1].veil) : null);
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && sheets.length) closeSheet(); });

  function confirmSheet(title, message, okText, onOk, { danger = false } = {}) {
    const b = openSheet(html`<h2>${title}</h2><p class="muted" style="white-space:pre-line">${message}</p>
      <div class="acts"><button class="btn ghost" data-a="close">Cancel</button>
      <button class="btn ${danger ? 'danger' : ''}" data-a="confirm-ok">${okText}</button></div>`);
    $('[data-a="confirm-ok"]', b)._ok = onOk;
  }

  // ------------------------------------------------------------- ui pieces
  const chip = (text, color, cls = '') => html`<span class="chip ${cls}" style="${color ? `background:${color}` : ''}">${text}</span>`;
  const av = (name, color, lg) => html`<div class="av ${lg ? 'lg' : ''}" style="background:${color || '#60A5FA'}">${initials(name)}</div>`;
  const bar = (frac, color) => html`<div class="bar"><i style="width:${Math.round(Math.max(0, Math.min(1, frac || 0)) * 100)}%;background:${color}"></i></div>`;
  const posChip = (pos) => (pos ? chip(L(pos), POS_COLORS[pos]) : chip('Bench', '', 'plain'));
  const empty = (title, hint) => html`<div class="empty"><b>${title}</b>${hint || ''}</div>`;
  function seg(name, values, cur, { block = false, cls = '' } = {}) {
    return html`<div class="seg ${block ? 'block' : ''} ${cls}" data-seg="${name}">${values.map((v) => {
      const [val, lab] = Array.isArray(v) ? v : [v, v];
      return html`<button type="button" class="${String(val) === String(cur) ? 'on' : ''}" data-a="seg" data-v="${val}">${lab}</button>`;
    })}</div>`;
  }
  const segVal = (name, root = document) => { const b = $(`[data-seg="${name}"] button.on`, root); return b ? b.dataset.v : null; };
  function sel(id, options, value, { attrs = '', placeholder = null } = {}) {
    return html`<select class="in" id="${id}" ${raw(attrs)}>${placeholder !== null ? html`<option value="">${placeholder}</option>` : ''}${options.map((o) => {
      const [v, t] = Array.isArray(o) ? o : [o, o];
      return html`<option value="${v}" ${String(v) === String(value) ? raw('selected') : ''}>${t}</option>`;
    })}</select>`;
  }
  const playerOpts = (list) => list.slice().sort(byName).map((p) => [p.id, p.name]);
  const field = (label, inner) => html`<div class="field"><label>${label}</label>${inner}</div>`;
  const val = (id, root = document) => { const el = root.querySelector('#' + id); return el ? el.value.trim() : ''; };
  // skill-based points — same formula as the server (data_store.win_chance / elo_multiplier)
  const srOf = (id) => (PMAP[id] && PMAP[id].sr != null ? PMAP[id].sr : S.rules.elo.start);
  function winChance(a, b) {
    const ra = a.reduce((t, id) => t + srOf(id), 0) / a.length, rb = b.reduce((t, id) => t + srOf(id), 0) / b.length;
    return 1 / (1 + Math.pow(10, (rb - ra) / 400));
  }
  function eloMult(ch) { const E = S.rules.elo; if (!E.k) return 1; return Math.max(E.min_pct / 100, Math.min(E.max_pct / 100, 2 * (1 - ch))); }
  const ptsOf = (base, m) => Math.max(1, Math.floor(Math.abs(base) * m + 0.5));
  const pct = (x) => Math.round(x * 100) + '%';
  const tag = (m) => (m >= 1.15 ? ' — upset!' : m <= 0.85 ? ' — expected' : '');
  function rankStatus(p) {
    if (p.rankup) return chip('Match ' + p.rankup.status, '', 'soft');
    if (p.qualified) return chip('Qualified', '', 'lime');
    return html`<span class="tiny muted">${p.need} to qualify</span>`;
  }

  // --------------------------------------------------------------- painting
  function snapshot() {
    const vals = {};
    for (const id of DIRTY) { const el = document.getElementById(id); if (el && el.closest('#app')) vals[id] = el.type === 'checkbox' ? el.checked : el.value; }
    const a = document.activeElement;
    return { vals, focus: a && a.id && a.closest('#app') ? a.id : null, sel: a && 'selectionStart' in a ? [a.selectionStart, a.selectionEnd] : null };
  }
  function restore(snap) {
    for (const [id, v] of Object.entries(snap.vals)) { const el = document.getElementById(id); if (!el) continue; if (el.type === 'checkbox') el.checked = v; else el.value = v; }
    if (snap.focus) { const el = document.getElementById(snap.focus); if (el) { el.focus({ preventScroll: true }); try { if (snap.sel) el.setSelectionRange(...snap.sel); } catch { /* not text */ } } }
  }
  function paint() {
    if (!S) return;
    const r = allowedRoute(UI.route) ? UI.route : defaultRoute();
    UI.route = r;
    const y = window.scrollY;
    const snap = snapshot();
    app.innerHTML = layout(VIEWS[r]()).s;
    restore(snap);
    window.scrollTo(0, y);
    afterPaint();
  }
  function paintPart(id, content) { const el = document.getElementById(id); if (el) el.innerHTML = rv(content); }
  document.addEventListener('input', (e) => { if (e.target.id) DIRTY.add(e.target.id); });
  document.addEventListener('change', (e) => { if (e.target.id) DIRTY.add(e.target.id); });

  // -------------------------------------------------------------- routing
  const NAV = [
    { k: 'home', t: 'Home', i: 'home' },
    { k: 'rankups', t: 'Rank-Up Matches', i: 'up', perm: 'rank' },
    { k: 'roster', t: 'Roster', i: 'users' },
    { k: 'lineup', t: 'Lineup & Challenges', i: 'grid' },
    { k: 'matches', t: 'PSAL Matches', i: 'flag' },
    { k: 'practice', t: 'Practice & Points', i: 'check', perm: 'practice' },
    { k: 'quizzes', t: 'Video Quizzes', i: 'quiz' },
    { k: 'videos', t: 'Optional Training', i: 'play' },
    { k: 'leaderboard', t: 'Leaderboard', i: 'star' },
    { k: 'training', t: '1S Training', i: 'target', perm: 'training' },
    { k: 'notes', t: 'Improvement Notes', i: 'edit', perm: 'notes' },
    { k: 'activity', t: 'Activity', i: 'clock', perm: 'rank' },
    { k: 'settings', t: 'Settings', i: 'gear', perm: 'settings' },
  ];
  const TABS = { player: ['home', 'quizzes', 'videos', 'leaderboard', 'more'], coach: ['home', 'roster', 'practice', 'rankups', 'more'],
    manager: ['rankups', 'home', 'practice', 'quizzes', 'more'] };
  const navItem = (k) => NAV.find((n) => n.k === k) || { k: 'more', t: 'More', i: 'more' };
  const allowedRoute = (r) => r === 'more' || NAV.some((n) => n.k === r && (!n.perm || can(n.perm)));
  const defaultRoute = () => (S.me.role === 'manager' ? 'rankups' : 'home');
  function onHash() {
    const r = (location.hash.replace(/^#\/?/, '') || '').split('?')[0];
    const next = r && (r === 'more' || NAV.some((n) => n.k === r)) ? r : '';
    const changed = next !== UI.route;
    UI.route = next || (S ? defaultRoute() : '');
    if (!S) return;
    if (changed) { DIRTY.clear(); window.scrollTo(0, 0); }
    paint();
    if (changed) enterRoute(UI.route);
  }
  window.addEventListener('hashchange', onHash);
  function go(r) { if (location.hash !== '#/' + r) location.hash = '#/' + r; else onHash(); }

  function badge(k) {
    if (k === 'rankups' && S.rankups && staff()) { const n = S.rankups.filter((r) => r.status === 'pending').length; return n ? html`<span class="dot">${n}</span>` : ''; }
    return '';
  }
  function layout(inner) {
    const tabs = TABS[S.me.role] || TABS.player;
    const cur = UI.route;
    const title = cur === 'more' ? 'More' : navItem(cur).t;
    const dark = document.documentElement.dataset.theme === 'dark';
    return html`<div class="shell">
      <aside class="sidebar">
        <div class="brand"><img src="/icon-192.png" alt=""><div><div class="n">${S.team.name}</div><div class="s">Season ${S.team.season}</div></div></div>
        <nav class="side-nav">${NAV.filter((n) => allowedRoute(n.k)).map((n) => html`<a href="#/${n.k}" class="${n.k === cur ? 'on' : ''}">${icon(n.i)}<span>${n.t}</span>${badge(n.k)}</a>`)}</nav>
        <div class="side-foot">
          <div class="me-card">${av(S.me.display || S.me.role, roleColor(), false)}<div class="grow"><div class="bold ellipsis">${S.me.display || S.me.username || 'Signed in'}</div>${chip(roleName(), roleColor())}</div></div>
          <div class="row"><button class="btn ghost sm grow" data-a="theme">${icon(dark ? 'sun' : 'moon')}${dark ? 'Light' : 'Dark'}</button><button class="btn ghost sm grow" data-a="logout">${icon('out')}Sign out</button></div>
        </div>
      </aside>
      <div class="col">
        <header class="topbar"><img class="logo" src="/icon-192.png" alt=""><div class="t ellipsis">${title}</div>
          <button class="btn ghost sm" data-a="theme" aria-label="Switch theme">${icon(dark ? 'sun' : 'moon')}</button></header>
        <main class="main" id="view">${inner}</main>
      </div>
      <nav class="tabbar">${tabs.map((k) => { const n = navItem(k); return html`<a href="#/${k}" class="${k === cur ? 'on' : ''}">${icon(n.i)}<span>${k === 'more' ? 'More' : shortName(k)}</span>${badge(k)}</a>`; })}</nav>
    </div>`;
  }
  const shortName = (k) => ({ home: 'Home', roster: 'Roster', practice: 'Practice', rankups: 'Rank-ups', quizzes: 'Quizzes', videos: 'Training', leaderboard: 'Ranks' }[k] || navItem(k).t);
  const roleName = () => ({ coach: 'Coach', manager: 'Manager', player: 'Player' }[S.me.role]);
  const roleColor = () => ({ coach: '#F5B83D', manager: '#A78BFA', player: '#60A5FA' }[S.me.role]);
  const pageHead = (title, sub, actions) => html`<div class="page-head"><div><h1>${title}</h1>${sub ? html`<p>${sub}</p>` : ''}</div>${actions ? html`<div class="row wrap gap6">${actions}</div>` : ''}</div>`;

  // things to do when a page is opened (load data the page needs)
  function enterRoute(r) {
    if (r === 'practice' && UI.prac.loaded !== UI.prac.date) loadAttendance();
  }
  function afterPaint() {
    if (UI.route === 'practice' && UI.prac.tab === 'Scrimmage') paintPart('scr-prev', scrPreview());
    if (UI.route === 'lineup') paintPart('ch-prev', chPreview());
  }

  // ============================================================ PAGES
  const VIEWS = {};

  // ---------------------------------------------------------------- home
  VIEWS.home = () => {
    const w = S.record[0], l = S.record[1];
    const board = roster();
    const top = board[0];
    const openNotes = (S.notes || []).filter((n) => !n.resolved);
    const pending = (S.rankups || []).filter((r) => r.status === 'pending').length;
    const stats = [['Players', board.length, `${S.managers.length} manager(s)`], ['Team record', `${w}-${l}`, `${w + l} PSAL matches`],
      ['Top player', top ? top.name : '—', top ? `${top.points} pts` : 'Add players']];
    if (staff()) {
      stats.push(['Rank-up requests', pending, 'waiting for a manager']);
      stats.push(['Open notes', openNotes.length, `${openNotes.filter((n) => n.priority === 'High').length} high priority`]);
    }
    const d = new Date();
    return html`
      <div class="hero"><h1>${S.me.greeting}</h1>
        <div class="sub">${['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'][d.getDay()]}, ${MON[d.getMonth()]} ${d.getDate()} · ${S.team.name} · Season record ${w}-${l}</div></div>
      <div class="mt">${progressCard()}</div>
      <div class="stats ${staff() ? 's5' : ''} mt">${stats.map(([t, v, s]) => html`<div class="stat"><div class="kicker">${t}</div><div class="v">${v}</div><div class="sub">${s}</div></div>`)}</div>
      <div class="g2 mt">
        <div class="card"><div class="card-h"><h2>Current lineup</h2><a href="#/lineup" class="small">Open</a></div>${lineupRows()}</div>
        <div class="card"><div class="card-h"><div><h2>Top 5</h2><div class="sub">Every ${S.rules.step} points = a rank-up match</div></div><a href="#/leaderboard" class="small">All</a></div>
          <div class="list">${board.slice(0, 5).map((p, i) => html`<div class="item tap" data-a="player" data-id="${p.id}"><div class="rank-n">${i + 1}</div>${av(p.name, p.color)}
            <div class="grow"><div class="name ellipsis">${p.name}</div>${bar(p.frac, p.color)}</div>${chip(p.rank, p.color)}<div class="pts">${p.points}</div></div>`)}
            ${board.length ? '' : empty('No players yet', staff() ? 'Add your team in Roster.' : '')}</div></div>
      </div>
      ${staff() ? html`<div class="g2 mt">
        <div class="card"><div class="card-h"><h2>Recent activity</h2><a href="#/activity" class="small">All</a></div>
          ${(S.activity || []).slice(0, 6).map((a) => html`<div class="row" style="align-items:flex-start;margin-top:8px"><span class="status-dot"></span><div class="grow"><div>${a.text}</div><div class="tiny muted">${a.by} · ${niceTs(a.ts)}</div></div></div>`)}
          ${(S.activity || []).length ? '' : empty('Nothing yet')}</div>
        <div class="card"><div class="card-h"><div><h2>Who needs to improve</h2><div class="sub">Open notes, highest priority first</div></div>${can('notes') ? html`<a href="#/notes" class="small">Notes</a>` : ''}</div>
          ${openNotes.sort((a, b) => S.consts.priorities.indexOf(a.priority) - S.consts.priorities.indexOf(b.priority)).slice(0, 6).map((n) => html`<div class="row" style="margin-top:8px">${chip(n.priority, PRIO_COLORS[n.priority])}<span class="bold ellipsis">${pname(n.pid)} — ${n.area}</span></div>`)}
          ${openNotes.length ? '' : empty('No open notes')}</div>
      </div>` : ''}`;
  };
  function lineupRows() {
    return S.consts.positions.map((pos) => {
      const ids = S.lineup[pos] || [];
      return html`<div class="lineup-row"><span class="lbar" style="background:${POS_COLORS[pos]}"></span><span class="bold" style="width:96px;flex:none">${L(pos)}</span>
        <span class="grow ${ids.length ? '' : 'muted'}">${ids.length ? ids.map((id) => `${pname(id)} (${PMAP[id] ? PMAP[id].points : 0})`).join(' & ') : 'Not set'}</span></div>`;
    });
  }
  function progressCard() {
    const p = me();
    if (!p) {
      if (S.me.role !== 'player') return '';
      return html`<div class="card"><h2>Link your account</h2><p class="muted small">Your login “${S.me.username}” isn't on the roster yet. Ask your coach to add it in Roster → Edit → KeyAuth username, or sign in with the team code and your PIN.</p></div>`;
    }
    const nxt = levelName(p.level + 1);
    let right;
    if (p.rankup) right = html`${chip('Rank-up match ' + p.rankup.status, '', 'lime')}<div class="small muted mt">${p.rankup.status === 'scheduled' ? `Scheduled: ${p.rankup.when || 'time TBD'}${p.rankup.details ? ' · ' + p.rankup.details : ''}` : 'Waiting for ' + (p.rankup.manager || 'a manager')}</div>
      ${p.rankup.status === 'pending' ? html`<button class="btn ghost sm mt" data-a="ru-cancel" data-id="${p.rankup.id}">Cancel request</button>` : ''}`;
    else if (p.qualified) right = html`<div class="bold good">You qualify for a rank-up match to ${nxt}!</div><button class="btn mt block" data-a="ru-request" data-id="${p.id}">Request rank-up match</button>`;
    else right = html`<div class="bold">${p.need} more points to qualify for your ${nxt} rank-up match</div>
      <div class="row wrap gap6 mt"><span class="small muted">Need extra points?</span><a class="btn ghost sm" href="#/quizzes">Video Quizzes</a><a class="btn ghost sm" href="#/videos">Optional Training</a></div>`;
    return html`<div class="card"><div class="row wrap" style="align-items:flex-start;gap:16px">
      <div class="row grow" style="min-width:240px">${av(p.name, p.color, true)}<div class="grow"><div class="kicker">Your progress</div><div style="font-size:26px;font-weight:800">${p.points} points</div>
        <div class="row gap6 mb">${chip(p.rank, p.color)}${posChip(p.pos)}</div>${bar(p.frac, p.color)}</div></div>
      <div style="flex:1;min-width:240px">${right}</div></div>
      ${S.my_skips ? html`<div class="small bad mt">Skipping was detected on ${S.my_skips} video(s) — watch videos all the way through to earn points.</div>` : ''}</div>`;
  }

  // ---------------------------------------------------------------- roster
  VIEWS.roster = () => {
    const fs = ['All', 'Players', 'Managers'].concat(staff() ? ['Inactive'] : []);
    return html`${pageHead('Roster', `Everyone starts at ${S.rules.start} points · every ${S.rules.step} points earns a rank-up match`,
      can('edit_roster') ? html`<button class="btn" data-a="player-add">${icon('plus')}Add player</button>` : '')}
      <div class="row wrap mb"><div class="search"><input class="in" id="roster-q" data-in="roster-q" placeholder="Search by name${isCoach() ? ' or ID' : ''}…" value="${UI.roster.q}" autocomplete="off"></div>
        ${seg('roster-f', fs, UI.roster.f)}</div>
      <div class="card" style="padding:8px"><div class="list" id="roster-list">${rosterList()}</div></div>`;
  };
  function rosterList() {
    const q = UI.roster.q.toLowerCase(), f = UI.roster.f;
    const rows = S.players.filter((p) => {
      if (f === 'Inactive' ? p.active : !p.active) return false;
      if (f === 'Players' && p.role === 'manager') return false;
      if (f === 'Managers' && p.role !== 'manager') return false;
      return !q || p.name.toLowerCase().includes(q) || String(p.student_id || '').toLowerCase().includes(q);
    });
    if (!rows.length) return empty('No one here', can('edit_roster') ? 'Tap “Add player” to build your team.' : '');
    return rows.map((p) => html`<div class="item tap" data-a="player" data-id="${p.id}">${av(p.name, p.role === 'manager' ? '#A78BFA' : p.color)}
      <div class="grow"><div class="name ellipsis">${p.name}</div><div class="meta ellipsis">${[p.grade ? 'Grade ' + p.grade : '', p.student_id ? 'ID ' + p.student_id : '', p.role === 'manager' ? 'Manager' : `W-L ${p.w}-${p.l}`].filter(Boolean).join(' · ')}</div>
        ${p.role === 'manager' ? '' : html`<div class="row gap6" style="margin-top:6px">${posChip(p.pos)}${chip(p.rank, p.color)}${rankStatus(p)}</div>`}</div>
      ${p.role === 'manager' ? chip('Manager', '#A78BFA') : html`<div class="pts">${p.points}<div class="tiny muted">pts</div></div>`}</div>`);
  }

  async function playerSheet(id) {
    const p = PMAP[id]; if (!p) return;
    const self = S.me.pid === id;
    const full = staff() || self;
    const acts = [];
    if (can('adjust') && p.role !== 'manager') acts.push(html`<button class="btn ghost sm" data-a="points" data-id="${id}">± Points</button>`);
    if (p.role !== 'manager' && p.qualified && !p.rankup && (can('rank') || self)) acts.push(html`<button class="btn sm" data-a="ru-request" data-id="${id}">Request rank-up match</button>`);
    if (can('edit_roster')) acts.push(html`<button class="btn ghost sm" data-a="player-edit" data-id="${id}">Edit</button>`);
    const st = p.stats;
    const body = openSheet(html`<div class="row">${av(p.name, p.color, true)}<div class="grow"><h2>${p.name}</h2>
        ${p.role === 'manager' ? chip('Manager', '#A78BFA') : html`<div class="row gap6 wrap" style="margin-top:4px"><span class="bold" style="font-size:18px">${p.points} pts</span>${chip(p.rank, p.color)}${posChip(p.pos)}</div>`}</div></div>
      ${p.role === 'manager' ? '' : html`<div class="small mt ${p.qualified ? 'good' : 'muted'}">${p.qualified ? `Qualified for a rank-up match to ${levelName(p.level + 1)}` : `${p.need} points to qualify for ${levelName(p.level + 1)}`}</div>`}
      ${acts.length ? html`<div class="row wrap gap6 mt">${acts}</div>` : ''}
      ${st ? html`<div class="stats mt">${[...(p.sr != null && p.role !== 'manager' ? [['Skill rating', p.sr]] : []), ['Matches', `${st.wins}-${st.losses}`], ['Scrimmages', `${st.scr_wins}-${st.scr_losses}`], ['Challenges', `${st.ch_wins}-${st.ch_losses}`],
        ['Practices', st.practices], ['Unexcused', st.absences], ['Excused', st.excused], ['Quizzes', st.quizzes], ['Videos', st.videos], ['Skips', st.skips]]
        .map(([t, v]) => html`<div class="stat"><div class="kicker">${t}</div><div class="v" style="font-size:18px">${v}</div></div>`)}</div>` :
        html`<div class="muted small mt">Match record ${p.w}-${p.l}</div>`}
      ${full ? html`<div id="hist" class="mt"><div class="spinner" style="margin:16px auto"></div></div>` : ''}
      <div class="acts"><button class="btn ghost" data-a="close">Close</button></div>`, { wide: true });
    if (full) loadHistory(body, id, 0);
  }
  async function loadHistory(body, id, offset) {
    const box = $('#hist', body); if (!box) return;
    let r;
    try { r = await act('history.get', { id, offset }, { quiet: true }); } catch (e) { box.innerHTML = rv(empty(e.message)); return; }
    const prev = offset ? box.innerHTML.replace(/<div class="more">[\s\S]*$/, '') : '';
    const ranks = !offset && r.ranks.length ? html`<div class="kicker mt">Rank history</div>${r.ranks.map((h) => html`<div class="small" style="margin-top:4px">${h.from_name} → ${h.to_name} · ${h.kind === 'match' ? 'rank-up match' : 'set by ' + h.by} · ${niceTs(h.ts)}${h.reason ? ' — ' + h.reason : ''}</div>`)}` : '';
    const head = !offset ? html`${ranks}<div class="kicker mt2">Points history</div>` : '';
    const rows = r.entries.map((e) => html`<div class="row" style="padding:8px 0;border-bottom:1px solid var(--line)"><b class="${e.delta > 0 ? 'good' : e.delta < 0 ? 'bad' : 'muted'}" style="width:52px;flex:none">${e.delta > 0 ? '+' : ''}${e.delta}</b>
      <div class="grow"><div>${e.reason}</div><div class="tiny muted">${niceTs(e.ts)} · by ${e.by}</div></div></div>`);
    const more = offset + r.entries.length < r.total ? html`<div class="more"><button class="btn ghost sm" data-a="hist-more" data-id="${id}" data-off="${offset + r.entries.length}">Show more (${r.total - offset - r.entries.length} left)</button></div>` : '';
    box.innerHTML = prev + rv(html`${head}${rows}${r.total ? '' : empty('No points changes yet', `Started at ${S.rules.start}.`)}${more}`);
  }

  function playerForm(p) {
    p = p || { role: 'player', active: true };
    return html`<h2>${p.id ? 'Edit player' : 'Add player'}</h2>
      ${field('Full name', html`<input class="in" id="pf-name" value="${p.name || ''}" maxlength="60" autocomplete="off">`)}
      <div class="cols2">${field('Grade', sel('pf-grade', ['', '9', '10', '11', '12'], p.grade || ''))}${field('Student / OSIS ID', html`<input class="in" id="pf-sid" value="${p.student_id || ''}" maxlength="20" inputmode="numeric">`)}</div>
      ${field('Role', seg('pf-role', [['player', 'Player'], ['manager', 'Manager']], p.role, { block: true }))}
      ${field('KeyAuth username (only if they sign in with a key)', html`<input class="in" id="pf-user" value="${p.username || ''}" maxlength="60" autocomplete="off" autocapitalize="off">`)}
      ${field('Discord user ID (managers — for rank-up pings)', html`<input class="in" id="pf-disc" value="${p.discord_id || ''}" maxlength="25" inputmode="numeric">`)}
      ${field('Notes', html`<input class="in" id="pf-notes" value="${p.notes || ''}" maxlength="300">`)}
      ${p.id ? html`<label class="check mt"><input type="checkbox" id="pf-active" ${p.active ? raw('checked') : ''}> Active on the team</label>` : ''}
      <div class="acts">${p.id ? html`<button class="btn danger left" data-a="player-remove" data-id="${p.id}">Remove</button>` : ''}
        ${p.id && p.has_pin ? html`<button class="btn ghost" data-a="pin-reset" data-id="${p.id}">Reset PIN</button>` : ''}
        <button class="btn ghost" data-a="close">Cancel</button><button class="btn" data-a="player-save" data-id="${p.id || ''}">Save</button></div>`;
  }

  // ---------------------------------------------------------------- lineup
  VIEWS.lineup = () => {
    const edit = can('lineup');
    const people = playerOpts(roster());
    return html`${pageHead('Lineup & Challenges', 'PSAL format: 3 singles + 2 doubles · win a challenge to take a higher spot',
      edit ? html`<button class="btn ghost" data-a="lineup-auto">Auto-fill by points</button><button class="btn" data-a="lineup-save">Save lineup</button>` : '')}
      <div class="g2"><div class="grid">${S.consts.positions.map((pos) => {
        const ids = S.lineup[pos] || [];
        return html`<div class="card"><div class="row"><span class="lbar" style="background:${POS_COLORS[pos]};height:18px"></span><h2 class="grow">${L(pos)}</h2>${pos === 'S1' ? chip('Manager training focus', '#A78BFA') : ''}</div>
          ${edit ? html`<div class="${S.consts.sizes[pos] === 2 ? 'cols2' : ''}">${Array.from({ length: S.consts.sizes[pos] }, (_, i) => html`<div class="field">${sel(`lu-${pos}-${i}`, people, ids[i] || '', { placeholder: '— Empty —' })}<div class="tiny muted">${ids[i] && PMAP[ids[i]] ? `${PMAP[ids[i]].points} pts · ${PMAP[ids[i]].rank}` : 'Open spot'}</div></div>`)}</div>`
            : html`<div class="mt ${ids.length ? 'bold' : 'muted'}">${ids.length ? ids.map(pname).join(' & ') : 'Not set'}</div>`}</div>`;
      })}</div>
      <div class="grid">
        ${can('challenge') ? html`<div class="card"><h2>Challenge match</h2><div class="small muted">If the challenger beats a player in a higher spot, they swap spots.</div>
          ${field('Challenger', sel('ch-c', people, '', { placeholder: 'Choose challenger', attrs: 'data-ch="ch-pick"' }))}
          ${field('Defender', sel('ch-d', people, '', { placeholder: 'Choose defender', attrs: 'data-ch="ch-pick"' }))}
          ${field('Result', seg('ch-w', [['challenger', 'Challenger won'], ['defender', 'Defender won']], UI.ch.win, { block: true }))}
          ${field('Score (optional)', html`<input class="in" id="ch-score" placeholder="e.g. 21-17, 21-19" maxlength="60">`)}
          <div class="lineup-row" id="ch-prev" style="display:block">${chPreview()}</div>
          <button class="btn block mt" data-a="challenge">Record challenge</button></div>` : ''}
        <div class="card"><h2>Recent challenges</h2>${S.challenges.length ? S.challenges.map((c) => {
          const loser = c.winner === c.challenger ? c.defender : c.challenger;
          return html`<div style="margin-top:10px"><div class="bold">${pname(c.winner)} beat ${pname(loser)}</div><div class="tiny muted">${niceTs(c.ts)} · ${c.score || 'no score'} · ${c.swap && c.swap.to ? 'Took ' + L(c.swap.to) : 'No spot change'}</div></div>`;
        }) : empty('No challenges yet')}</div>
      </div></div>`;
  };

  // --------------------------------------------------------------- matches
  VIEWS.matches = () => {
    const canRec = can('match');
    const tab = UI.matches.tab || (canRec ? 'Record match' : 'Match history');
    UI.matches.tab = tab;
    const [w, l] = S.record;
    return html`${pageHead('PSAL Matches', 'Record a match and points are awarded automatically', canRec ? seg('m-tab', ['Record match', 'Match history'], tab) : '')}
      ${tab === 'Record match' && canRec ? matchForm() : html`<div class="bold mb">Season record ${w}-${l}</div>${S.matches.length ? S.matches.map(matchCard) : html`<div class="card">${empty('No matches yet')}</div>`}`}`;
  };
  function matchForm() {
    const people = playerOpts(roster());
    return html`<div class="card"><h2>Match details</h2>
      <div class="cols2">${field('Date', html`<input class="in" type="date" id="m-date" value="${today()}">`)}${field('Home / Away', seg('m-home', ['Home', 'Away'], UI.matches.home, { block: true }))}</div>
      ${field('Opponent school', html`<input class="in" id="m-opp" placeholder="e.g. Stuyvesant HS" maxlength="80">`)}</div>
      <div class="card"><h2>Results</h2><div class="small muted">Players come from your saved lineup — change them if someone subbed in.</div>
      ${S.consts.positions.map((pos) => {
        const res = UI.matches.res[pos] || 'Win';
        const ids = S.lineup[pos] || [];
        return html`<div class="lineup-row" style="display:block"><div class="row"><span class="lbar" style="background:${POS_COLORS[pos]};height:18px"></span><b class="grow">${L(pos)}</b></div>
          <div class="${S.consts.sizes[pos] === 2 ? 'cols2' : ''}">${Array.from({ length: S.consts.sizes[pos] }, (_, i) => html`<div class="field">${sel(`m-${pos}-${i}`, people, ids[i] || '', { placeholder: '— Pick player —' })}</div>`)}</div>
          <div class="row wrap mt">${seg('mres-' + pos, ['Win', 'Loss', 'Not played'], res)}<input class="in grow" id="m-score-${pos}" placeholder="Score e.g. 21-15, 21-18" maxlength="60" style="min-width:150px"></div></div>`;
      })}
      <div class="row wrap mt2"><div class="grow bold" id="m-preview">${matchPreview()}</div><button class="btn" data-a="match-save">Save match & award points</button></div></div>`;
  }
  function matchPreview() {
    const played = S.consts.positions.filter((p) => (UI.matches.res[p] || 'Win') !== 'Not played');
    const wins = played.filter((p) => (UI.matches.res[p] || 'Win') === 'Win').length;
    if (!played.length) return html`<span class="muted">No positions played</span>`;
    const won = wins > played.length / 2;
    return html`<span class="${won ? 'good' : 'bad'}">Team ${won ? 'WINS' : 'LOSES'} ${wins}-${played.length - wins}</span>`;
  }
  function matchCard(m) {
    return html`<div class="card"><div class="row wrap">${chip(m.team_won ? 'W' : 'L', m.team_won ? '#22C55E' : '#EF4444')}<h2 class="grow">vs ${m.opponent}</h2>
      <span class="small muted">${m.score} · ${m.home ? 'Home' : 'Away'} · ${niceDate(m.date)}</span>
      ${can('delete') ? html`<button class="btn danger sm" data-a="match-del" data-id="${m.id}" data-n="${m.opponent}">Delete</button>` : ''}</div>
      ${S.consts.positions.map((pos) => { const r = m.results[pos]; if (!r) return ''; return html`<div class="row small" style="margin-top:6px"><span class="muted" style="width:96px;flex:none">${L(pos)}</span>
        ${r.played === false ? html`<span class="muted">Not played</span>` : html`<b class="${r.won ? 'good' : 'bad'}" style="width:40px;flex:none">${r.won ? 'WIN' : 'LOSS'}</b><span class="grow">${r.players.map(pname).join(' & ')}${r.score ? html` <span class="muted">(${r.score})</span>` : ''}</span>`}</div>`; })}</div>`;
  }

  // -------------------------------------------------------------- practice
  async function loadAttendance() {
    const d = UI.prac.date;
    try {
      const rec = await act('attendance.get', { date: d }, { quiet: true });
      UI.prac.status = {}; UI.prac.reasons = {}; UI.prac.saved = !!rec;
      if (rec) {
        rec.present.forEach((id) => { UI.prac.status[id] = 'Present'; });
        rec.absent.forEach((id) => { UI.prac.status[id] = 'Absent'; });
        Object.entries(rec.excused).forEach(([id, why]) => { UI.prac.status[id] = 'Excused'; UI.prac.reasons[id] = why; });
      }
      UI.prac.loaded = d;
      if (UI.route === 'practice') paint();
    } catch (e) { toast(e.message, 'error'); }
  }
  VIEWS.practice = () => {
    const t = UI.prac.tab;
    return html`${pageHead('Practice & Points', 'Unexcused absences and lost scrimmages cost points', seg('p-tab', ['Attendance', 'Scrimmage', 'Recent', 'Point rules'], t))}
      ${t === 'Attendance' ? attendanceView() : t === 'Scrimmage' ? scrimmageView() : t === 'Recent' ? recentPractice() : rulesCard()}`;
  };
  function attendanceView() {
    const people = roster().slice().sort(byName);
    const st = UI.prac.status;
    return html`<div class="card"><div class="row wrap"><input class="in" type="date" id="p-date" value="${UI.prac.date}" data-ch="p-date" style="max-width:190px">
        <button class="btn ghost sm" data-a="att-all">Everyone present</button>
        <span class="small ${UI.prac.saved ? 'warn' : 'muted'}">${UI.prac.loaded !== UI.prac.date ? 'Loading…' : UI.prac.saved ? 'Already saved — saving again replaces it' : 'New practice day'}</span></div>
      <div class="small muted mt">Absent = unexcused (−${S.rules.absence}). Excused needs a reason and costs nothing.</div>
      <div class="mt">${people.length ? people.map((p) => { const s = st[p.id] || 'Present'; return html`<div class="att-row"><div><div class="bold">${p.name}</div><div class="tiny muted">${p.points} pts</div></div>
          ${seg('att-' + p.id, ['Present', 'Absent', 'Excused'], s, { cls: 'att' })}
          <input class="in reason ${s === 'Excused' ? '' : 'hide'}" id="rs-${p.id}" placeholder="Reason (required)" value="${UI.prac.reasons[p.id] || ''}" maxlength="120" data-in="reason" data-id="${p.id}"></div>`; }) : empty('No players yet')}</div>
      <div class="row wrap mt2"><div class="grow bold" id="att-preview">${attPreview()}</div><button class="btn" data-a="att-save">Save attendance</button></div></div>`;
  }
  function attPreview() {
    const vals = roster().map((p) => UI.prac.status[p.id] || 'Present');
    const pr = vals.filter((v) => v === 'Present').length, ab = vals.filter((v) => v === 'Absent').length, ex = vals.filter((v) => v === 'Excused').length;
    return html`<span class="${ab ? 'bad' : ''}">${pr} present (+${S.rules.practice})${ab ? ` · ${ab} unexcused (−${S.rules.absence})` : ''}${ex ? ` · ${ex} excused (0)` : ''}</span>`;
  }
  function scrimmageView() {
    const people = playerOpts(roster());
    const dbl = UI.prac.scrType === 'Doubles';
    const side = (k, name) => html`<div class="lineup-row" style="display:block"><div class="kicker">${name}</div>
      ${field('', sel(`s${k}-0`, people, '', { placeholder: 'Choose player', attrs: 'data-ch="scr-pick"' }))}${dbl ? field('', sel(`s${k}-1`, people, '', { placeholder: 'Choose partner', attrs: 'data-ch="scr-pick"' })) : ''}</div>`;
    return html`<div class="card"><h2>Practice scrimmage</h2>
      ${field('Type', seg('scr-type', ['Singles', 'Doubles'], UI.prac.scrType, { block: true }))}
      <div class="g2">${side('a', 'Side A')}${side('b', 'Side B')}</div>
      ${field('Result', seg('scr-win', [['A', 'Side A won'], ['B', 'Side B won']], UI.prac.scrWin, { block: true }))}
      ${field('Score (optional)', html`<input class="in" id="scr-score" placeholder="e.g. 21-18" maxlength="60">`)}
      <div class="lineup-row" id="scr-prev" style="display:block">${scrPreview()}</div>
      <button class="btn block mt" data-a="scr-save">Record scrimmage</button></div>`;
  }
  function scrPreview() {
    const R = S.rules; const n = UI.prac.scrType === 'Doubles' ? 2 : 1; const a = [], b = [];
    for (let i = 0; i < n; i++) { a.push(val(`sa-${i}`)); b.push(val(`sb-${i}`)); }
    const each = n === 2 ? ' each' : '';
    if (a.concat(b).some((x) => !x)) return html`<span class="small muted">Even game: winners +${R.scrimmage_win}${each}, losers −${Math.abs(R.scrimmage_loss)}${each}. ${R.elo.k ? 'Pick the players to see skill-based points — beating a stronger side is worth more.' : ''}</span>`;
    const pa = winChance(a, b), ma = eloMult(pa), mb = eloMult(1 - pa);
    return html`<div class="small">Win chance: <b>Side A ${pct(pa)}</b> · <b>Side B ${pct(1 - pa)}</b></div>
      <div class="small mt">If <b>A</b> wins: A <b class="good">+${ptsOf(R.scrimmage_win, ma)}</b>${each}, B <b class="bad">−${ptsOf(R.scrimmage_loss, ma)}</b>${each}${tag(ma)}</div>
      <div class="small">If <b>B</b> wins: B <b class="good">+${ptsOf(R.scrimmage_win, mb)}</b>${each}, A <b class="bad">−${ptsOf(R.scrimmage_loss, mb)}</b>${each}${tag(mb)}</div>`;
  }
  function chPreview() {
    const R = S.rules; const c = val('ch-c'), d = val('ch-d');
    if (!c || !d || c === d) return html`<span class="small muted">Winner gets about +${R.challenge_win} (more for beating a stronger player, less for a weaker one); loser +${R.challenge_loss}.</span>`;
    const pc = winChance([c], [d]);
    return html`<div class="small">Win chance: <b>${pname(c)} ${pct(pc)}</b> · <b>${pname(d)} ${pct(1 - pc)}</b></div>
      <div class="small">If ${pname(c)} wins: <b class="good">+${ptsOf(R.challenge_win, eloMult(pc))}</b>${tag(eloMult(pc))} · If ${pname(d)} wins: <b class="good">+${ptsOf(R.challenge_win, eloMult(1 - pc))}</b>${tag(eloMult(1 - pc))} · loser +${R.challenge_loss}</div>`;
  }
  function recentPractice() {
    const r = UI.prac.recent;
    const body = r === 'Practices' ? (S.attendance.length ? S.attendance.map((a) => html`<div class="note-item mt"><div class="grow"><div class="row"><b class="grow">${niceDate(a.date)}</b>
        ${can('delete') ? html`<button class="btn danger sm" data-a="att-del" data-id="${a.id}" data-n="${niceDate(a.date)}">Undo</button>` : ''}</div>
        <div class="small muted">${a.present.length} present · ${a.absent.length} unexcused · ${Object.keys(a.excused).length} excused</div>
        ${a.absent.length ? html`<div class="small bad">Unexcused: ${a.absent.map(pname).join(', ')}</div>` : ''}
        ${Object.entries(a.excused).map(([id, why]) => html`<div class="small muted">Excused: ${pname(id)} — ${why}</div>`)}</div></div>`) : empty('No practices saved yet'))
      : (S.scrimmages.length ? S.scrimmages.map((x) => { const [wn, ls] = x.winner === 'A' ? [x.a, x.b] : [x.b, x.a];
        return html`<div class="note-item mt"><div class="grow"><div class="row wrap"><b class="good">${wn.map(pname).join(' & ')}</b><span class="muted">beat</span><b class="bad">${ls.map(pname).join(' & ')}</b>
          <span class="grow"></span>${can('delete') ? html`<button class="btn danger sm" data-a="scr-del" data-id="${x.id}">Undo</button>` : ''}</div><div class="tiny muted">${niceTs(x.ts)}${x.score ? ' · ' + x.score : ''}${x.gain ? ` · +${x.gain} / −${x.loss}` : ''}${x.chance != null ? ` · winner had a ${pct(x.chance)} chance` : ''}</div></div></div>`; }) : empty('No scrimmages yet'));
    return html`<div class="card">${seg('p-recent', ['Practices', 'Scrimmages'], r)}${body}</div>`;
  }
  function rulesCard() {
    const R = S.rules;
    const rows = [['Start', `${R.start} points for everyone`], ['Rank-up match', `Qualify every ${R.step} points`], ['Practice attendance', `+${R.practice}`, 'good'],
      ['Unexcused absence', `−${R.absence}`, 'bad'], ['Excused absence (with reason)', '0'],
      ['Scrimmage win (even game)', `+${R.scrimmage_win}`, 'good'], ['Scrimmage loss (even game)', `−${Math.abs(R.scrimmage_loss)}`, 'bad'],
      ['Skill-based points', R.elo.k ? `On — ${R.elo.min_pct}% to ${R.elo.max_pct}% of normal` : 'Off'],
      ...S.consts.positions.map((p) => [`${L(p)} match win`, `+${R.win[p]}`, 'good']), ['Match loss (played)', `+${R.loss}`, 'good'], ['Team win bonus', `+${R.team_win_bonus} each`, 'good'],
      ['Challenge win (even game) / loss', `+${R.challenge_win} / +${R.challenge_loss}`, 'good'], ['Quiz passed (Beg / Int / Exp)', `+${R.quiz_points.Beginner} / +${R.quiz_points.Intermediate} / +${R.quiz_points.Expert}`, 'good'],
      ['Training video (Beg / Int / Exp)', `+${R.video_points.Beginner} / +${R.video_points.Intermediate} / +${R.video_points.Expert}`, 'good'], ['Skipping a video', `−${R.penalty}`, 'bad']];
    return html`<div class="card"><h2>How points are earned & lost</h2><div class="small muted">Coaches can change these in Settings. Scrimmages and challenges are skill-based like Valorant: beating a stronger player is worth more, losing to a weaker one costs more.</div>
      ${rows.map(([k, v, c]) => html`<div class="row" style="padding:7px 0;border-bottom:1px solid var(--line)"><span class="grow muted">${k}</span><b class="${c || ''}">${v}</b></div>`)}</div>`;
  }

  // ------------------------------------------------------ quizzes & videos
  VIEWS.quizzes = () => libraryView('quiz');
  VIEWS.videos = () => libraryView('optional');
  function libraryView(kind) {
    const F = UI.lib[kind];
    const cats = kind === 'quiz' ? S.consts.quiz_cats : S.consts.train_cats;
    const vids = S.videos.filter((v) => v.kind === kind);
    const R = S.rules;
    const who = UI.lib.who;
    const title = kind === 'quiz' ? 'Video Quizzes' : 'Optional Training';
    const sub = kind === 'quiz' ? 'Need extra points? Watch a training video, then pass the quiz' : 'Footwork · Shots · Grip · Plyometrics — watch the whole video for extra points';
    const info = kind === 'quiz' ? `Watch the whole video, then the quiz unlocks (${R.pass_pct}% to pass, ${R.attempts} tries). Skipping is detected: no points and −${R.penalty}.`
      : `Watch for extra points — no quiz. Videos can't be skipped: skipping = no points and −${R.penalty}.`;
    let groups = '';
    for (const lv of S.consts.levels) {
      if (F.level !== 'All' && F.level !== lv) continue;
      const items = vids.filter((v) => v.level === lv && (F.cat === 'All' || v.category === F.cat));
      const done = items.filter((v) => (v.my && (kind === 'quiz' ? v.my.passed : v.my.watched))).length;
      groups += rv(html`<div class="level-h"><span class="lbar" style="background:${S.consts.level_colors[lv]}"></span><h2>${lv}</h2><span class="small muted grow">${LEVEL_BLURB[lv]}</span>${S.me.pid && items.length ? html`<span class="small bold muted">${done}/${items.length} done</span>` : ''}</div>
        ${items.length ? html`<div class="vgrid">${items.map((v) => videoCard(v, kind))}</div>` : html`<div class="small muted">Nothing here yet.</div>`}`);
    }
    return html`${pageHead(title, sub, can('videos') ? html`<button class="btn" data-a="video-add" data-kind="${kind}">${icon('plus')}Add video</button>` : '')}
      <div class="small muted mb">${info}</div>
      <div class="scroller mb">${seg('lvl-' + kind, ['All'].concat(S.consts.levels).map((x) => [x, x === 'All' ? 'All levels' : x]), F.level)}${seg('cat-' + kind, ['All'].concat(cats), F.cat)}</div>
      ${can('quiz_others') ? html`<div class="row wrap mb"><span class="small muted">See a player's progress:</span><div style="min-width:220px">${sel('lib-who', playerOpts(roster()), who, { placeholder: 'Choose player', attrs: 'data-ch="lib-who"' })}</div></div>` : ''}
      ${!vids.length ? html`<div class="card">${empty('No videos yet', can('videos') ? '' : 'Coaches and managers can add YouTube videos here.')}
        ${can('videos') ? html`<div class="center"><button class="btn" data-a="starters" data-kind="${kind}">Add ${kind === 'quiz' ? 6 : 13} starter videos (all levels)</button></div>` : ''}</div>` : raw(groups)}`;
  }
  function videoCard(v, kind) {
    const id = ytId(v.url);
    const my = v.my;
    const who = UI.lib.who;
    const st = who ? (UI.lib.status[who] || {})[v.id] : null;
    let action = '';
    if (my) {
      if (my.skipped) action = html`<span class="small bold bad">Skipping detected — no points</span>`;
      else if (kind === 'optional') action = my.watched ? html`<span class="small bold good">Watched ✓ points earned</span>` : html`<button class="btn sm" data-a="watch" data-id="${v.id}">Watch</button>`;
      else if (my.passed) action = html`<span class="small bold good">Passed ✓ ${my.score}</span>`;
      else if (!my.viewed) action = html`<button class="btn sm" data-a="watch" data-id="${v.id}">Watch to unlock quiz</button>`;
      else if (my.left <= 0) action = html`<span class="small bold bad">No tries left</span>`;
      else action = html`<button class="btn good sm" data-a="quiz" data-id="${v.id}">Take quiz (${my.left} ${my.left === 1 ? 'try' : 'tries'} left)</button>`;
    }
    let staffLine = '';
    if (st) {
      const txt = st.skipped ? 'Skipping detected' : kind === 'optional' ? (st.watched ? 'Watched ✓' : 'Not watched') : st.passed ? `Passed ✓ ${st.score}` : st.viewed ? `Watched · ${st.attempts} tries used${st.score ? ' · best ' + st.score : ''}` : 'Not watched';
      staffLine = html`<div class="row wrap gap6"><span class="small ${st.skipped ? 'bad' : st.passed || st.watched ? 'good' : 'muted'}">${pname(who)}: ${txt}</span>
        ${st.skipped && can('videos') ? html`<button class="btn ghost sm" data-a="clear-skip" data-id="${v.id}">Allow re-watch</button>` : ''}
        ${kind === 'quiz' && !st.passed && st.attempts > 0 && can('videos') ? html`<button class="btn ghost sm" data-a="quiz-reset" data-id="${v.id}">Reset tries</button>` : ''}</div>`;
    }
    const playable = my && !my.skipped && (kind === 'optional' ? !my.watched : !my.viewed);
    return html`<div class="card vcard">
      <div class="thumb ${playable ? 'tap' : ''}" ${playable ? raw(`data-a="watch" data-id="${esc(v.id)}" style="cursor:pointer"`) : ''}>${id ? html`<img loading="lazy" src="https://i.ytimg.com/vi/${id}/mqdefault.jpg" alt="">` : ''}
        ${playable ? html`<div class="play"><span>${raw('<svg width="22" height="22" viewBox="0 0 24 24"><path d="M8 5l12 7-12 7z" fill="#fff"/></svg>')}</span></div>` : ''}
        ${my && (my.passed || my.watched) ? html`<span class="ok">${chip('✓ Done', '#22C55E')}</span>` : ''}</div>
      <div class="row gap6">${chip(v.level, S.consts.level_colors[v.level])}${chip(v.category, '', 'plain')}<span class="grow"></span><b class="good">+${v.points} pts</b></div>
      <div class="bold">${v.title}</div>
      <div class="tiny muted">${kind === 'quiz' ? `${v.qcount} questions · ` : ''}Min. ${v.minutes} min · tracked, no skipping</div>
      ${action ? html`<div>${action}</div>` : ''}${staffLine}
      ${can('videos') ? html`<div class="row gap6"><span class="grow"></span><button class="btn ghost sm" data-a="video-edit" data-id="${v.id}" data-kind="${kind}">Edit</button><button class="btn danger sm" data-a="video-del" data-id="${v.id}">Delete</button></div>` : ''}</div>`;
  }

  async function quizSheet(vid) {
    let q;
    try { q = await act('quiz.get', { id: vid }, { quiet: true }); } catch (e) { toast(e.message, 'error'); return; }
    const b = openSheet(html`<h2>${q.title}</h2><div class="small muted">${q.questions.length} questions · ${S.rules.pass_pct}% to pass · +${q.points} pts · ${q.left} ${q.left === 1 ? 'try' : 'tries'} left</div>
      ${q.questions.map((x, i) => html`<div class="q"><div class="bold">${i + 1}. ${x.q}</div>${x.options.map((o, j) => (o ? html`<label class="opt"><input type="radio" name="q${i}" value="${j}"><span>${o}</span></label>` : ''))}</div>`)}
      <div class="err" id="quiz-err"></div>
      <div class="acts"><button class="btn ghost" data-a="close">Cancel</button><button class="btn good" data-a="quiz-submit" data-id="${vid}" data-n="${q.questions.length}">Submit answers</button></div>`, { wide: true });
    b.addEventListener('change', (e) => { if (e.target.type === 'radio') $$(`input[name="${e.target.name}"]`, b).forEach((r) => r.closest('.opt').classList.toggle('sel', r.checked)); });
  }

  // video editor (add / edit) — quiz questions live in an in-memory list
  let VED = null;
  async function videoEditor(vid, kind) {
    let v = { kind, title: '', url: '', category: (kind === 'quiz' ? S.consts.quiz_cats : S.consts.train_cats)[0], level: 'Beginner', minutes: 1, questions: [] };
    if (vid) { try { v = await act('video.full', { id: vid }, { quiet: true }); } catch (e) { toast(e.message, 'error'); return; } }
    v.points = v.points != null ? v.points : (kind === 'quiz' ? S.rules.quiz_points : S.rules.video_points)[v.level];
    VED = { id: vid || null, kind, qs: (v.questions || []).map((q) => ({ q: q.q, options: (q.options || []).concat(['', '', '', '']).slice(0, 4), answer: q.answer })), pointsTouched: !!vid };
    if (kind === 'quiz' && !VED.qs.length) VED.qs.push({ q: '', options: ['', '', '', ''], answer: 0 });
    const cats = kind === 'quiz' ? S.consts.quiz_cats : S.consts.train_cats;
    openSheet(html`<h2>${vid ? 'Edit' : 'Add'} ${kind === 'quiz' ? 'quiz video' : 'training video'}</h2>
      ${field('Title', html`<input class="in" id="ve-title" value="${v.title}" maxlength="120">`)}
      ${field('YouTube link', html`<input class="in" id="ve-url" value="${v.url}" placeholder="https://www.youtube.com/watch?v=…" inputmode="url" autocapitalize="off">`)}
      <div class="cols2">${field('Category', sel('ve-cat', cats, v.category))}${field('Points', html`<input class="in" id="ve-pts" type="number" inputmode="numeric" value="${v.points}" data-in="ve-pts">`)}</div>
      ${field('Level', seg('ve-level', S.consts.levels, v.level, { block: true }))}
      ${field('Minimum minutes', html`<input class="in" id="ve-min" type="number" inputmode="numeric" value="${v.minutes}">`)}
      <div class="tiny muted" style="margin-top:4px">Players must watch 95% of the real video; this is an extra floor — keep it at or below the video's length.</div>
      ${kind === 'quiz' ? html`<div class="kicker mt2">Questions</div><div id="ve-qs">${vedQuestions()}</div><button class="btn ghost sm mt" data-a="ve-addq">${icon('plus')}Add question</button>` : ''}
      <div class="err" id="ve-err"></div>
      <div class="acts"><button class="btn ghost" data-a="close">Cancel</button><button class="btn" data-a="ve-save">Save</button></div>`, { wide: true, onClose: () => { VED = null; } });
  }
  function vedSync() {
    const b = topSheet(); if (!b || !VED) return;
    VED.qs.forEach((q, i) => {
      const t = $(`#vq-${i}`, b); if (t) q.q = t.value;
      for (let j = 0; j < 4; j++) { const o = $(`#vo-${i}-${j}`, b); if (o) q.options[j] = o.value; }
      const a = segVal('va-' + i, b); if (a !== null) q.answer = +a;
    });
  }
  function vedQuestions() {
    return VED.qs.map((q, i) => html`<div class="lineup-row" style="display:block"><div class="row"><b class="grow">Question ${i + 1}</b>${VED.qs.length > 1 ? html`<button class="btn danger sm" data-a="ve-delq" data-i="${i}">Remove</button>` : ''}</div>
      <div class="field"><input class="in" id="vq-${i}" value="${q.q}" placeholder="Question" maxlength="300"></div>
      ${[0, 1, 2, 3].map((j) => html`<div class="field" style="margin-top:6px"><input class="in" id="vo-${i}-${j}" value="${q.options[j]}" placeholder="Answer ${'ABCD'[j]}${j > 1 ? ' (optional)' : ''}" maxlength="200"></div>`)}
      <div class="row mt"><span class="small muted">Correct answer:</span>${seg('va-' + i, [0, 1, 2, 3].map((j) => [j, 'ABCD'[j]]), q.answer)}</div></div>`);
  }

  // ------------------------------------------------------------ leaderboard
  VIEWS.leaderboard = () => {
    const f = UI.lb.f;
    const board = roster().filter((p) => f === 'All' || (f === 'Singles' ? ['S1', 'S2', 'S3'].includes(p.pos) : f === 'Doubles' ? ['D1', 'D2'].includes(p.pos) : !p.pos));
    const medal = ['#F5B83D', '#AEB7C4', '#CD7F32'];
    const pod = (idx, cls) => { const p = board[idx]; if (!p) return html`<div class="card pod"><div class="muted">—</div></div>`;
      return html`<div class="card pod ${cls} tap" data-a="player" data-id="${p.id}" style="cursor:pointer">${chip('#' + (idx + 1), medal[idx])}<div style="display:flex;justify-content:center;margin-top:8px">${av(p.name, p.color, idx === 0)}</div>
        <div class="nm">${p.name}</div><div class="p">${p.points}</div>${chip(p.rank, p.color)}</div>`; };
    return html`${pageHead('Leaderboard', 'Bronze → Silver → Gold → Platinum → Diamond → Champion → Legend',
      html`${seg('lb-f', ['All', 'Singles', 'Doubles', 'Bench'], f)}${isCoach() ? html`<a class="btn ghost" href="/api/export/leaderboard.csv" download>Export CSV</a>` : ''}`)}
      <div class="podium">${pod(1, '')}${pod(0, 'first')}${pod(2, '')}</div>
      <div class="card mt" style="padding:8px"><div class="list">${board.map((p, i) => html`<div class="item tap" data-a="player" data-id="${p.id}"><div class="rank-n">${i + 1}</div>${av(p.name, p.color)}
        <div class="grow"><div class="name ellipsis">${p.name}</div><div class="row gap6" style="margin-top:4px">${posChip(p.pos)}${chip(p.rank, p.color)}<span class="tiny ${p.qualified ? 'good' : 'muted'}">${p.qualified ? 'Qualified!' : p.need + ' to qualify'}</span>${staff() && p.sr != null ? html`<span class="tiny muted">· SR ${p.sr}</span>` : ''}</div></div>
        <div class="pts">${p.points}</div></div>`)}${board.length ? '' : empty('No players to show')}</div></div>`;
  };

  // --------------------------------------------------------- 1S training
  VIEWS.training = () => {
    const T = S.training || {};
    const tp = T.pid ? PMAP[T.pid] : null;
    const mgrNames = S.managers.map((m) => m.name);
    const myName = S.me.display || S.me.username;
    if (myName && !mgrNames.includes(myName)) mgrNames.push(myName);
    const skills = T.skills || {};
    const sugg = suggestPoints();
    return html`${pageHead('1st Singles Training', 'A separate point track managers use to develop the best player')}
      <div class="card">${tp ? html`<div class="row wrap">${av(tp.name, '#A78BFA', true)}<div class="grow"><div class="row gap6"><h2>${tp.name}</h2>${posChip(tp.pos)}</div>
          <div class="small muted">Team points: ${tp.points} · ${tp.rank}</div><div style="max-width:320px;margin-top:8px">${bar(T.level ? T.level[1] : 0, '#A78BFA')}</div><div class="tiny muted">${T.level ? T.level[2] + ' to next level' : ''}</div></div>
          <div class="right"><div class="kicker">Training points</div><div style="font-size:30px;font-weight:800">${T.points}</div>${chip(T.level ? T.level[0] : '', '#A78BFA')}</div></div>`
        : empty('No 1st singles player yet', 'Set one in Lineup, or choose a training player below.')}
        ${can('training') ? html`<div class="field"><label>Training player</label>${sel('tr-player', playerOpts(roster()), T.chosen || '', { placeholder: 'Current 1st Singles', attrs: 'data-ch="tr-player"' })}</div>` : ''}</div>
      <div class="g2 mt">
        <div class="card"><h2>Log a training session</h2><div class="small muted">Training points are separate from team points.</div>
          <div class="cols2">${field('Manager', sel('tr-mgr', mgrNames, mgrNames[0] || ''))}${field('Focus', sel('tr-focus', S.consts.focus, S.consts.focus[0]))}</div>
          <div class="cols2">${field('Minutes', html`<input class="in" id="tr-min" type="number" inputmode="numeric" value="60" data-in="tr-min">`)}${field('Training points', html`<input class="in" id="tr-pts" type="number" inputmode="numeric" value="${sugg}" data-in="tr-pts">`)}</div>
          ${field('Effort', seg('tr-effort', ['1', '2', '3', '4', '5'], UI.tr.effort, { block: true }))}
          ${field('Notes', html`<textarea class="in" id="tr-notes" maxlength="300"></textarea>`)}
          <button class="btn block mt" data-a="tr-log">Log session</button></div>
        <div class="card"><h2>Skill ratings</h2><div class="small muted">Rate 1–10.</div>
          ${S.consts.skills.map((k, i) => html`<div class="row" style="margin-top:10px"><span style="width:84px;flex:none">${k}</span><input type="range" class="range grow" min="1" max="10" id="sk-${i}" value="${skills[k] || 5}" data-in="skill" data-i="${i}"><b id="skv-${i}" style="width:22px;text-align:right">${skills[k] || 5}</b></div>`)}
          <button class="btn ghost block mt" data-a="tr-skills">Save ratings</button></div>
      </div>
      <div class="card mt"><h2>Session history</h2>${(T.sessions || []).length ? T.sessions.map((x) => html`<div class="note-item mt"><b style="color:#A78BFA;width:48px;flex:none">+${x.points}</b><div class="grow"><div class="bold">${x.focus} · ${x.minutes} min · effort ${x.effort}/5</div>
        <div class="small muted">with ${x.manager} · ${niceDate(x.date)}${x.notes ? ' — ' + x.notes : ''}</div></div>${can('delete') ? html`<button class="btn danger sm" data-a="tr-del" data-id="${x.id}">Delete</button>` : ''}</div>`) : empty('No sessions logged yet')}</div>`;
  };
  function suggestPoints() { const m = parseInt(val('tr-min') || '60', 10) || 0; return Math.round(m * 0.5 + (+UI.tr.effort) * 5); }

  // ----------------------------------------------------------------- notes
  VIEWS.notes = () => {
    const f = UI.notes.f;
    const order = (a, b) => S.consts.priorities.indexOf(a.priority) - S.consts.priorities.indexOf(b.priority) || (a.ts < b.ts ? -1 : 1);
    const notes = (S.notes || []).filter((n) => (f === 'All' ? true : f === 'Open' ? !n.resolved : n.resolved)).sort(order);
    const people = S.players.filter((p) => p.active).slice().sort(byName).map((p) => [p.id, p.name]);
    return html`${pageHead('Improvement Notes', 'Who needs to improve on what — send them to the managers on Discord')}
      <div class="g2"><div class="card"><h2>New note</h2>
        ${field('Player', sel('n-pid', people, '', { placeholder: 'Choose a player' }))}
        ${field('Needs to improve on', sel('n-area', S.consts.areas, S.consts.areas[0]))}
        ${field('Priority', seg('n-prio', S.consts.priorities, UI.notes.prio, { block: true }))}
        ${field('Details', html`<textarea class="in" id="n-text" maxlength="500"></textarea>`)}
        <label class="check mt"><input type="checkbox" id="n-send" ${S.webhook ? '' : raw('disabled')}> Also send to managers on Discord</label>
        <div class="small ${S.webhook ? 'good' : 'warn'}">${S.webhook ? 'Discord webhook connected.' : 'No Discord webhook yet — a coach can add one in Settings.'}</div>
        <button class="btn block mt" data-a="note-add">Add note</button></div>
      <div class="card"><div class="row wrap mb">${seg('n-f', ['Open', 'Resolved', 'All'], f)}<span class="grow"></span><button class="btn sm" data-a="note-send-all" ${S.webhook ? '' : raw('disabled')}>Send open notes</button></div>
        ${notes.length ? notes.map((n) => html`<div class="note-item mt"><span class="lbar" style="background:${PRIO_COLORS[n.priority]}"></span><div class="grow">
          <div class="row wrap gap6"><b>${pname(n.pid)}</b>${chip(n.area, '', 'soft')}${chip(n.priority, PRIO_COLORS[n.priority])}${n.resolved ? chip('Resolved', '#22C55E') : ''}</div>
          ${n.text ? html`<div class="small" style="margin-top:4px">${n.text}</div>` : ''}<div class="tiny muted">by ${n.by} · ${niceTs(n.ts)}${n.sent ? ' · sent to managers' : ''}</div>
          <div class="row gap6 wrap" style="margin-top:8px"><button class="btn ghost sm" data-a="note-send" data-id="${n.id}" ${S.webhook ? '' : raw('disabled')}>Send</button>
            <button class="btn ghost sm" data-a="note-resolve" data-id="${n.id}" data-v="${n.resolved ? '' : '1'}">${n.resolved ? 'Reopen' : 'Resolve'}</button>
            <button class="btn danger sm" data-a="note-del" data-id="${n.id}">Delete</button></div></div></div>`) : empty('No notes here')}</div></div>`;
  };

  // --------------------------------------------------------------- rank-ups
  VIEWS.rankups = () => {
    const reqs = S.rankups || [];
    const open = reqs.filter((r) => r.status === 'pending' || r.status === 'scheduled');
    const mineId = S.me.mgr_pid;
    const mine = open.filter((r) => mineId && r.manager === mineId);
    const qual = roster().filter((p) => p.qualified && !p.rankup);
    const ups = (S.rank_history || []).filter((h) => h.to > h.from).length;
    const f = UI.ru.f;
    let show = f === 'Open' ? open : f === 'Closed' ? reqs.filter((r) => !open.includes(r)) : reqs;
    show = show.slice().sort((a, b) => (mine.includes(b) - mine.includes(a)) || (a.ts < b.ts ? -1 : 1));
    return html`<div class="hero"><h1>${S.me.greeting}</h1><div class="sub">${open.length} open rank-up request(s)${mine.length ? ` · ${mine.length} assigned to you` : ''}</div></div>
      <div class="stats s4 mt">${[['Waiting', open.filter((r) => r.status === 'pending').length, 'to schedule'], ['Scheduled', open.filter((r) => r.status === 'scheduled').length, 'coming up'], ['Qualified', qual.length, 'no request yet'], ['Rank-ups', ups, 'recently']]
        .map(([t, v, s]) => html`<div class="stat"><div class="kicker">${t}</div><div class="v">${v}</div><div class="sub">${s}</div></div>`)}</div>
      <div class="g2 mt">
        <div class="card"><div class="card-h"><h2>Requests</h2>${seg('ru-f', ['Open', 'Closed', 'All'], f)}</div>
          ${show.length ? show.slice(0, 60).map((r) => requestCard(r, mine.includes(r))) : empty('No requests here', 'Players request a match from their Home screen once they qualify.')}</div>
        <div class="grid">
          <div class="card"><h2>Qualified — no request yet</h2>${qual.length ? qual.map((p) => html`<div class="row" style="margin-top:10px">${av(p.name, p.color)}<div class="grow"><div class="bold">${p.name}</div>
            <div class="tiny muted">${p.points} pts · ${p.rank} → ${levelName(p.level + 1)}</div></div><button class="btn sm" data-a="ru-start" data-id="${p.id}">Start match</button></div>`) : empty('Nobody waiting')}</div>
          <div class="card"><h2>Manual rank change</h2><div class="small muted">Rank someone up or down without a match.</div>
            ${field('Player', sel('mr-pid', playerOpts(roster()), '', { placeholder: 'Choose player', attrs: 'data-ch="mr-pid"' }))}
            <div class="small muted" id="mr-cur" style="margin-top:6px"></div>
            ${field('Reason (required)', html`<input class="in" id="mr-why" maxlength="120">`)}
            <div class="row mt"><button class="btn good grow" data-a="rank-step" data-v="1">▲ Rank up</button><button class="btn danger grow" data-a="rank-step" data-v="-1">▼ Rank down</button></div></div>
        </div></div>`;
  };
  function requestCard(r, mine) {
    const p = PMAP[r.pid] || { name: '(removed)', color: '#888', points: 0 };
    const open = r.status === 'pending' || r.status === 'scheduled';
    const info = open ? (r.status === 'scheduled' ? `Scheduled: ${r.scheduled_for || 'time TBD'}${r.details ? ' · ' + r.details : ''} · with ${r.manager ? pname(r.manager) : 'any manager'}`
      : `Requested ${niceTs(r.ts)} · waiting for ${r.manager ? pname(r.manager) : 'any manager'}`)
      : `${r.status[0].toUpperCase() + r.status.slice(1)} · by ${r.decided_by || '?'} · ${niceTs(r.decided_ts || r.ts)}${r.score ? ' · ' + r.score : ''}`;
    return html`<div class="req mt ${mine ? 'mine' : ''}"><div class="row">${av(p.name, p.color)}<div class="grow"><div class="bold">${p.name}</div>
        <div class="tiny muted">${levelName(r.from_level)} → ${levelName(r.to_level)} · ${p.points} pts</div></div>${mine ? chip('Yours', '', 'soft') : ''}${chip(r.status, STATUS_COLORS[r.status])}</div>
      <div class="small" style="margin-top:8px">${info}</div>${r.message ? html`<div class="small muted">“${r.message}”</div>` : ''}${r.result_note ? html`<div class="small muted">${r.result_note}</div>` : ''}
      ${open && can('rank') ? html`<div class="row wrap gap6 mt"><button class="btn good sm" data-a="ru-result" data-id="${r.id}">Record result</button>
        <button class="btn ghost sm" data-a="ru-schedule" data-id="${r.id}">${r.status === 'pending' ? 'Schedule' : 'Reschedule'}</button><span class="grow"></span>
        <button class="btn danger sm" data-a="ru-cancel" data-id="${r.id}">Cancel</button></div>` : ''}</div>`;
  }

  // -------------------------------------------------------------- activity
  VIEWS.activity = () => {
    const acts = S.activity || [];
    return html`${pageHead('Activity', 'Every change, who made it and when')}<div class="card">
      ${acts.slice(0, UI.act.n).map((a) => html`<div class="row" style="align-items:flex-start;padding:8px 0;border-bottom:1px solid var(--line)"><span class="status-dot"></span><div class="grow"><div>${a.text}</div><div class="tiny muted">${a.by} · ${niceTs(a.ts)}</div></div></div>`)}
      ${acts.length ? '' : empty('Nothing yet')}${acts.length > UI.act.n ? html`<div class="more"><button class="btn ghost sm" data-a="act-more">Show more (${acts.length - UI.act.n} left)</button></div>` : ''}</div>`;
  };

  // -------------------------------------------------------------- settings
  VIEWS.settings = () => {
    const X = S.settings;
    const pts = X.points;
    const pf = [['start_points', 'Starting points', X.start_points], ['rank_step', 'Points per rank-up match', X.rank_step],
      ...S.consts.positions.map((p) => [`win.${p}`, `${L(p)} win`, pts.win[p]]), ['loss', 'Loss (played)', pts.loss], ['team_win_bonus', 'Team win bonus', pts.team_win_bonus],
      ['practice', 'Practice (+)', pts.practice], ['absence', 'Unexcused absence (−)', pts.absence], ['scrimmage_win', 'Scrimmage win (+)', pts.scrimmage_win],
      ['scrimmage_loss', 'Scrimmage loss (−)', pts.scrimmage_loss], ['challenge_win', 'Challenge win', pts.challenge_win], ['challenge_loss', 'Challenge loss', pts.challenge_loss],
      ['level_step', 'Training pts per level', X.level_step]];
    const E = X.extras;
    const xf = [...S.consts.levels.map((l) => [`quiz.${l}`, `Quiz · ${l}`, E.quiz_points[l]]), ...S.consts.levels.map((l) => [`video.${l}`, `Video · ${l}`, E.video_points[l]]),
      ['quiz_pass_pct', 'Quiz pass %', E.quiz_pass_pct], ['quiz_attempts', 'Quiz tries', E.quiz_attempts], ['integrity_penalty', 'Skipping penalty (−)', E.integrity_penalty]];
    const nPlayers = roster().length, withPin = roster().filter((p) => p.has_pin).length;
    const numGrid = (prefix, list) => html`<div class="cols3">${list.map(([k, t, v]) => field(t, html`<input class="in" type="number" inputmode="numeric" id="${prefix}-${k.replace('.', '_')}" data-k="${k}" value="${v}">`))}</div>`;
    return html`${pageHead('Settings', 'Team info, sign-in, point values, Discord and data')}
      <div class="card"><h2>Team</h2><div class="cols3">${field('Team name', html`<input class="in" id="st-name" value="${S.team.name}" maxlength="60">`)}${field('School', html`<input class="in" id="st-school" value="${S.team.school}" maxlength="80">`)}${field('Season', html`<input class="in" id="st-season" value="${S.team.season}" maxlength="20">`)}</div>
        <button class="btn mt" data-a="set-team">Save team info</button></div>
      <div class="card"><h2>Player sign-in (no license key)</h2><div class="small muted">Players choose the Player tab, type this team code, pick their name and make their own PIN. Leave it empty to turn player sign-in off.</div>
        <div class="row wrap mt"><input class="in" id="st-code" value="${X.player_code}" maxlength="40" placeholder="e.g. Lions2026" style="max-width:260px" autocapitalize="off"><button class="btn" data-a="set-code">Save code</button></div>
        <div class="small mt ${X.player_code ? 'good' : 'muted'}">${X.player_code ? `On · ${withPin} of ${nPlayers} players have made a PIN` : 'Off — no team code set'}</div>
        <div class="tiny muted">Forgot PIN? Roster → tap the player → Edit → Reset PIN.</div></div>
      <div class="card"><h2>Point system</h2><div class="small muted">Changes apply to new points only — history stays the same.</div>${numGrid('sp', pf)}<button class="btn mt" data-a="set-points">Save point values</button></div>
      <div class="card"><h2>Extra points — videos & quizzes</h2>${numGrid('sx', xf)}<button class="btn mt" data-a="set-extras">Save extra points</button></div>
      <div class="card"><h2>Skill-based points (like Valorant)</h2><div class="small muted">Scrimmages and challenges use a hidden skill rating (starts at ${X.elo.start}). Beat a stronger player = more points; lose to a weaker one = lose more. K is how fast ratings move — set it to 0 to turn this off.</div>
        ${numGrid('se', [['k', 'K (0 = off)', X.elo.k], ['min_pct', 'Smallest change %', X.elo.min_pct], ['max_pct', 'Biggest change %', X.elo.max_pct]])}
        <button class="btn mt" data-a="set-elo">Save skill-based points</button></div>
      <div class="card"><h2>Discord — managers' channel</h2><div class="small muted">Discord: Server Settings → Integrations → Webhooks → New Webhook → pick the managers' channel → Copy Webhook URL.</div>
        ${field('Webhook URL', html`<input class="in" id="st-hook" type="password" value="${X.webhook}" placeholder="https://discord.com/api/webhooks/…" autocomplete="off">`)}
        ${field('Ping (optional) — e.g. <@&ROLE_ID>', html`<input class="in" id="st-mention" value="${X.mention}" maxlength="80">`)}
        <div class="row wrap mt"><button class="btn" data-a="set-discord">Save webhook</button><button class="btn ghost" data-a="test-discord">Send test message</button><button class="btn ghost" data-a="show-hook">Show / hide URL</button></div></div>
      <div class="card"><h2>Data & backups</h2><div class="small muted">Saved on the server PC in: ${X.data_dir}. A copy is made every day in the “backups” folder there.</div>
        <div class="row wrap mt"><a class="btn ghost" href="/api/export/backup.json" download>Download backup</a><a class="btn ghost" href="/api/export/leaderboard.csv" download>Export leaderboard (CSV)</a>
          <label class="btn ghost">Import backup<input type="file" accept=".json,application/json" id="st-import" class="hide" data-ch="import"></label><span class="grow"></span><button class="btn danger" data-a="new-season">Start new season…</button></div></div>
      <div class="card"><h2>Your account</h2><div class="kv mt"><div>Signed in as</div><div class="bold">${S.me.username || S.me.display}</div><div>Role</div><div>${roleName()}</div><div>Website build</div><div>${S.build}</div></div></div>`;
  };

  // ------------------------------------------------------------------ more
  VIEWS.more = () => {
    const tabs = TABS[S.me.role] || TABS.player;
    const rest = NAV.filter((n) => allowedRoute(n.k) && !tabs.includes(n.k));
    const dark = document.documentElement.dataset.theme === 'dark';
    return html`${pageHead('More', '')}
      <div class="card" style="padding:8px"><div class="list">${rest.map((n) => html`<a class="item tap" href="#/${n.k}" style="text-decoration:none;color:inherit">${icon(n.i)}<span class="grow bold">${n.t}</span>${badge(n.k)}</a>`)}</div></div>
      <div class="card"><div class="row">${av(S.me.display || S.me.role, roleColor())}<div class="grow"><div class="bold">${S.me.display || S.me.username}</div>${chip(roleName(), roleColor())}</div></div>
        <div class="grid mt"><button class="btn ghost block" data-a="theme">${icon(dark ? 'sun' : 'moon')}${dark ? 'Light mode' : 'Dark mode'}</button>
        ${S.me.kind === 'pin' ? html`<button class="btn ghost block" data-a="change-pin">${icon('key')}Change my PIN</button>` : ''}
        <button class="btn ghost block" data-a="logout">${icon('out')}Sign out</button></div></div>
      <div class="card"><h2>Put it on your home screen</h2><div class="small muted mt"><b>iPhone:</b> in Safari tap Share → “Add to Home Screen”.<br><b>Android:</b> in Chrome tap ⋮ → “Add to Home screen” or “Install app”.</div></div>
      <div class="foot-note">PSAL Badminton · build ${S.build}</div>`;
  };

  // ============================================================== SIGN IN
  function renderLogin() {
    const Lg = UI.login;
    if (!Lg.tab) Lg.tab = store.get('logintab', LOGIN.player_signin ? 'player' : 'staff');
    if (!Lg.code) Lg.code = store.get('teamcode', '');
    const hello = store.get('hello', 'Hello!');
    let form;
    if (Lg.tab === 'player') {
      if (!LOGIN.player_signin) form = html`<div class="card mt"><b>Player sign-in is off.</b><div class="small muted">Ask your coach to turn it on (Settings → Player sign-in), or sign in with a key on the Coach / Manager tab.</div></div>`;
      else if (Lg.step === 'code') form = html`<form data-f="code">${field('Team code', html`<input class="in" id="lg-code" value="${Lg.code}" placeholder="Ask your coach" autocapitalize="off" autocomplete="off" autocorrect="off">`)}
        <button class="btn block mt" type="submit">Next</button><div class="small muted mt">No license key needed — just the team code, your name and your PIN.</div></form>`;
      else {
        const lastPid = store.get('lastpid', '');
        const cur = Lg.pid || (Lg.players.some((p) => p.id === lastPid) ? lastPid : '');
        const pl = Lg.players.find((p) => p.id === cur);
        const newPin = pl && !pl.has_pin;
        form = html`<form data-f="player">${field('Your name', sel('lg-pid', Lg.players.map((p) => [p.id, p.name]), cur, { placeholder: 'Choose your name', attrs: 'data-ch="lg-pid"' }))}
          ${field(newPin ? 'Make a PIN (4–8 digits)' : 'PIN', html`<input class="in" id="lg-pin" type="password" inputmode="numeric" pattern="[0-9]*" maxlength="8" autocomplete="${newPin ? 'new-password' : 'current-password'}">`)}
          ${newPin ? field('Type the new PIN again', html`<input class="in" id="lg-pin2" type="password" inputmode="numeric" pattern="[0-9]*" maxlength="8" autocomplete="new-password">`) : ''}
          ${newPin ? html`<div class="small muted mt">First time? Keep your PIN secret — it's how the app knows it's you.</div>` : ''}
          <button class="btn block mt" type="submit">${newPin ? 'Create PIN & sign in' : 'Sign in'}</button>
          <div class="center mt"><a href="#" class="small" data-a="lg-back">Change team code</a></div></form>`;
      }
    } else {
      const m = Lg.mode;
      form = html`<form data-f="staff">${seg('lg-mode', [['login', 'Login'], ['register', 'Register'], ['license', 'License key']], m, { block: true })}
        ${m !== 'license' ? field('Username', html`<input class="in" id="lg-user" autocomplete="username" autocapitalize="off" value="${store.get('lastuser', '')}">`) : ''}
        ${m !== 'license' ? field('Password', html`<input class="in" id="lg-pass" type="password" autocomplete="${m === 'register' ? 'new-password' : 'current-password'}">`) : ''}
        ${m !== 'login' ? field('License key', html`<input class="in" id="lg-key" autocapitalize="off" autocomplete="off">`) : ''}
        ${m !== 'register' ? field('2FA code (leave blank if not using 2FA)', html`<input class="in" id="lg-2fa" inputmode="numeric" autocomplete="one-time-code">`) : ''}
        <button class="btn block mt" type="submit">${m === 'register' ? 'Create account' : m === 'license' ? 'Activate' : 'Sign in'}</button>
        <div class="small muted mt">Secured with KeyAuth.</div></form>`;
    }
    app.innerHTML = rv(html`<div class="login">
      <div class="brandp"><img src="/icon-192.png" alt=""><div class="k">PSAL BADMINTON</div><h1>Team Points &amp; Lineup System</h1>
        <div class="tag">Hit ${500} points, win your rank-up match, earn your rank.</div>
        <div class="sign"><b>${hello}</b><span>Welcome back — your team is ready to train.</span></div>
        <div class="pills"><span>1st–3rd Singles</span><span>1st–2nd Doubles</span><span>Video Quizzes</span><span>Rank-Up Matches</span></div></div>
      <div class="formp"><div class="box"><h1>Sign in</h1><div class="small muted">${LOGIN.team}</div>
        <div class="mt">${seg('lg-tab', [['player', 'Player'], ['staff', 'Coach / Manager']], Lg.tab, { block: true })}</div>
        ${form}<div class="err" id="lg-err"></div><div class="foot-note">build ${LOGIN.build}</div></div></div></div>`);
    const first = $('#lg-code') || $('#lg-pin') || $('#lg-user') || $('#lg-key');
    if (first && window.innerWidth > 700) first.focus();
  }
  const lgErr = (m) => { const e = $('#lg-err'); if (e) e.textContent = m || ''; };
  async function signedIn() { closeAllSheets(); S = null; await boot(); }

  // ============================================================ HANDLERS
  const A = {};   // click handlers  (data-a)
  const SEG = {}; // segmented-control handlers (data-seg prefix)
  const IN = {};  // input handlers (data-in)
  const CH = {};  // change handlers (data-ch)
  const FORM = {};

  document.addEventListener('click', (e) => {
    const el = e.target.closest('[data-a]');
    if (!el || el.disabled || el.classList.contains('busy')) return;
    const fn = A[el.dataset.a]; if (!fn) return;
    e.preventDefault();
    fn(el, e);
  });
  document.addEventListener('submit', (e) => { const fn = FORM[e.target.dataset.f]; if (fn) { e.preventDefault(); fn(e.target); } });
  document.addEventListener('input', (e) => { const el = e.target.closest('[data-in]'); if (el && IN[el.dataset.in]) IN[el.dataset.in](el, e); });
  document.addEventListener('change', (e) => { const el = e.target.closest('[data-ch]'); if (el && CH[el.dataset.ch]) CH[el.dataset.ch](el, e); });

  A.seg = (el) => {
    const box = el.closest('[data-seg]');
    $$('button', box).forEach((b) => b.classList.toggle('on', b === el));
    const name = box.dataset.seg;
    const key = Object.keys(SEG).find((k) => name === k || name.startsWith(k + '-'));
    if (key) SEG[key](el.dataset.v, name, el);
  };
  A.close = () => closeSheet();
  A['confirm-ok'] = (el) => { const fn = el._ok; closeSheet(); if (fn) fn(); };
  A.theme = () => { const t = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark'; store.set('theme', t); applyTheme(); paint(); };
  A.logout = (el) => run(el, async () => { await req('/api/logout', { method: 'POST' }); S = null; closeAllSheets(); location.hash = ''; boot(); });

  // ---- sign in
  SEG['lg-tab'] = (v) => { UI.login.tab = v; store.set('logintab', v); lgErr(''); renderLogin(); };
  SEG['lg-mode'] = (v) => { UI.login.mode = v; renderLogin(); };
  A['lg-back'] = () => { UI.login.step = 'code'; renderLogin(); };
  CH['lg-pid'] = (el) => { UI.login.pid = el.value; renderLogin(); };
  FORM.code = async (f) => {
    const code = val('lg-code'); if (!code) return lgErr('Type the team code.');
    const btn = $('button[type=submit]', f);
    await run(btn, async () => {
      try { const r = await req('/api/login/names', { method: 'POST', body: JSON.stringify({ code }) });
        UI.login.code = code; UI.login.players = r.players; UI.login.step = 'pick'; store.set('teamcode', code); renderLogin(); }
      catch (e) { lgErr(e.message); }
    });
  };
  FORM.player = async (f) => {
    const pid = $('#lg-pid').value, pin = val('lg-pin'), pin2 = $('#lg-pin2') ? val('lg-pin2') : '';
    if (!pid) return lgErr('Pick your name.');
    if (!pin) return lgErr('Enter your PIN.');
    await run($('button[type=submit]', f), async () => {
      try { await req('/api/login/player', { method: 'POST', body: JSON.stringify({ code: UI.login.code, pid, pin, pin2 }) });
        store.set('lastpid', pid); await signedIn(); }
      catch (e) { lgErr(e.message); const p = $('#lg-pin'); if (p) p.value = ''; }
    });
  };
  FORM.staff = async (f) => {
    const m = UI.login.mode;
    const body = { mode: m, username: $('#lg-user') ? val('lg-user') : '', password: $('#lg-pass') ? $('#lg-pass').value : '', key: $('#lg-key') ? val('lg-key') : '', code: $('#lg-2fa') ? val('lg-2fa') : '' };
    await run($('button[type=submit]', f), async () => {
      lgErr('');
      try { await req('/api/login/key', { method: 'POST', body: JSON.stringify(body) }); if (body.username) store.set('lastuser', body.username); await signedIn(); }
      catch (e) { lgErr(e.message); }
    });
  };

  // ---- roster
  IN['roster-q'] = (el) => { UI.roster.q = el.value; paintPart('roster-list', rosterList()); };
  SEG['roster-f'] = (v) => { UI.roster.f = v; paintPart('roster-list', rosterList()); };
  A.player = (el) => playerSheet(el.dataset.id);
  A['hist-more'] = (el) => loadHistory(topSheet(), el.dataset.id, +el.dataset.off);
  A['player-add'] = () => openSheet(playerForm(null));
  A['player-edit'] = (el) => { closeSheet(); openSheet(playerForm(PMAP[el.dataset.id])); };
  A['player-save'] = (el) => {
    const b = topSheet();
    const body = { name: val('pf-name', b), grade: val('pf-grade', b), student_id: val('pf-sid', b), role: segVal('pf-role', b), username: val('pf-user', b), discord_id: val('pf-disc', b), notes: val('pf-notes', b) };
    if (!body.name) return toast('Enter a name.', 'error');
    const id = el.dataset.id;
    if (id) { body.id = id; body.active = $('#pf-active', b).checked; }
    run(el, async () => { await act(id ? 'player.update' : 'player.add', body); closeSheet(); });
  };
  A['player-remove'] = (el) => confirmSheet('Remove player?', `This deletes ${pname(el.dataset.id)} and all of their points history. To keep history, untick “Active” instead.`, 'Remove',
    () => run(null, async () => { await act('player.remove', { id: el.dataset.id }); closeAllSheets(); }), { danger: true });
  A['pin-reset'] = (el) => confirmSheet('Reset PIN?', `${pname(el.dataset.id)} will make a new PIN the next time they sign in with the team code.`, 'Reset PIN',
    () => run(null, async () => { await act('player.reset_pin', { id: el.dataset.id }); closeAllSheets(); }));
  A.points = (el) => {
    const id = el.dataset.id;
    const b = openSheet(html`<h2>Adjust points</h2><div class="bold">${pname(id)}</div><div class="small muted">Currently ${PMAP[id].points} pts · ${PMAP[id].rank}</div>
      ${field('Points (use a minus sign to take away)', html`<input class="in" id="ap-amt" type="number" inputmode="numeric" placeholder="e.g. 25 or -10">`)}
      <div class="row wrap gap6 mt">${[10, 25, 50, 100, -10, -25].map((v) => html`<button class="btn ghost sm" data-a="ap-quick" data-v="${v}">${v > 0 ? '+' : ''}${v}</button>`)}</div>
      ${field('Reason', html`<input class="in" id="ap-why" maxlength="120" placeholder="e.g. Great sportsmanship">`)}
      <div class="acts"><button class="btn ghost" data-a="close">Cancel</button><button class="btn" data-a="ap-save" data-id="${id}">Apply</button></div>`);
    $('#ap-amt', b).focus();
  };
  A['ap-quick'] = (el) => { $('#ap-amt', topSheet()).value = el.dataset.v; };
  A['ap-save'] = (el) => {
    const b = topSheet(); const delta = parseInt(val('ap-amt', b), 10);
    if (!delta) return toast('Enter a whole number that isn’t 0.', 'error');
    run(el, async () => { await act('points.adjust', { pids: [el.dataset.id], delta, reason: val('ap-why', b) }); closeAllSheets(); });
  };

  // ---- rank-up requests
  A['ru-request'] = (el) => {
    const id = el.dataset.id; const p = PMAP[id];
    const hasHook = S.webhook;
    closeAllSheets();
    openSheet(html`<h2>Request a rank-up match</h2><div class="bold">${p.name}: ${p.rank} → ${levelName(p.level + 1)}</div>
      <div class="small muted">${p.points} points — qualified! Pick a manager to run the rank-up match.</div>
      ${field('Ask which manager?', sel('rq-mgr', [['', 'Any manager']].concat(S.managers.map((m) => [m.id, m.name])), ''))}
      ${field('Message (optional)', html`<input class="in" id="rq-msg" maxlength="200" placeholder="e.g. I'm free after practice Tue/Thu">`)}
      <div class="small muted mt">${hasHook ? 'The manager gets a Discord ping.' : 'Tip: tell the manager in person too.'}</div>
      <div class="acts"><button class="btn ghost" data-a="close">Cancel</button><button class="btn" data-a="rq-send" data-id="${id}">Send request</button></div>`);
  };
  A['rq-send'] = (el) => { const b = topSheet(); run(el, async () => { await act('rankup.request', { id: el.dataset.id, manager: val('rq-mgr', b), message: val('rq-msg', b) }); closeSheet(); }); };
  A['ru-cancel'] = (el) => confirmSheet('Cancel request?', 'They can request again later.', 'Cancel request', () => run(null, () => act('rankup.cancel', { id: el.dataset.id })), { danger: true });
  A['ru-start'] = (el) => run(el, () => act('rankup.request', { id: el.dataset.id, manager: S.me.mgr_pid || '', message: 'Started by a manager' }));
  A['ru-schedule'] = (el) => {
    const r = S.rankups.find((x) => x.id === el.dataset.id);
    openSheet(html`<h2>Schedule ${pname(r.pid)}'s rank-up match</h2>
      <div class="cols2">${field('Date', html`<input class="in" type="date" id="rs-date" value="${today()}">`)}${field('Time', html`<input class="in" id="rs-time" placeholder="e.g. 3:30 PM" maxlength="40">`)}</div>
      ${field('Format / opponent', html`<input class="in" id="rs-det" value="${r.details || ''}" maxlength="120" placeholder="e.g. Best of 3 to 21 vs a manager">`)}
      <div class="acts"><button class="btn ghost" data-a="close">Cancel</button><button class="btn" data-a="rs-save" data-id="${r.id}">Schedule</button></div>`);
  };
  A['rs-save'] = (el) => { const b = topSheet(); run(el, async () => { await act('rankup.schedule', { id: el.dataset.id, date: val('rs-date', b), time: val('rs-time', b), details: val('rs-det', b) }); closeSheet(); }); };
  A['ru-result'] = (el) => {
    const r = S.rankups.find((x) => x.id === el.dataset.id);
    openSheet(html`<h2>${pname(r.pid)} → ${levelName(r.to_level)}</h2>${field('Result', seg('rr-res', [['1', 'Passed — rank up'], ['0', 'Did not pass']], '1', { block: true }))}
      ${field('Score (optional)', html`<input class="in" id="rr-score" placeholder="e.g. 21-17, 21-19" maxlength="60">`)}
      ${field('Note (optional)', html`<input class="in" id="rr-note" maxlength="200" placeholder="e.g. Great net play — work on backhand clears">`)}
      <div class="acts"><button class="btn ghost" data-a="close">Cancel</button><button class="btn good" data-a="rr-save" data-id="${r.id}">Save result</button></div>`);
  };
  A['rr-save'] = (el) => { const b = topSheet(); run(el, async () => { await act('rankup.decide', { id: el.dataset.id, passed: segVal('rr-res', b) === '1', score: val('rr-score', b), note: val('rr-note', b) }); closeSheet(); }); };
  SEG['ru-f'] = (v) => { UI.ru.f = v; paint(); };
  CH['mr-pid'] = (el) => { const p = PMAP[el.value]; paintPart('mr-cur', p ? `Current rank: ${p.rank} · ${p.points} pts` : ''); };
  A['rank-step'] = (el) => {
    const pid = val('mr-pid'), why = val('mr-why'), step = +el.dataset.v;
    if (!pid) return toast('Choose a player.', 'error');
    if (!why) return toast('Add a reason for the rank change.', 'error');
    const p = PMAP[pid]; const to = levelName(p.level + step);
    if (p.level + step < 0) return toast("They're already at the lowest rank.", 'error');
    confirmSheet('Change rank?', `${p.name}: ${p.rank} → ${to}\nReason: ${why}`, step > 0 ? 'Rank up' : 'Rank down', () => run(null, () => act('rank.set', { id: pid, step, reason: why })), { danger: step < 0 });
  };

  // ---- lineup & challenges
  A['lineup-save'] = (el) => {
    const lu = {}; const seen = new Set(); let dup = false;
    for (const pos of S.consts.positions) {
      lu[pos] = [];
      for (let i = 0; i < S.consts.sizes[pos]; i++) { const v = val(`lu-${pos}-${i}`); if (v) { if (seen.has(v)) dup = true; seen.add(v); lu[pos].push(v); } }
    }
    if (dup) return toast('A player can only be in one spot.', 'error');
    run(el, () => act('lineup.set', { lineup: lu }));
  };
  A['lineup-auto'] = () => {
    const ids = roster().map((p) => p.id);
    const plan = { S1: ids.slice(0, 1), S2: ids.slice(1, 2), S3: ids.slice(2, 3), D1: ids.slice(3, 5), D2: ids.slice(5, 7) };
    for (const pos of S.consts.positions) for (let i = 0; i < S.consts.sizes[pos]; i++) { const el = $(`#lu-${pos}-${i}`); if (el) { el.value = plan[pos][i] || ''; DIRTY.add(el.id); } }
    toast('Filled by points — press Save lineup to keep it.');
  };
  SEG['ch-w'] = (v) => { UI.ch.win = v; };
  A.challenge = (el) => {
    const c = val('ch-c'), d = val('ch-d');
    if (!c || !d) return toast('Pick both players.', 'error');
    if (c === d) return toast('Pick two different players.', 'error');
    run(el, () => act('challenge.record', { challenger: c, defender: d, winner: UI.ch.win, score: val('ch-score') }));
  };

  // ---- matches
  SEG['m-tab'] = (v) => { UI.matches.tab = v; paint(); };
  SEG['m-home'] = (v) => { UI.matches.home = v; };
  SEG.mres = (v, name) => { UI.matches.res[name.slice(5)] = v; paintPart('m-preview', matchPreview()); };
  A['match-save'] = (el) => {
    const opp = val('m-opp'); const date = val('m-date');
    if (!date) return toast('Pick the date.', 'error');
    if (!opp) return toast('Enter the opponent school.', 'error');
    const results = {}; const lines = []; const R = S.rules;
    for (const pos of S.consts.positions) {
      const res = UI.matches.res[pos] || 'Win'; const played = res !== 'Not played';
      const ids = []; for (let i = 0; i < S.consts.sizes[pos]; i++) { const v = val(`m-${pos}-${i}`); if (v) ids.push(v); }
      results[pos] = { players: ids, won: res === 'Win', played, score: val(`m-score-${pos}`) };
      if (played) lines.push(`${L(pos)}: ${ids.map(pname).join(' & ') || '?'} ${res === 'Win' ? 'won' : 'lost'} → +${res === 'Win' ? R.win[pos] : R.loss}`);
    }
    const played = Object.values(results).filter((r) => r.played); const wins = played.filter((r) => r.won).length;
    if (wins > played.length / 2 && R.team_win_bonus) lines.push(`Team win bonus: +${R.team_win_bonus} each`);
    confirmSheet(`Save match vs ${opp}?`, lines.join('\n'), 'Save & award points', () => run(null, async () => {
      await act('match.record', { date, opponent: opp, home: UI.matches.home === 'Home', results }); UI.matches.res = {}; paint(); }));
  };
  A['match-del'] = (el) => confirmSheet('Delete match?', `This removes the match vs ${el.dataset.n} and takes back the points it gave.`, 'Delete',
    () => run(null, () => act('match.delete', { id: el.dataset.id })), { danger: true });

  // ---- practice
  SEG['p-tab'] = (v) => { UI.prac.tab = v; paint(); if (v === 'Attendance' && UI.prac.loaded !== UI.prac.date) loadAttendance(); };
  SEG['p-recent'] = (v) => { UI.prac.recent = v; paint(); };
  CH['p-date'] = (el) => { if (!el.value) return; UI.prac.date = el.value; UI.prac.loaded = null; DIRTY.delete('p-date'); paint(); loadAttendance(); };
  SEG.att = (v, name) => {
    const id = name.slice(4); UI.prac.status[id] = v;
    const r = document.getElementById('rs-' + id); if (r) { r.classList.toggle('hide', v !== 'Excused'); if (v === 'Excused') r.focus(); }
    paintPart('att-preview', attPreview());
  };
  IN.reason = (el) => { UI.prac.reasons[el.dataset.id] = el.value; };
  A['att-all'] = () => { UI.prac.status = {}; paint(); };
  A['att-save'] = (el) => {
    const present = [], absent = [], excused = {};
    for (const p of roster()) {
      const s = UI.prac.status[p.id] || 'Present';
      if (s === 'Present') present.push(p.id);
      else if (s === 'Absent') absent.push(p.id);
      else { const why = (UI.prac.reasons[p.id] || '').trim(); if (!why) return toast(`Add a reason for ${p.name}'s excused absence (or mark them Absent).`, 'error'); excused[p.id] = why; }
    }
    const R = S.rules;
    const lines = [`${present.length} present → +${R.practice} each`];
    if (absent.length) lines.push(`${absent.length} unexcused → −${R.absence} each: ${absent.map(pname).join(', ')}`);
    if (Object.keys(excused).length) lines.push(`${Object.keys(excused).length} excused → no change`);
    if (UI.prac.saved) lines.push('This day was already saved — the old points will be undone first.');
    confirmSheet(`${UI.prac.saved ? 'Replace' : 'Save'} attendance for ${niceDate(UI.prac.date)}?`, lines.join('\n'), 'Save',
      () => run(null, async () => { await act('attendance.save', { date: UI.prac.date, present, absent, excused }); UI.prac.saved = true; paint(); }));
  };
  A['att-del'] = (el) => confirmSheet('Undo this practice?', `Removes attendance for ${el.dataset.n} and reverses its points.`, 'Undo',
    () => run(null, async () => { await act('attendance.delete', { id: el.dataset.id }); UI.prac.loaded = null; }), { danger: true });
  SEG['scr-type'] = (v) => { UI.prac.scrType = v; paint(); };
  SEG['scr-win'] = (v) => { UI.prac.scrWin = v; };
  A['scr-save'] = (el) => {
    const n = UI.prac.scrType === 'Doubles' ? 2 : 1;
    const a = [], b = [];
    for (let i = 0; i < n; i++) { a.push(val(`sa-${i}`)); b.push(val(`sb-${i}`)); }
    if (a.concat(b).some((x) => !x)) return toast(`Pick ${n * 2} players.`, 'error');
    if (new Set(a.concat(b)).size !== n * 2) return toast('Each player can only be on one side once.', 'error');
    run(el, () => act('scrimmage.record', { a, b, winner: UI.prac.scrWin, score: val('scr-score') }));
  };
  A['scr-del'] = (el) => run(el, () => act('scrimmage.delete', { id: el.dataset.id }));

  // ---- videos & quizzes
  SEG.lvl = (v, name) => { UI.lib[name.slice(4)].level = v; paint(); };
  SEG.cat = (v, name) => { UI.lib[name.slice(4)].cat = v; paint(); };
  CH['lib-who'] = (el) => {
    UI.lib.who = el.value;
    if (!el.value) return paint();
    run(null, async () => { UI.lib.status[el.value] = await act('video.status', { id: el.value }, { quiet: true }); paint(); });
  };
  async function refreshWho() { if (UI.lib.who && can('quiz_others')) UI.lib.status[UI.lib.who] = await act('video.status', { id: UI.lib.who }, { quiet: true }); paint(); }
  A.watch = (el) => run(el, async () => {
    const r = await act('watch.start', { id: el.dataset.id }, { quiet: true });
    toast(`Opening the video — watch it all the way through. Skipping or speeding up = no points and −${S.rules.penalty}.`, 'info', 6000);
    location.href = r.url;
  });
  A.quiz = (el) => quizSheet(el.dataset.id);
  A['quiz-submit'] = (el) => {
    const b = topSheet(); const n = +el.dataset.n; const answers = [];
    for (let i = 0; i < n; i++) { const c = $(`input[name="q${i}"]:checked`, b); answers.push(c ? +c.value : -1); }
    const miss = answers.indexOf(-1);
    if (miss >= 0) { $('#quiz-err', b).textContent = `Answer every question first (question ${miss + 1} is empty).`; return; }
    run(el, async () => {
      const res = await act('quiz.submit', { id: el.dataset.id, answers }, { quiet: true });
      closeSheet();
      openSheet(html`<h2>${res.passed ? 'Passed!' : 'Not quite'}</h2><div style="font-size:30px;font-weight:800" class="${res.passed ? 'good' : 'bad'}">${res.score} / ${res.total} correct</div>
        <div class="mt">${res.passed ? `+${res.points} points added.` : `Review question(s) ${res.wrong.map((i) => i + 1).join(', ')} and try again — ${res.attempts_left} ${res.attempts_left === 1 ? 'try' : 'tries'} left.`}</div>
        <div class="acts"><button class="btn" data-a="close">OK</button></div>`);
    });
  };
  A['quiz-reset'] = (el) => run(el, async () => { await act('quiz.reset', { pid: UI.lib.who, id: el.dataset.id }); await refreshWho(); });
  A['clear-skip'] = (el) => run(el, async () => { await act('video.clear_skip', { pid: UI.lib.who, id: el.dataset.id }); await refreshWho(); });
  A.starters = (el) => run(el, () => act('video.starters', { kind: el.dataset.kind }));
  A['video-add'] = (el) => videoEditor(null, el.dataset.kind);
  A['video-edit'] = (el) => videoEditor(el.dataset.id, el.dataset.kind);
  A['video-del'] = (el) => { const v = S.videos.find((x) => x.id === el.dataset.id);
    confirmSheet('Delete video?', `Remove “${v ? v.title : ''}”? Points players already earned are kept.`, 'Delete', () => run(null, () => act('video.delete', { id: el.dataset.id })), { danger: true }); };
  SEG['ve-level'] = (v) => { if (!VED || VED.pointsTouched) return; const el = $('#ve-pts', topSheet()); if (el) el.value = (VED.kind === 'quiz' ? S.rules.quiz_points : S.rules.video_points)[v]; };
  IN['ve-pts'] = () => { if (VED) VED.pointsTouched = true; };
  A['ve-addq'] = () => { vedSync(); VED.qs.push({ q: '', options: ['', '', '', ''], answer: 0 }); paintPartIn(topSheet(), 've-qs', vedQuestions()); };
  A['ve-delq'] = (el) => { vedSync(); VED.qs.splice(+el.dataset.i, 1); paintPartIn(topSheet(), 've-qs', vedQuestions()); };
  SEG.va = () => {};
  function paintPartIn(root, id, content) { const el = root && $('#' + id, root); if (el) el.innerHTML = rv(content); }
  A['ve-save'] = (el) => {
    const b = topSheet(); vedSync();
    const body = { id: VED.id, kind: VED.kind, title: val('ve-title', b), url: val('ve-url', b), category: val('ve-cat', b), level: segVal('ve-level', b),
      points: parseInt(val('ve-pts', b), 10), minutes: parseInt(val('ve-min', b), 10), questions: VED.kind === 'quiz' ? VED.qs : [] };
    const err = $('#ve-err', b);
    if (!body.title) { err.textContent = 'Give the video a title.'; return; }
    if (!ytId(body.url)) { err.textContent = 'Use a YouTube link — only YouTube videos can be tracked for skipping.'; return; }
    if (isNaN(body.points) || isNaN(body.minutes)) { err.textContent = 'Points and minutes must be whole numbers.'; return; }
    run(el, async () => { try { await act('video.save', body); closeSheet(); } catch (e) { err.textContent = e.message; } });
  };

  // ---- leaderboard
  SEG['lb-f'] = (v) => { UI.lb.f = v; paint(); };

  // ---- training
  CH['tr-player'] = (el) => run(null, () => act('training.set_player', { id: el.value }));
  SEG['tr-effort'] = (v) => { UI.tr.effort = v; if (!UI.tr.pointsTouched) { const p = $('#tr-pts'); if (p) p.value = suggestPoints(); } };
  IN['tr-min'] = () => { if (!UI.tr.pointsTouched) { const p = $('#tr-pts'); if (p) { p.value = suggestPoints(); DIRTY.add('tr-pts'); } } };
  IN['tr-pts'] = () => { UI.tr.pointsTouched = true; };
  IN.skill = (el) => { const v = $('#skv-' + el.dataset.i); if (v) v.textContent = el.value; };
  const readSkills = () => { const o = {}; S.consts.skills.forEach((k, i) => { const r = $('#sk-' + i); if (r) o[k] = +r.value; }); return o; };
  A['tr-log'] = (el) => run(el, async () => {
    await act('training.log', { manager: val('tr-mgr'), focus: val('tr-focus'), minutes: parseInt(val('tr-min'), 10), effort: +UI.tr.effort, points: parseInt(val('tr-pts'), 10), notes: val('tr-notes'), skills: readSkills() });
    UI.tr.pointsTouched = false;
  });
  A['tr-skills'] = (el) => run(el, () => act('training.skills', { skills: readSkills() }));
  A['tr-del'] = (el) => run(el, () => act('training.delete', { id: el.dataset.id }));

  // ---- notes
  SEG['n-f'] = (v) => { UI.notes.f = v; paint(); };
  SEG['n-prio'] = (v) => { UI.notes.prio = v; };
  A['note-add'] = (el) => {
    const pid = val('n-pid'); if (!pid) return toast('Choose a player.', 'error');
    run(el, () => act('note.add', { pid, area: val('n-area'), priority: UI.notes.prio, text: val('n-text'), send: $('#n-send').checked }));
  };
  A['note-send'] = (el) => run(el, () => act('note.send', { ids: [el.dataset.id] }));
  A['note-send-all'] = (el) => { const n = (S.notes || []).filter((x) => !x.resolved).length;
    if (!n) return toast('No open notes to send.', 'error');
    confirmSheet('Send to managers?', `Post ${n} open note(s) to the managers' Discord channel?`, 'Send', () => run(el, () => act('note.send', { ids: 'open' }))); };
  A['note-resolve'] = (el) => run(el, () => act('note.resolve', { id: el.dataset.id, resolved: !!el.dataset.v }, { quiet: true }));
  A['note-del'] = (el) => run(el, () => act('note.delete', { id: el.dataset.id }));

  // ---- activity
  A['act-more'] = () => { UI.act.n += 100; paint(); };

  // ---- settings
  A['set-team'] = (el) => run(el, () => act('settings.team', { name: val('st-name'), school: val('st-school'), season: val('st-season') }));
  A['set-code'] = (el) => run(el, () => act('settings.player_code', { code: val('st-code') }));
  const numValues = (prefix) => { const o = {}; $$(`input[id^="${prefix}-"]`).forEach((i) => { o[i.dataset.k] = i.value; }); return o; };
  A['set-points'] = (el) => run(el, () => act('settings.points', { values: numValues('sp') }));
  A['set-extras'] = (el) => run(el, () => act('settings.extras', { values: numValues('sx') }));
  A['set-elo'] = (el) => run(el, () => act('settings.elo', { values: numValues('se') }));
  CH['scr-pick'] = () => paintPart('scr-prev', scrPreview());
  CH['ch-pick'] = () => paintPart('ch-prev', chPreview());
  A['set-discord'] = (el) => run(el, () => act('settings.discord', { webhook: val('st-hook'), mention: val('st-mention') }));
  A['test-discord'] = (el) => run(el, () => act('settings.discord_test', {}));
  A['show-hook'] = () => { const i = $('#st-hook'); i.type = i.type === 'password' ? 'text' : 'password'; };
  CH.import = (el) => {
    const f = el.files && el.files[0]; if (!f) return;
    confirmSheet('Import backup?', 'This replaces the current team data. A copy of the current data is saved on the server PC first.', 'Import', () => run(null, async () => {
      const fd = new FormData(); fd.append('file', f);
      const d = await req('/api/import', { method: 'POST', body: fd });
      DIRTY.clear(); setState(d.state); toast(d.msg, 'success');
    }), { danger: true });
    el.value = '';
  };
  A['new-season'] = () => {
    openSheet(html`<h2>Start a new season</h2><p class="muted">Everyone goes back to the starting points and Bronze. Matches, challenges, practices and training are archived to a file on the server PC. The roster, lineup and videos stay.</p>
      ${field('New season name', html`<input class="in" id="ns-name" value="${new Date().getFullYear() + 1}" maxlength="20">`)}
      <div class="acts"><button class="btn ghost" data-a="close">Cancel</button><button class="btn danger" data-a="ns-go">Start new season</button></div>`);
  };
  A['ns-go'] = (el) => { const n = val('ns-name', topSheet()); if (!n) return; run(el, async () => { await act('season.new', { name: n }); closeSheet(); }); };

  // ---- my PIN
  A['change-pin'] = () => openSheet(html`<h2>Change my PIN</h2>
    ${field('Current PIN', html`<input class="in" id="cp-old" type="password" inputmode="numeric" maxlength="8" autocomplete="current-password">`)}
    ${field('New PIN (4–8 digits)', html`<input class="in" id="cp-new" type="password" inputmode="numeric" maxlength="8" autocomplete="new-password">`)}
    ${field('New PIN again', html`<input class="in" id="cp-new2" type="password" inputmode="numeric" maxlength="8" autocomplete="new-password">`)}
    <div class="acts"><button class="btn ghost" data-a="close">Cancel</button><button class="btn" data-a="cp-save">Change PIN</button></div>`);
  A['cp-save'] = (el) => { const b = topSheet(); run(el, async () => { await act('me.pin', { old: val('cp-old', b), new: val('cp-new', b), new2: val('cp-new2', b) }); closeSheet(); }); };

  // ================================================================= BOOT
  async function boot() {
    try {
      const d = await req('/api/state');
      if (d.signin) { LOGIN = d.login; UI.login.step = 'code'; UI.login.pid = ''; renderLogin(); return; }
      S = null;
      const r = (location.hash.replace(/^#\/?/, '') || '').split('?')[0];
      UI.route = r;
      window.scrollTo(0, 0);
      setState(d);
      window.scrollTo(0, 0);
      enterRoute(UI.route);
      if (UI.route === 'quizzes' || UI.route === 'videos') setTimeout(poll, 1500); // back from a video
    } catch (e) {
      app.innerHTML = rv(html`<div class="boot"><div class="center" style="padding:20px"><h2>Can't reach the team website</h2><p class="muted">${e.message}</p><button class="btn" data-a="retry">Try again</button></div></div>`);
    }
  }
  A.retry = () => boot();
  boot();
})();
