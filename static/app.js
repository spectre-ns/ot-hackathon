"use strict";

// --------------------------------------------------------------------------
// API helper
// --------------------------------------------------------------------------
const api = {
  async get(path) { return this._req("GET", path); },
  async post(path, body) { return this._req("POST", path, body); },
  async put(path, body) { return this._req("PUT", path, body); },
  async delete(path, body) { return this._req("DELETE", path, body); },
  async _req(method, path, body) {
    const opts = { method, headers: {} };
    if (body !== undefined) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(body);
    }
    const res = await fetch(path, opts);
    const text = await res.text();
    const data = text ? JSON.parse(text) : null;
    if (!res.ok) throw new Error(data && data.detail ? data.detail : `Error ${res.status}`);
    return data;
  },
};

// --------------------------------------------------------------------------
// State
// --------------------------------------------------------------------------
const state = {
  me: null, config: null, users: [], route: "feed", routeArg: null,
};

const $ = sel => document.querySelector(sel);
const $$ = sel => Array.from(document.querySelectorAll(sel));

// --------------------------------------------------------------------------
// Utils
// --------------------------------------------------------------------------
function initials(name) {
  return name.split(" ").map(p => p[0]).slice(0, 2).join("").toUpperCase();
}
function avatarHTML(user, size = 40) {
  const s = `width:${size}px;height:${size}px;font-size:${Math.round(size * .38)}px;flex-shrink:0;`;
  if (user.avatar_url)
    return `<span class="avatar" style="${s}background-image:url('${user.avatar_url}')"></span>`;
  return `<span class="avatar" style="${s}background:${user.avatar_color || "#4D75FE"}">${initials(user.name)}</span>`;
}
function timeAgo(iso) {
  const secs = Math.floor((Date.now() - new Date(iso)) / 1000);
  for (const [l, s] of [["y",31536e3],["mo",2592e3],["d",86400],["h",3600],["m",60]])
    if (secs >= s) return `${Math.floor(secs/s)}${l} ago`;
  return "just now";
}
function esc(s) {
  const d = document.createElement("div"); d.textContent = s == null ? "" : String(s); return d.innerHTML;
}
function toast(msg, kind = "") {
  const el = document.createElement("div");
  el.className = `toast ${kind}`; el.textContent = msg;
  $("#toast-wrap").appendChild(el);
  setTimeout(() => { el.style.opacity = "0"; el.style.transition = "opacity .3s"; }, 2800);
  setTimeout(() => el.remove(), 3200);
}
const REACTIONS = ["🎉","👏","❤️","🔥","🙌","🚀"];

// --------------------------------------------------------------------------
// Auth / boot
// --------------------------------------------------------------------------
async function boot() {
  state.config = await api.get("/api/config");
  try { state.me = await api.get("/api/me"); } catch { state.me = null; }
  if (state.me) {
    state.users = await api.get("/api/users");
    showApp();
  } else showLogin();
}
function showLogin() {
  $("#login").classList.remove("hidden"); $("#app").classList.add("hidden");
  if (state.config.github_oauth_enabled) $("#github-login-btn").classList.remove("hidden");
  api.get("/api/users").then(u => {
    state.users = u;
    const sel = $("#demo-user-select");
    sel.innerHTML = u.map(u =>
      `<option value="${u.id}">${esc(u.name)} — ${esc(u.title||"Employee")}${u.is_admin?" (admin)":""}</option>`
    ).join("");
  });
  api.get("/api/feed?limit=3").then(feed => {
    $("#login-aside-feed").innerHTML = feed.map(k => `
      <div class="aside-card" style="animation-delay:${feed.indexOf(k)*.15}s">
        <div class="ac-top">${k.value.emoji} <strong>${esc(k.giver.name)}</strong> → ${esc(k.receiver.name)}</div>
        <div class="ac-msg">${esc(k.message)}</div>
      </div>`).join("");
  });
}
$("#demo-login-btn").addEventListener("click", async () => {
  await api.post("/api/auth/demo", { user_id: parseInt($("#demo-user-select").value, 10) });
  await boot();
});
function showApp() {
  $("#login").classList.add("hidden"); $("#app").classList.remove("hidden");
  renderTopbar();
  $$(".admin-only").forEach(e => e.classList.toggle("hidden", !state.me.is_admin));
  go(state.route, state.routeArg);
}
async function refreshMe() {
  state.me = await api.get("/api/me"); renderTopbar();
}
function renderTopbar() {
  $("#giving-balance").textContent = state.me.giving_balance;
  const btn = $("#avatar-btn");
  btn.style.backgroundImage = state.me.avatar_url ? `url('${state.me.avatar_url}')` : "";
  btn.style.background = state.me.avatar_url ? "" : state.me.avatar_color;
  btn.textContent = state.me.avatar_url ? "" : initials(state.me.name);
  // Notification badge
  const badge = $("#notif-badge");
  const count = state.me.unread_notifications || 0;
  if (count > 0) { badge.textContent = count > 9 ? "9+" : count; badge.classList.remove("hidden"); }
  else badge.classList.add("hidden");
}

// --------------------------------------------------------------------------
// Routing
// --------------------------------------------------------------------------
function go(route, arg = null) {
  state.route = route; state.routeArg = arg;
  $$(".nav-link").forEach(l => l.classList.toggle("active", l.dataset.route === route));
  const view = $("#view");
  view.innerHTML = '<div class="spinner"></div>';
  (ROUTES[route] || ROUTES.feed)(view, arg).catch(e => {
    view.innerHTML = `<div class="empty">${esc(e.message)}</div>`;
  });
}
document.addEventListener("click", e => {
  const r = e.target.closest("[data-route]");
  if (r) { e.preventDefault(); go(r.dataset.route); }
});

// --------------------------------------------------------------------------
// Views
// --------------------------------------------------------------------------
const ROUTES = {};

// ---- Feed ----
ROUTES.feed = async (view) => {
  const [stats, feed] = await Promise.all([api.get("/api/stats"), api.get("/api/feed")]);
  view.innerHTML = `
    <div class="page-head"><h2>Recognition Feed</h2></div>
    <div class="stats">
      ${sc(stats.kudos_count,"kudos given")}${sc(stats.points_awarded,"points awarded")}
      ${sc(stats.people_recognized,"people recognized")}${sc(stats.crm_events,"CRM events")}
    </div>
    <div class="feed">${feed.map(k=>kudosCard(k)).join("") || empty("🌱","No kudos yet — be the first!")}</div>`;
  wireReactions(view);
};
const sc = (n,l) => `<div class="stat"><div class="stat-num">${n}</div><div class="stat-label">${l}</div></div>`;

function kudosCard(k) {
  const rxns = k.reactions.map(r =>
    `<button class="react-chip${r.mine?" mine":""}" data-kudos="${k.id}" data-emoji="${r.emoji}">${r.emoji} ${r.count}</button>`).join("");
  const artifact = k.artifact_url
    ? `<a class="artifact-link" href="${esc(k.artifact_url)}" target="_blank" rel="noopener">🔗 ${esc(k.artifact_label || k.artifact_url)}</a>`
    : "";
  return `
    <div class="card kudos">
      <div class="kudos-top">
        ${avatarHTML(k.giver,42)}
        <div class="kudos-people">
          <div class="kudos-line"><strong>${esc(k.giver.name)}</strong> <span class="to">recognized</span> <strong>${esc(k.receiver.name)}</strong></div>
          <div class="kudos-time">${timeAgo(k.created_at)}</div>
        </div>
        <span class="value-tag" style="background:${k.value.color}18;color:${k.value.color}">${k.value.emoji} ${esc(k.value.label)}</span>
        <span class="points-badge">+${k.points}</span>
      </div>
      <div class="kudos-msg">${esc(k.message)}${artifact ? `<div class="artifact-wrap">${artifact}</div>` : ""}</div>
      <div class="kudos-foot">
        ${rxns}
        <div class="react-menu"><button class="react-chip react-add" data-toggle-react="${k.id}">😀 react</button></div>
      </div>
    </div>`;
}

function wireReactions(scope) {
  scope.querySelectorAll(".react-chip[data-emoji]").forEach(c =>
    c.addEventListener("click", () => sendReaction(c.dataset.kudos, c.dataset.emoji)));
  scope.querySelectorAll("[data-toggle-react]").forEach(btn => {
    btn.addEventListener("click", e => {
      e.stopPropagation();
      const existing = btn.parentElement.querySelector(".react-picker");
      if (existing) { existing.remove(); return; }
      const picker = document.createElement("div");
      picker.className = "react-picker";
      picker.style.cssText = "display:inline-flex;gap:4px;margin-left:6px;flex-wrap:wrap";
      picker.innerHTML = REACTIONS.map(em =>
        `<button class="react-chip" data-emoji="${em}" style="font-size:15px">${em}</button>`).join("");
      picker.querySelectorAll("button").forEach(b =>
        b.addEventListener("click", () => sendReaction(btn.dataset.toggleReact, b.dataset.emoji)));
      btn.parentElement.appendChild(picker);
    });
  });
}
async function sendReaction(kudosId, emoji) {
  try { await api.post(`/api/kudos/${kudosId}/react`, {emoji}); go(state.route, state.routeArg); }
  catch(e) { toast(e.message, "error"); }
}

// ---- Leaderboard ----
ROUTES.leaderboard = async (view, arg) => {
  const period = arg || "month";
  const rows = await api.get(`/api/leaderboard?period=${period}`);
  const medals = {1:"🥇",2:"🥈",3:"🥉"};
  view.innerHTML = `
    <div class="page-head"><h2>Leaderboard</h2>
      <div class="seg">
        <button class="${period==="month"?"active":""}" data-period="month">This month</button>
        <button class="${period==="all"?"active":""}" data-period="all">All time</button>
      </div>
    </div>
    <div class="card">
      ${rows.map(r => `
        <div class="lb-row" data-profile="${r.user.id}">
          <div class="lb-rank ${r.rank<=3?"top":""}">${medals[r.rank]||r.rank}</div>
          ${avatarHTML(r.user,38)}
          <div class="lb-name">${esc(r.user.name)}<div class="lb-sub">${esc(r.user.title||"")}${r.user.department?" · "+esc(r.user.department):""}</div></div>
          <div class="lb-pts">${r.points} pts</div>
        </div>`).join("") || empty("🏆","No points awarded in this period yet.")}
    </div>`;
  view.querySelectorAll("[data-period]").forEach(b => b.addEventListener("click", () => go("leaderboard", b.dataset.period)));
  wireProfileLinks(view);
};

// ---- People ----
ROUTES.people = async (view) => {
  const users = await api.get("/api/users");
  view.innerHTML = `
    <div class="page-head"><h2>People</h2></div>
    <div class="people-grid">
      ${users.map(u => `
        <div class="card person" data-profile="${u.id}">
          ${avatarHTML(u,64)}
          <div class="person-name">${esc(u.name)}</div>
          <div class="person-title">${esc(u.title||"Employee")}</div>
          <div class="person-pts">${u.earned_points} <span>pts earned</span></div>
        </div>`).join("")}
    </div>`;
  wireProfileLinks(view);
};

// ---- Profile ----
ROUTES.profile = async (view, userId) => {
  const id = userId || state.me.id;
  const p = await api.get(`/api/users/${id}`);
  const isMe = id === state.me.id;
  const crmEtMap = {};
  (state.config.crm_event_types||[]).forEach(e => crmEtMap[e.key] = e);
  view.innerHTML = `
    <div class="card profile-head">
      ${avatarHTML(p.user,88)}
      <div class="profile-meta">
        <h2>${esc(p.user.name)}</h2>
        <div class="sub">${esc(p.user.title||"Employee")}${p.user.department?" · "+esc(p.user.department):""}</div>
        ${p.user.github_login?`<div class="gh">🐙 @${esc(p.user.github_login)}</div>`:""}
      </div>
      <div class="profile-stats">
        <div><div class="ps-num">${p.earned_points}</div><div class="ps-label">pts earned</div></div>
        <div><div class="ps-num">${p.kudos_count}</div><div class="ps-label">kudos received</div></div>
        <div><div class="ps-num">${p.given_count}</div><div class="ps-label">kudos given</div></div>
      </div>
    </div>
    ${p.value_breakdown.length?`<div class="value-breakdown">${p.value_breakdown.map(v=>`<span class="value-tag" style="background:${v.value.color}18;color:${v.value.color}">${v.value.emoji} ${esc(v.value.label)} · ${v.count}</span>`).join("")}</div>`:""}
    <div class="tabs">
      <div class="tab active" data-tab="received">Kudos (${p.received.length})</div>
      <div class="tab" data-tab="github">GitHub (${p.github_contributions.length})</div>
      <div class="tab" data-tab="crm">CRM (${p.crm_contributions.length})</div>
      ${isMe&&p.user.github_login?`<button class="btn btn-ghost" id="profile-sync" style="margin-left:auto;font-size:13px">🔄 Sync GitHub</button>`:""}
    </div>
    <div id="tab-received" class="feed">${p.received.map(k=>kudosCard(k)).join("") || empty("🌱","No kudos yet.")}</div>
    <div id="tab-github" class="card hidden">
      ${p.github_contributions.map(c => `
        <div class="contrib">
          <span class="contrib-kind ${c.kind}">${c.kind==="pr"?"PR":"Issue"}</span>
          <div class="contrib-title">
            ${c.url?`<a href="${esc(c.url)}" target="_blank" rel="noopener" style="color:var(--blue)">${esc(c.title)}</a>`:esc(c.title)}
            <div class="contrib-repo">${esc(c.repo)} #${c.number}</div>
          </div>
          <button class="btn btn-ghost award-artifact-btn" style="font-size:12px;padding:6px 10px"
            data-url="${esc(c.url)}" data-label="${esc(c.kind==="pr"?"PR":"Issue")+" #"+c.number+": "+esc(c.title)}"
            data-receiver="${p.user.id}">Award kudos</button>
        </div>`).join("") || empty("🐙","No synced GitHub activity.")}
    </div>
    <div id="tab-crm" class="card hidden">
      ${p.crm_contributions.map(c => {
        const et = crmEtMap[c.event_type]||{emoji:"📋",label:c.event_type};
        return `
        <div class="contrib">
          <span class="contrib-kind pr" style="background:#eef1ff;color:var(--blue)">${et.emoji}</span>
          <div class="contrib-title">
            ${c.artifact_url?`<a href="${esc(c.artifact_url)}" target="_blank" rel="noopener" style="color:var(--blue)">${esc(c.title)}</a>`:esc(c.title)}
            <div class="contrib-repo">${esc(et.label)} · ${esc(c.company||"")} · ${timeAgo(c.happened_at)}</div>
          </div>
          <span class="contrib-pts">+${c.points}</span>
        </div>`;
      }).join("") || empty("📋","No CRM activity.")}
    </div>`;
  wireReactions(view);
  // Tab switching
  view.querySelectorAll(".tab[data-tab]").forEach(t => t.addEventListener("click", () => {
    view.querySelectorAll(".tab[data-tab]").forEach(x => x.classList.remove("active")); t.classList.add("active");
    ["received","github","crm"].forEach(name => document.getElementById(`tab-${name}`).classList.toggle("hidden", t.dataset.tab !== name));
  }));
  const syncBtn = $("#profile-sync");
  if (syncBtn) syncBtn.addEventListener("click", () => runSync(syncBtn));
  // "Award kudos" buttons on GitHub contributions open the give modal pre-filled
  view.querySelectorAll(".award-artifact-btn").forEach(btn => {
    btn.addEventListener("click", () => openGive({
      receiverId: parseInt(btn.dataset.receiver, 10),
      artifactUrl: btn.dataset.url,
      artifactLabel: btn.dataset.label,
    }));
  });
};

// ---- Rewards (Swag catalog) ----
ROUTES.rewards = async (view, arg) => {
  const tab = arg || "catalog";
  const [catalog, myOrders] = await Promise.all([
    api.get("/api/swag"),
    api.get("/api/swag/orders"),
  ]);
  const spendable = catalog.spendable_points;
  const pendingCount = myOrders.filter(o => o.current_state && o.current_state !== "approved" && o.current_state !== "rejected" && o.current_state !== "shipped").length;
  view.innerHTML = `
    <div class="page-head">
      <h2>Rewards</h2>
      <div class="balance-pill" style="font-size:15px">
        <span>⭐</span> <strong>${spendable}</strong> <span style="color:var(--muted);font-size:13px">pts to spend</span>
      </div>
    </div>
    <div class="tabs">
      <div class="tab ${tab==="catalog"?"active":""}" data-rtab="catalog">Swag Catalog</div>
      <div class="tab ${tab==="orders"?"active":""}" data-rtab="orders">My Orders${myOrders.length?` (${myOrders.length})`:""}
        ${pendingCount?`<span class="notif-badge" style="margin-left:6px">${pendingCount}</span>`:""}
      </div>
    </div>
    <div id="rtab-catalog" class="${tab!=="catalog"?"hidden":""}">
      <div class="swag-grid">
        ${catalog.items.map(item => swagCard(item, spendable)).join("") || empty("🛍️","No swag items yet.")}
      </div>
    </div>
    <div id="rtab-orders" class="${tab!=="orders"?"hidden":""}">
      ${myOrders.length ? myOrders.map(o => orderCard(o)).join("") : empty("📦","You haven't placed any orders yet.")}
    </div>`;
  view.querySelectorAll("[data-rtab]").forEach(t => t.addEventListener("click", () => go("rewards", t.dataset.rtab)));
  view.querySelectorAll(".redeem-btn").forEach(btn => {
    btn.addEventListener("click", () => openRedeemModal(
      parseInt(btn.dataset.itemId, 10), btn.dataset.itemName, parseInt(btn.dataset.cost, 10)));
  });
};

function swagCard(item, spendable) {
  const canAfford = spendable >= item.point_cost;
  const stockLabel = item.stock != null ? `· ${item.stock} left` : "";
  return `
    <div class="card swag-card${!canAfford?" swag-unaffordable":""}">
      <div class="swag-icon">🎁</div>
      <div class="swag-name">${esc(item.name)}</div>
      <div class="swag-desc">${esc(item.description)}</div>
      <div class="swag-footer">
        <span class="points-badge">${item.point_cost} pts${stockLabel}</span>
        ${canAfford
          ? `<button class="btn btn-primary redeem-btn" style="font-size:13px;padding:8px 14px"
              data-item-id="${item.id}" data-item-name="${esc(item.name)}" data-cost="${item.point_cost}">Redeem</button>`
          : `<span class="swag-locked">Need ${item.point_cost - spendable} more pts</span>`}
      </div>
    </div>`;
}

function orderCard(o) {
  const state_info = o.state_info || {};
  const color = state_info.color || "#888";
  return `
    <div class="card kudos" style="margin-bottom:12px">
      <div class="kudos-top">
        <div class="kudos-people" style="flex:1">
          <div class="kudos-line"><strong>${esc(o.item_name)}</strong></div>
          <div class="kudos-time">Ordered ${timeAgo(o.created_at)}${o.notes?` · "${esc(o.notes)}"`:""}</div>
        </div>
        <span class="value-tag" style="background:${color}20;color:${color}">${esc(state_info.name||o.current_state||"pending")}</span>
        <span class="points-badge" style="background:#e6e8f0;color:var(--navy)">-${o.points_cost} pts</span>
      </div>
      ${o.transition_log&&o.transition_log.length?`
        <div style="margin:10px 0 0;padding:10px 14px;background:var(--surface-2);border-radius:8px;font-size:13px;color:var(--muted)">
          ${o.transition_log.map(t=>`<div>${esc(t.label)}: ${esc(t.from)} → <strong>${esc(t.to)}</strong>${t.reason?" — "+esc(t.reason):""}</div>`).join("")}
        </div>`:""}
    </div>`;
}

// ---- Admin ----
ROUTES.admin = async (view, arg) => {
  if (!state.me.is_admin) { view.innerHTML = empty("🔒","Admins only."); return; }
  const subTab = arg || "settings";
  const [settings, pendingOrders, allOrders] = await Promise.all([
    api.get("/api/settings"),
    api.get("/api/swag/orders/pending"),
    api.get("/api/swag/orders/all"),
  ]);
  const pendingLabel = pendingOrders.length ? ` <span class="notif-badge">${pendingOrders.length}</span>` : "";
  view.innerHTML = `
    <div class="page-head"><h2>Admin</h2></div>
    <div class="tabs">
      <div class="tab ${subTab==="settings"?"active":""}" data-atab="settings">Settings</div>
      <div class="tab ${subTab==="crm"?"active":""}" data-atab="crm">CRM Simulator</div>
      <div class="tab ${subTab==="orders"?"active":""}" data-atab="orders">Approvals${pendingLabel}</div>
      <div class="tab ${subTab==="workflow"?"active":""}" data-atab="workflow">Workflow</div>
      <div class="tab ${subTab==="catalog"?"active":""}" data-atab="catalog">Swag Catalog</div>
    </div>
    <div id="atab-settings" class="${subTab!=="settings"?"hidden":""}"></div>
    <div id="atab-crm" class="${subTab!=="crm"?"hidden":""}"></div>
    <div id="atab-orders" class="${subTab!=="orders"?"hidden":""}"></div>
    <div id="atab-workflow" class="${subTab!=="workflow"?"hidden":""}"></div>
    <div id="atab-catalog" class="${subTab!=="catalog"?"hidden":""}"></div>`;
  view.querySelectorAll("[data-atab]").forEach(t => t.addEventListener("click", () => go("admin", t.dataset.atab)));
  renderAdminSettings(document.getElementById("atab-settings"), settings);
  renderCRMSimulator(document.getElementById("atab-crm"));
  renderAdminOrders(document.getElementById("atab-orders"), pendingOrders, allOrders);
  renderWorkflowEditor(document.getElementById("atab-workflow"));
  renderSwagCatalog(document.getElementById("atab-catalog"));
};

// ---- Admin: Settings ----
function renderAdminSettings(el, s) {
  el.innerHTML = `
    <div class="card admin-card">
      <form id="settings-form">
        <h3 style="margin-top:0">Point weights & allowances</h3>
        <div class="weight-field">
          <div><div class="wf-label">Monthly giving allowance</div><div class="wf-desc">Points each employee can give per month</div></div>
          <input type="number" id="monthly_allowance" min="0" max="100000" value="${s.monthly_allowance}" style="width:96px">
        </div>
        <h3>GitHub activity</h3>
        <div class="weight-field">
          <div>
            <div class="wf-label">Auto-accumulation</div>
            <div class="wf-desc">When ON: merged PRs and closed issues auto-award points. When OFF: GitHub activity is informational only; points come from manual kudos.</div>
          </div>
          <label class="toggle-label">
            <input type="checkbox" id="github_accumulation_enabled" ${s.github_accumulation_enabled?"checked":""}>
            <span class="toggle-track"></span>
          </label>
        </div>
        <div class="weight-field">
          <div><div class="wf-label">Points per merged PR</div></div>
          <input type="number" id="pr_points" min="0" max="1000" value="${s.pr_points}" style="width:96px">
        </div>
        <div class="weight-field">
          <div><div class="wf-label">Points per closed issue</div></div>
          <input type="number" id="issue_points" min="0" max="1000" value="${s.issue_points}" style="width:96px">
        </div>
        <h3>CRM event weights</h3>
        ${(state.config.crm_event_types||[]).map(et => `
          <div class="weight-field">
            <div><div class="wf-label">${et.emoji} ${esc(et.label)}</div><div class="wf-desc">${esc(et.desc)}</div></div>
            <input type="number" id="${et.settings_key}" min="0" max="1000" value="${s[et.settings_key]||et.default_points}" style="width:96px">
          </div>`).join("")}
        <div style="margin-top:18px;text-align:right">
          <button class="btn btn-primary" type="submit">Save settings</button>
        </div>
      </form>
    </div>`;
  document.getElementById("settings-form").addEventListener("submit", async e => {
    e.preventDefault();
    try {
      const body = {
        monthly_allowance: parseInt(document.getElementById("monthly_allowance").value, 10),
        github_accumulation_enabled: document.getElementById("github_accumulation_enabled").checked,
        pr_points: parseInt(document.getElementById("pr_points").value, 10),
        issue_points: parseInt(document.getElementById("issue_points").value, 10),
      };
      (state.config.crm_event_types||[]).forEach(et => {
        body[et.settings_key] = parseInt(document.getElementById(et.settings_key).value, 10);
      });
      await api.put("/api/settings", body);
      await refreshMe();
      toast("Settings saved", "success");
    } catch(err) { toast(err.message, "error"); }
  });
}

// ---- Admin: CRM Simulator ----
function renderCRMSimulator(el) {
  const settings = state.config.settings || {};
  el.innerHTML = `
    <div class="card admin-card" style="max-width:720px">
      <h3 style="margin-top:0">CRM Simulator</h3>
      <p style="color:var(--muted);margin-top:4px;font-size:14px">
        Fire a simulated CRM event to award points to an employee. In production, Salesforce
        (or any CRM) would POST the same JSON to <code>/api/crm/event</code> with the
        <code>X-CRM-Key</code> header shown below.
      </p>
      <div class="weight-field" style="align-items:flex-start;gap:12px">
        <div><div class="wf-label">Webhook URL</div><div class="wf-desc">POST this endpoint from your CRM</div></div>
        <code style="font-size:12px;padding:8px;background:var(--surface-2);border-radius:8px;word-break:break-all">/api/crm/event</code>
      </div>
      <div class="weight-field" style="align-items:flex-start;gap:12px">
        <div><div class="wf-label">API Key (X-CRM-Key header)</div><div class="wf-desc">Include in every webhook call</div></div>
        <code class="api-key-display" style="font-size:12px;padding:8px;background:var(--surface-2);border-radius:8px;word-break:break-all;cursor:pointer"
          title="Click to copy" id="api-key-val">${esc(settings.crm_api_key||"—")}</code>
      </div>
      <hr style="border:0;border-top:1px solid var(--line);margin:20px 0">
      <h4 style="margin:0 0 14px">Simulate an event</h4>
      <form id="crm-form">
        <div class="field"><span>Employee (GitHub login or email)</span>
          <select class="select" id="crm-user">
            ${state.users.map(u=>`<option value="${esc(u.github_login||u.id)}">${esc(u.name)}</option>`).join("")}
          </select></div>
        <div class="field"><span>Event type</span>
          <div id="crm-event-chips" class="value-chips"></div></div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px">
          <div class="field"><span>Reference ID</span>
            <input type="text" id="crm-ref" placeholder="OPP-8821" class="select" value="OPP-${Math.floor(Math.random()*9000+1000)}"></div>
          <div class="field"><span>Company</span>
            <input type="text" id="crm-company" placeholder="Acme Corp" class="select" value=""></div>
        </div>
        <div class="field"><span>Title (optional)</span>
          <input type="text" id="crm-title" placeholder="Auto-generated if blank" class="select" value=""></div>
        <div class="modal-foot">
          <span class="form-error" id="crm-error"></span>
          <button type="submit" class="btn btn-primary">Fire event</button>
        </div>
      </form>
      <div id="crm-result" class="hidden" style="margin-top:16px;padding:14px;background:var(--surface-2);border-radius:10px;font-size:14px"></div>
    </div>`;
  // Copy API key
  document.getElementById("api-key-val").addEventListener("click", () => {
    navigator.clipboard.writeText(settings.crm_api_key||"").then(()=>toast("API key copied","success"));
  });
  // Event type chips
  let selectedCrmEvent = null;
  const chipsEl = document.getElementById("crm-event-chips");
  chipsEl.innerHTML = (state.config.crm_event_types||[]).map(et =>
    `<div class="vchip" data-crmkey="${et.key}"><div class="vc-emoji">${et.emoji}</div><div class="vc-label">${esc(et.label)}</div></div>`
  ).join("");
  chipsEl.querySelectorAll(".vchip").forEach(c => c.addEventListener("click", () => {
    chipsEl.querySelectorAll(".vchip").forEach(x=>x.classList.remove("active"));
    c.classList.add("active"); selectedCrmEvent = c.dataset.crmkey;
  }));
  document.getElementById("crm-form").addEventListener("submit", async e => {
    e.preventDefault();
    const errEl = document.getElementById("crm-error");
    errEl.textContent = "";
    if (!selectedCrmEvent) { errEl.textContent = "Select an event type."; return; }
    const userVal = document.getElementById("crm-user").value;
    try {
      const result = await api.post("/api/crm/simulate", {
        event_type: selectedCrmEvent,
        user_identifier: userVal,
        reference_id: document.getElementById("crm-ref").value || `SIM-${Date.now()}`,
        company: document.getElementById("crm-company").value,
        title: document.getElementById("crm-title").value,
        happened_at: new Date().toISOString(),
      });
      const res = document.getElementById("crm-result");
      res.classList.remove("hidden");
      res.innerHTML = result.created
        ? `✅ <strong>+${result.points_awarded} pts</strong> awarded to ${esc(result.user.name)} for "${esc(result.event_type.label)}"!`
        : `⚠️ This reference ID already exists — points refreshed but not re-awarded.`;
      await refreshMe();
    } catch(err) { errEl.textContent = err.message; }
  });
}

// ---- Admin: Orders ----
function renderAdminOrders(el, pendingOrders, allOrders) {
  const wf = null; // loaded lazily
  el.innerHTML = `
    <div class="tabs" style="margin-bottom:16px">
      <div class="tab active" data-otab="pending">Pending (${pendingOrders.length})</div>
      <div class="tab" data-otab="all">All orders (${allOrders.length})</div>
    </div>
    <div id="otab-pending">${renderOrderList(pendingOrders, true)}</div>
    <div id="otab-all" class="hidden">${renderOrderList(allOrders, true)}</div>`;
  el.querySelectorAll("[data-otab]").forEach(t => t.addEventListener("click", () => {
    el.querySelectorAll("[data-otab]").forEach(x=>x.classList.remove("active")); t.classList.add("active");
    document.getElementById("otab-pending").classList.toggle("hidden", t.dataset.otab!=="pending");
    document.getElementById("otab-all").classList.toggle("hidden", t.dataset.otab!=="all");
  }));
  wireOrderActions(el);
}

function renderOrderList(orders, isAdmin = false) {
  if (!orders.length) return empty("✅","No orders here.");
  return orders.map(o => {
    const s = o.state_info || {};
    const transitions = (o.available_transitions||[]).filter(t => !t.requires_admin || isAdmin);
    return `
      <div class="card kudos" style="margin-bottom:14px">
        <div class="kudos-top">
          ${o.user ? avatarHTML(o.user, 38) : ""}
          <div class="kudos-people">
            <div class="kudos-line"><strong>${o.user?esc(o.user.name):"?"}</strong> ordered <strong>${esc(o.item_name)}</strong></div>
            <div class="kudos-time">${timeAgo(o.created_at)}${o.notes?` · "${esc(o.notes)}"`:""}</div>
          </div>
          <span class="value-tag" style="background:${s.color||"#888"}20;color:${s.color||"#888"}">${esc(s.name||"pending")}</span>
          <span class="points-badge" style="background:#e6e8f0;color:var(--navy)">-${o.points_cost} pts</span>
        </div>
        ${transitions.length ? `
          <div style="display:flex;gap:8px;margin-top:12px;flex-wrap:wrap">
            ${transitions.map(t => `
              <button class="btn btn-ghost transition-btn" style="font-size:13px;padding:7px 14px"
                data-order="${o.id}" data-tid="${t.id}" data-label="${esc(t.label)}"
                data-needs-reason="${t.requires_reason?1:0}">
                ${esc(t.label)}
              </button>`).join("")}
          </div>` : ""}
      </div>`;
  }).join("");
}

function wireOrderActions(scope) {
  scope.querySelectorAll(".transition-btn").forEach(btn => {
    btn.addEventListener("click", async () => {
      const needsReason = btn.dataset.needsReason === "1";
      let reason = "";
      if (needsReason) {
        reason = prompt(`Reason for "${btn.dataset.label}":`);
        if (reason === null) return;
      }
      try {
        await api.post(`/api/swag/orders/${btn.dataset.order}/transition`,
          {transition_id: btn.dataset.tid, reason});
        await refreshMe();
        go("admin", "orders");
        toast(`Order ${btn.dataset.label}d`, "success");
      } catch(err) { toast(err.message, "error"); }
    });
  });
}

// ---- Admin: Workflow editor ----
async function renderWorkflowEditor(el) {
  const wf = await api.get("/api/workflow");
  el.innerHTML = `
    <div class="wf-editor">
      <div class="wf-diagram-wrap">
        <div class="wf-diagram" id="wf-diagram">${renderWFDiagram(wf)}</div>
      </div>
      <div class="wf-panel">
        <h4>States</h4>
        <div id="wf-states-list">
          ${wf.states.map(s => `
            <div class="wf-state-row" style="border-left:3px solid ${s.color}">
              <span class="wf-state-chip" style="background:${s.color}20;color:${s.color}">${esc(s.name)}</span>
              <span style="font-size:11px;color:var(--muted)">${s.is_initial?"initial":""}${s.is_terminal?" · terminal":""}</span>
              ${!s.is_initial?`<button class="icon-btn wf-del-state" data-sid="${s.id}" title="Delete state">✕</button>`:""}
            </div>`).join("")}
        </div>
        <form id="add-state-form" style="margin-top:12px">
          <div style="display:flex;gap:8px;align-items:center">
            <input type="text" id="ns-name" placeholder="State name" class="select" style="flex:1">
            <input type="color" id="ns-color" value="#4D75FE" style="width:38px;height:38px;border-radius:8px;border:1px solid var(--line);padding:2px">
            <label style="font-size:13px;display:flex;align-items:center;gap:4px;white-space:nowrap">
              <input type="checkbox" id="ns-terminal"> terminal
            </label>
            <button class="btn btn-primary" type="submit" style="padding:8px 14px;font-size:13px">Add</button>
          </div>
        </form>
        <h4 style="margin-top:20px">Transitions</h4>
        <div id="wf-trans-list">
          ${wf.transitions.map(t => {
            const fs = wf.states.find(s=>s.id===t.from)||{name:t.from,color:"#888"};
            const ts = wf.states.find(s=>s.id===t.to)||{name:t.to,color:"#888"};
            return `
            <div class="wf-trans-row">
              <span class="wf-state-chip" style="background:${fs.color}20;color:${fs.color};font-size:12px">${esc(fs.name)}</span>
              <span style="font-size:13px;color:var(--muted)">→</span>
              <span class="wf-state-chip" style="background:${ts.color}20;color:${ts.color};font-size:12px">${esc(ts.name)}</span>
              <span style="font-size:12px;flex:1;color:var(--text)">${esc(t.label)}</span>
              ${t.requires_reason?`<span style="font-size:11px;color:var(--muted)">reason req.</span>`:""}
              <button class="icon-btn wf-del-trans" data-tid="${t.id}" title="Delete transition">✕</button>
            </div>`;
          }).join("")}
        </div>
        <form id="add-trans-form" style="margin-top:12px">
          <div style="display:grid;grid-template-columns:1fr auto 1fr;gap:8px;align-items:center;margin-bottom:8px">
            <select id="nt-from" class="select">
              ${wf.states.map(s=>`<option value="${s.id}">${esc(s.name)}</option>`).join("")}
            </select>
            <span style="font-size:18px;color:var(--muted)">→</span>
            <select id="nt-to" class="select">
              ${wf.states.map(s=>`<option value="${s.id}">${esc(s.name)}</option>`).join("")}
            </select>
          </div>
          <div style="display:flex;gap:8px;align-items:center">
            <input type="text" id="nt-label" placeholder="Transition label" class="select" style="flex:1">
            <label style="font-size:13px;display:flex;align-items:center;gap:4px;white-space:nowrap">
              <input type="checkbox" id="nt-reason"> reason req.
            </label>
            <button class="btn btn-primary" type="submit" style="padding:8px 14px;font-size:13px">Add</button>
          </div>
        </form>
      </div>
    </div>`;

  // Delete state
  el.querySelectorAll(".wf-del-state").forEach(btn => btn.addEventListener("click", async () => {
    if (!confirm(`Delete state "${btn.dataset.sid}"?`)) return;
    try { await api.delete(`/api/workflow/states/${btn.dataset.sid}`); renderWorkflowEditor(el); }
    catch(e) { toast(e.message, "error"); }
  }));
  // Delete transition
  el.querySelectorAll(".wf-del-trans").forEach(btn => btn.addEventListener("click", async () => {
    try { await api.delete("/api/workflow/transitions", {transition_id: btn.dataset.tid}); renderWorkflowEditor(el); }
    catch(e) { toast(e.message, "error"); }
  }));
  // Add state
  document.getElementById("add-state-form").addEventListener("submit", async e => {
    e.preventDefault();
    const name = document.getElementById("ns-name").value.trim();
    if (!name) return;
    try {
      await api.post("/api/workflow/states", {
        name, color: document.getElementById("ns-color").value,
        is_terminal: document.getElementById("ns-terminal").checked,
      });
      renderWorkflowEditor(el);
    } catch(err) { toast(err.message, "error"); }
  });
  // Add transition
  document.getElementById("add-trans-form").addEventListener("submit", async e => {
    e.preventDefault();
    const label = document.getElementById("nt-label").value.trim();
    if (!label) return;
    try {
      await api.post("/api/workflow/transitions", {
        from_state: document.getElementById("nt-from").value,
        to_state: document.getElementById("nt-to").value,
        label, requires_admin: true,
        requires_reason: document.getElementById("nt-reason").checked,
      });
      renderWorkflowEditor(el);
    } catch(err) { toast(err.message, "error"); }
  });
}

function renderWFDiagram(wf) {
  // SVG flow diagram of the workflow states and transitions
  const states = wf.states;
  const n = states.length;
  const W = 120, H = 44, GAP_X = 60, GAP_Y = 70;
  // Layout: arrange in rows of 3
  const cols = Math.min(n, 3);
  const rows = Math.ceil(n / cols);
  const svgW = cols * W + (cols - 1) * GAP_X + 40;
  const svgH = rows * H + (rows - 1) * GAP_Y + 40;
  const pos = {};
  states.forEach((s, i) => {
    const col = i % cols, row = Math.floor(i / cols);
    pos[s.id] = {
      x: 20 + col * (W + GAP_X),
      y: 20 + row * (H + GAP_Y),
    };
  });
  const stateRects = states.map(s => {
    const {x, y} = pos[s.id];
    return `<g>
      <rect x="${x}" y="${y}" width="${W}" height="${H}" rx="10"
        fill="${s.color}22" stroke="${s.color}" stroke-width="2"/>
      ${s.is_initial?`<polygon points="${x-10},${y+H/2} ${x-4},${y+H/2-6} ${x-4},${y+H/2+6}" fill="${s.color}"/>`:""}
      <text x="${x+W/2}" y="${y+H/2+5}" text-anchor="middle" font-size="13" font-weight="600" fill="${s.color}">${esc(s.name)}</text>
      ${s.is_terminal?`<circle cx="${x+W-8}" cy="${y+8}" r="5" fill="${s.color}"/>`:""}</g>`;
  }).join("");
  const arrows = wf.transitions.map(t => {
    const fp = pos[t.from], tp = pos[t.to];
    if (!fp || !tp) return "";
    const x1 = fp.x + W/2, y1 = fp.y + H;
    const x2 = tp.x + W/2, y2 = tp.y;
    const mx = (x1+x2)/2, my = (y1+y2)/2;
    const dx = x2-x1, dy = y2-y1;
    const mx2 = mx - dy*0.15, my2 = my + dx*0.15;
    return `<g>
      <path d="M${x1},${y1} Q${mx2},${my2} ${x2},${y2}" fill="none" stroke="#aaa" stroke-width="1.5" marker-end="url(#arr)"/>
      <text x="${mx2}" y="${my2}" text-anchor="middle" font-size="10" fill="var(--muted)">${esc(t.label)}</text></g>`;
  }).join("");
  return `<svg width="${svgW}" height="${svgH}" viewBox="0 0 ${svgW} ${svgH}" style="max-width:100%">
    <defs><marker id="arr" markerWidth="8" markerHeight="6" refX="6" refY="3" orient="auto">
      <path d="M0,0 L8,3 L0,6 Z" fill="#aaa"/></marker></defs>
    ${arrows}${stateRects}
  </svg>`;
}

// ---- Admin: Swag catalog management ----
async function renderSwagCatalog(el) {
  const {items} = await api.get("/api/swag");
  el.innerHTML = `
    <div class="card admin-card" style="max-width:700px">
      <h3 style="margin-top:0">Swag Catalog</h3>
      <div id="catalog-list">
        ${items.map(item => `
          <div class="weight-field" style="align-items:flex-start;gap:12px">
            <div>
              <div class="wf-label">${esc(item.name)}</div>
              <div class="wf-desc">${esc(item.description)}</div>
            </div>
            <div style="text-align:right;flex-shrink:0">
              <div class="points-badge" style="display:inline-block">${item.point_cost} pts</div>
              <div style="font-size:12px;color:var(--muted);margin-top:4px">${item.stock!=null?item.stock+" in stock":"unlimited"} · ${item.is_available?"available":"hidden"}</div>
            </div>
          </div>`).join("")}
      </div>
      <hr style="border:0;border-top:1px solid var(--line);margin:20px 0">
      <h4 style="margin:0 0 14px">Add swag item</h4>
      <form id="add-swag-form">
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
          <div class="field"><span>Name</span><input type="text" id="swag-name" class="select" required></div>
          <div class="field"><span>Points</span><input type="number" id="swag-cost" class="select" min="1" value="100" required></div>
        </div>
        <div class="field"><span>Description</span><textarea id="swag-desc" class="select" rows="2"></textarea></div>
        <div style="display:flex;gap:12px;align-items:center">
          <div class="field" style="flex:1"><span>Stock (blank = unlimited)</span><input type="number" id="swag-stock" class="select" min="0"></div>
          <label style="font-size:14px;display:flex;align-items:center;gap:6px;margin-top:4px">
            <input type="checkbox" id="swag-avail" checked> Available
          </label>
        </div>
        <div style="text-align:right;margin-top:8px">
          <button class="btn btn-primary" type="submit">Add item</button>
        </div>
      </form>
    </div>`;
  document.getElementById("add-swag-form").addEventListener("submit", async e => {
    e.preventDefault();
    const stockVal = document.getElementById("swag-stock").value;
    try {
      await api.post("/api/swag", {
        name: document.getElementById("swag-name").value,
        description: document.getElementById("swag-desc").value,
        point_cost: parseInt(document.getElementById("swag-cost").value, 10),
        stock: stockVal ? parseInt(stockVal, 10) : null,
        is_available: document.getElementById("swag-avail").checked,
      });
      toast("Item added", "success");
      renderSwagCatalog(el);
    } catch(err) { toast(err.message, "error"); }
  });
}

function wireProfileLinks(scope) {
  scope.querySelectorAll("[data-profile]").forEach(el =>
    el.addEventListener("click", () => go("profile", parseInt(el.dataset.profile, 10))));
}
function empty(emoji, msg) {
  return `<div class="empty"><span class="emoji">${emoji}</span>${esc(msg)}</div>`;
}

// --------------------------------------------------------------------------
// GitHub sync
// --------------------------------------------------------------------------
async function runSync(btn) {
  const orig = btn ? btn.textContent : null;
  if (btn) { btn.disabled = true; btn.textContent = "Syncing…"; }
  try {
    const res = await api.post("/api/github/sync");
    const s = res.summary;
    toast(`Synced: +${s.prs_added} PRs, +${s.issues_added} issues stored`, "success");
    await refreshMe();
    go(state.route, state.routeArg);
  } catch(e) { toast(e.message, "error"); }
  finally { if (btn) { btn.disabled = false; btn.textContent = orig; } }
}

// --------------------------------------------------------------------------
// Avatar menu
// --------------------------------------------------------------------------
$("#avatar-btn").addEventListener("click", e => {
  e.stopPropagation(); $("#user-menu").classList.toggle("hidden");
});
document.addEventListener("click", () => {
  $("#user-menu").classList.add("hidden");
  $("#notif-dropdown").classList.add("hidden");
});
$("#user-menu").addEventListener("click", async e => {
  const action = e.target.dataset.action;
  if (action === "profile") go("profile", state.me.id);
  if (action === "logout") { await api.post("/api/auth/logout"); location.reload(); }
  if (action === "sync") {
    if (!state.me.github_login) { toast("Log in with GitHub to sync activity.", "error"); return; }
    runSync(null);
  }
});

// --------------------------------------------------------------------------
// Notification bell
// --------------------------------------------------------------------------
$("#notif-btn").addEventListener("click", async e => {
  e.stopPropagation();
  const dd = $("#notif-dropdown");
  if (!dd.classList.contains("hidden")) { dd.classList.add("hidden"); return; }
  const notifs = await api.get("/api/notifications");
  dd.innerHTML = notifs.length
    ? notifs.slice(0, 20).map(n => `
        <div class="notif-item ${n.read?"":"notif-unread"}">
          <span>${n.message}</span>
          <span class="notif-time">${timeAgo(n.created_at)}</span>
        </div>`).join("")
    : `<div class="notif-item" style="color:var(--muted)">No notifications</div>`;
  dd.classList.remove("hidden");
  if (state.me.unread_notifications > 0) {
    await api.post("/api/notifications/read");
    state.me.unread_notifications = 0;
    renderTopbar();
  }
});

// --------------------------------------------------------------------------
// Give Kudos modal
// --------------------------------------------------------------------------
let selectedValue = null;

function openGive(prefill = {}) {
  const sel = $("#give-recipient");
  sel.innerHTML = `<option value="" disabled ${prefill.receiverId?"":"selected"}>Choose a teammate…</option>` +
    state.users.filter(u => u.id !== state.me.id).map(u =>
      `<option value="${u.id}" ${u.id===prefill.receiverId?"selected":""}>${esc(u.name)} — ${esc(u.title||"Employee")}</option>`
    ).join("");

  const chips = $("#value-chips");
  chips.innerHTML = state.config.core_values.map(v =>
    `<div class="vchip" data-value="${v.key}" title="${esc(v.desc)}"><div class="vc-emoji">${v.emoji}</div><div class="vc-label">${esc(v.label)}</div></div>`
  ).join("");
  selectedValue = null;
  chips.querySelectorAll(".vchip").forEach(c => c.addEventListener("click", () => {
    chips.querySelectorAll(".vchip").forEach(x=>x.classList.remove("active"));
    c.classList.add("active"); selectedValue = c.dataset.value;
  }));

  const bal = state.me.giving_balance;
  const max = Math.max(1, bal);
  const range = $("#points-range"), num = $("#points-number");
  range.max = max; num.max = max;
  range.value = Math.min(10, max); num.value = Math.min(10, max);
  $("#points-hint").textContent = `· ${bal} left this month`;
  $("#give-error").textContent = bal === 0 ? "You've used all your points this month." : "";
  $("#give-message").value = "";
  $("#give-artifact-url").value = prefill.artifactUrl || "";
  $("#give-artifact-label").value = prefill.artifactLabel || "";
  $("#give-modal").classList.remove("hidden");
}

$("#open-give").addEventListener("click", () => openGive());
$("#close-give").addEventListener("click", () => $("#give-modal").classList.add("hidden"));
$("#give-modal").addEventListener("click", e => { if (e.target.id==="give-modal") $("#give-modal").classList.add("hidden"); });
$("#points-range").addEventListener("input", e => $("#points-number").value = e.target.value);
$("#points-number").addEventListener("input", e => $("#points-range").value = e.target.value);

$("#give-form").addEventListener("submit", async e => {
  e.preventDefault();
  const err = $("#give-error"); err.textContent = "";
  if (!selectedValue) { err.textContent = "Pick a core value."; return; }
  const body = {
    receiver_id: parseInt($("#give-recipient").value, 10),
    points: parseInt($("#points-number").value, 10),
    value_key: selectedValue,
    message: $("#give-message").value.trim(),
    artifact_url: $("#give-artifact-url").value.trim(),
    artifact_label: $("#give-artifact-label").value.trim(),
  };
  if (!body.receiver_id) { err.textContent = "Choose a teammate."; return; }
  if (!body.message) { err.textContent = "Add a message."; return; }
  const submit = $("#give-submit"); submit.disabled = true;
  try {
    await api.post("/api/kudos", body);
    $("#give-modal").classList.add("hidden");
    await refreshMe();
    fireConfetti();
    toast("Kudos sent! 🎉", "success");
    go("feed");
  } catch(e2) { err.textContent = e2.message; }
  finally { submit.disabled = false; }
});

// --------------------------------------------------------------------------
// Redeem swag modal
// --------------------------------------------------------------------------
function openRedeemModal(itemId, itemName, cost) {
  const html = `
    <div class="modal-backdrop" id="redeem-modal">
      <div class="modal">
        <div class="modal-head"><h2>Redeem Swag</h2><button class="icon-btn" id="close-redeem">✕</button></div>
        <div style="padding:22px 26px">
          <p>You're about to spend <strong>${cost} pts</strong> on <strong>${esc(itemName)}</strong>.</p>
          <p style="color:var(--muted);font-size:14px">Your balance after this order: <strong>${state.me.spendable_points - cost} pts</strong>. Your manager will review and approve the order.</p>
          <div class="field"><span>Notes for your manager (optional)</span>
            <textarea id="redeem-notes" class="select" rows="2" placeholder="e.g. Size L, ship to home address"></textarea></div>
          <div class="modal-foot">
            <span class="form-error" id="redeem-error"></span>
            <button class="btn btn-primary" id="redeem-confirm">Confirm order</button>
          </div>
        </div>
      </div>
    </div>`;
  document.body.insertAdjacentHTML("beforeend", html);
  const modal = document.getElementById("redeem-modal");
  document.getElementById("close-redeem").addEventListener("click", () => modal.remove());
  modal.addEventListener("click", e => { if (e.target === modal) modal.remove(); });
  document.getElementById("redeem-confirm").addEventListener("click", async () => {
    const btn = document.getElementById("redeem-confirm"); btn.disabled = true;
    try {
      await api.post(`/api/swag/${itemId}/order`, {notes: document.getElementById("redeem-notes").value});
      modal.remove();
      await refreshMe();
      toast(`Order placed for ${itemName}! Awaiting approval.`, "success");
      go("rewards", "orders");
    } catch(e) {
      document.getElementById("redeem-error").textContent = e.message;
      btn.disabled = false;
    }
  });
}

// --------------------------------------------------------------------------
// Confetti
// --------------------------------------------------------------------------
function fireConfetti() {
  const canvas = $("#confetti"); canvas.classList.remove("hidden");
  const ctx = canvas.getContext("2d");
  canvas.width = innerWidth; canvas.height = innerHeight;
  const colors = ["#4D75FE","#FAA944","#2E9E6B","#FF8A69","#7C5CFF","#000F3A"];
  const pieces = Array.from({length: 140}, () => ({
    x: innerWidth/2, y: innerHeight/3,
    vx: (Math.random()-.5)*16, vy: Math.random()*-16-4,
    size: Math.random()*8+4, color: colors[Math.floor(Math.random()*colors.length)],
    rot: Math.random()*360, vr: (Math.random()-.5)*20,
  }));
  let f = 0;
  (function tick() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    pieces.forEach(p => {
      p.vy += .5; p.x += p.vx; p.y += p.vy; p.rot += p.vr;
      ctx.save(); ctx.translate(p.x,p.y); ctx.rotate(p.rot*Math.PI/180);
      ctx.fillStyle = p.color; ctx.fillRect(-p.size/2,-p.size/2, p.size, p.size*.6);
      ctx.restore();
    });
    if (++f < 120) requestAnimationFrame(tick);
    else { ctx.clearRect(0,0,canvas.width,canvas.height); canvas.classList.add("hidden"); }
  })();
}

// --------------------------------------------------------------------------
boot().catch(e => { document.body.innerHTML = `<div class="empty">Failed to load: ${esc(e.message)}</div>`; });
