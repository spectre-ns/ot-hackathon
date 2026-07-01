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
      `<option value="${u.id}">${esc(u.name)} — ${esc(u.title||"Employee")}${u.role && u.role !== "user" ? " (" + u.role + ")" : ""}</option>`
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
  const { route, arg } = urlToRoute(location.pathname);
  history.replaceState({ route, arg }, "", location.pathname);
  go(route, arg, false);
}
async function refreshMe() {
  state.me = await api.get("/api/me"); renderTopbar();
}
function renderTopbar() {
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
function routeToUrl(route, arg) {
  if (!route || route === "feed") return "/";
  return arg != null ? `/${route}/${arg}` : `/${route}`;
}
function urlToRoute(pathname) {
  const parts = pathname.replace(/^\//, "").split("/").filter(Boolean);
  if (!parts.length || parts[0] === "feed") return { route: "feed", arg: null };
  const raw = parts[1] ?? null;
  const arg = raw === null ? null : (!isNaN(raw) && raw !== "" ? Number(raw) : raw);
  return { route: parts[0], arg };
}
function go(route, arg = null, push = true) {
  state.route = route; state.routeArg = arg;
  $$(".nav-link").forEach(l => l.classList.toggle("active", l.dataset.route === route));
  if (push) history.pushState({ route, arg }, "", routeToUrl(route, arg));
  const view = $("#view");
  view.innerHTML = '<div class="spinner"></div>';
  (ROUTES[route] || ROUTES.feed)(view, arg).catch(e => {
    view.innerHTML = `<div class="empty">${esc(e.message)}</div>`;
  });
}
function navigateTo(link) {
  if (!link) return;
  const { route, arg } = urlToRoute(link);
  go(route, arg);
}
window.addEventListener("popstate", e => {
  if (!state.me) return;
  const { route, arg } = e.state || urlToRoute(location.pathname);
  go(route, arg, false);
});
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
        ${isMe ? `<div><div class="ps-num" id="giving-balance">${state.me.giving_balance}</div><div class="ps-label">pts to give</div></div>` : ""}
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
    <div id="tab-github" class="hidden" style="display:flex;flex-direction:column;gap:10px">
      ${p.github_contributions.map(c => `
        <div class="card act-card">
          <div class="act-top">
            <span class="contrib-kind ${c.kind}">${c.kind==="pr"?"PR":"Issue"}</span>
            <div class="act-body">
              <div class="act-title">${c.url?`<a href="${esc(c.url)}" target="_blank" rel="noopener" style="color:var(--blue)">${esc(c.title)}</a>`:esc(c.title)}</div>
              <div class="act-meta">${esc(c.repo)} #${c.number} · ${timeAgo(c.happened_at)}</div>
            </div>
            <span class="contrib-pts act-pts">+${c.points}</span>
          </div>
          <div class="act-foot">
            <button class="btn btn-ghost award-artifact-btn" style="font-size:12px;padding:6px 12px"
              data-url="${esc(c.url)}" data-label="${esc(c.kind==="pr"?"PR":"Issue")+" #"+c.number+": "+esc(c.title)}"
              data-receiver="${p.user.id}">Award kudos</button>
          </div>
        </div>`).join("") || empty("🐙","No synced GitHub activity.")}
    </div>
    <div id="tab-crm" class="hidden" style="display:flex;flex-direction:column;gap:10px">
      ${p.crm_contributions.map(c => {
        const et = crmEtMap[c.event_type]||{emoji:"📋",label:c.event_type};
        return `
        <div class="card act-card">
          <div class="act-top">
            <span class="contrib-kind" style="background:#eef1ff;color:var(--blue)">${et.emoji}</span>
            <div class="act-body">
              <div class="act-title">${c.artifact_url?`<a href="${esc(c.artifact_url)}" target="_blank" rel="noopener" style="color:var(--blue)">${esc(c.title)}</a>`:esc(c.title)}</div>
              <div class="act-meta">${esc(et.label)} · ${esc(c.company||"")}${c.company?" · ":""}${timeAgo(c.happened_at)}</div>
            </div>
            <span class="contrib-pts act-pts">+${c.points}</span>
          </div>
          <div class="act-foot">
            <button class="btn btn-ghost award-artifact-btn" style="font-size:12px;padding:6px 12px"
              data-url="${esc(c.artifact_url||"")}"
              data-label="${esc(et.label+": "+c.title)}"
              data-receiver="${p.user.id}">Award kudos</button>
          </div>
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

// ---- Activity feed (all GitHub + CRM contributions) ----
ROUTES.activity = async (view, arg) => {
  const tab = arg || "all";
  view.innerHTML = `<div class="page-head"><h2>Activity</h2></div><div class="spinner"></div>`;
  const items = await api.get("/api/activity");
  const github = items.filter(x => x.source === "github");
  const crm = items.filter(x => x.source === "crm");
  view.innerHTML = `
    <div class="page-head">
      <h2>Activity</h2>
      <p style="color:var(--muted);font-size:14px;margin:0">Contributions from GitHub and CRM — click <strong>Award kudos</strong> to recognize teammates.</p>
    </div>
    <div class="tabs">
      <div class="tab ${tab==="all"?"active":""}" data-atab2="all">All (${items.length})</div>
      <div class="tab ${tab==="github"?"active":""}" data-atab2="github">GitHub (${github.length})</div>
      <div class="tab ${tab==="crm"?"active":""}" data-atab2="crm">CRM (${crm.length})</div>
    </div>
    <div id="act-all" class="${tab!=="all"?"hidden":""}">
      ${items.length ? items.map(c => activityCard(c)).join("") : empty("📭","No activity yet.")}
    </div>
    <div id="act-github" class="${tab!=="github"?"hidden":""}">
      ${github.length ? github.map(c => activityCard(c)).join("") : empty("🐙","No GitHub activity synced.")}
    </div>
    <div id="act-crm" class="${tab!=="crm"?"hidden":""}">
      ${crm.length ? crm.map(c => activityCard(c)).join("") : empty("📋","No CRM events recorded.")}
    </div>`;
  view.querySelectorAll("[data-atab2]").forEach(t => t.addEventListener("click", () => {
    view.querySelectorAll("[data-atab2]").forEach(x=>x.classList.remove("active")); t.classList.add("active");
    ["all","github","crm"].forEach(n => document.getElementById(`act-${n}`).classList.toggle("hidden", t.dataset.atab2 !== n));
  }));
  view.querySelectorAll(".award-artifact-btn").forEach(btn => {
    btn.addEventListener("click", () => openGive({
      receiverId: parseInt(btn.dataset.receiver, 10),
      artifactUrl: btn.dataset.url,
      artifactLabel: btn.dataset.label,
    }));
  });
};

function activityCard(c) {
  const isGH = c.source === "github";
  const user = c.user;
  const kindBadge = isGH
    ? `<span class="contrib-kind ${c.kind}">${c.kind==="pr"?"PR":"Issue"}</span>`
    : `<span class="contrib-kind" style="background:#eef1ff;color:var(--blue)">${c.event_emoji||"📋"}</span>`;
  const titleHtml = (c.url||c.artifact_url)
    ? `<a href="${esc(c.url||c.artifact_url)}" target="_blank" rel="noopener" style="color:var(--blue)">${esc(c.title)}</a>`
    : esc(c.title||"—");
  const meta = isGH
    ? `${esc(c.repo)} #${c.number} · ${timeAgo(c.happened_at)}`
    : `${esc(c.event_label||c.event_type)} · ${esc(c.company||"")}${c.company?" · ":""}${timeAgo(c.happened_at)}`;
  const artifactUrl = c.url || c.artifact_url || "";
  const artifactLabel = isGH
    ? `${c.kind==="pr"?"PR":"Issue"} #${c.number}: ${c.title}`
    : `${c.event_label||c.event_type}: ${c.title}`;
  return `
    <div class="card act-card">
      <div class="act-top">
        ${user ? `<div class="act-user" onclick="go('profile',${user.id})" style="cursor:pointer">${avatarHTML(user,34)}<span class="act-name">${esc(user.name)}</span></div>` : ""}
        ${kindBadge}
        <div class="act-body">
          <div class="act-title">${titleHtml}</div>
          <div class="act-meta">${meta}</div>
        </div>
        <span class="contrib-pts act-pts">+${c.points}</span>
      </div>
      ${user ? `<div class="act-foot">
        <button class="btn btn-ghost award-artifact-btn" style="font-size:12px;padding:6px 12px"
          data-receiver="${user.id}"
          data-url="${esc(artifactUrl)}"
          data-label="${esc(artifactLabel)}">Award kudos</button>
      </div>` : ""}
    </div>`;
}

// ---- Rewards (Swag catalog) ----
ROUTES.rewards = async (view, arg) => {
  const tab = arg || "catalog";
  const [catalog, myOrders, wf] = await Promise.all([
    api.get("/api/swag"),
    api.get("/api/swag/orders"),
    api.get("/api/workflow"),
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
      ${myOrders.length ? myOrders.map(o => orderCard(o, wf.states)).join("") : empty("📦","You haven't placed any orders yet.")}
    </div>`;
  view.querySelectorAll("[data-rtab]").forEach(t => t.addEventListener("click", () => go("rewards", t.dataset.rtab)));
  view.querySelectorAll(".redeem-btn").forEach(btn => {
    btn.addEventListener("click", () => openRedeemModal(
      parseInt(btn.dataset.itemId, 10), btn.dataset.itemName, parseInt(btn.dataset.cost, 10)));
  });
};

const SWAG_EMOJI_MAP = [
  [["shirt","tee"], "👕", "#dce6ff"],
  [["hoodie","sweatshirt"], "🧥", "#d0d4f0"],
  [["headphone","earphone","audio"], "🎧", "#ede8ff"],
  [["gift card","amazon","voucher"], "🎁", "#fff8e0"],
  [["desk","mat","ergonomic"], "🖥️", "#e8f5e9"],
  [["bottle","water","hydro"], "💧", "#e0f4ff"],
  [["backpack","bag"], "🎒", "#ffecd4"],
  [["pto","day off","vacation","time off"], "🏖️", "#e0f4ff"],
  [["charit","donat"], "❤️", "#ffe8ea"],
];
function swagEmoji(name) {
  const n = name.toLowerCase();
  for (const [keys, emoji] of SWAG_EMOJI_MAP) if (keys.some(k => n.includes(k))) return emoji;
  return "🎁";
}
function swagBg(name) {
  const n = name.toLowerCase();
  for (const [keys, , bg] of SWAG_EMOJI_MAP) if (keys.some(k => n.includes(k))) return bg;
  return "#f0f0f0";
}

function swagCard(item, spendable) {
  const canAfford = spendable >= item.point_cost;
  const stockLabel = item.stock != null ? ` · ${item.stock} left` : "";
  const thumb = item.image_url
    ? `<div class="swag-thumb"><img src="${esc(item.image_url)}" alt="${esc(item.name)}" loading="lazy"></div>`
    : `<div class="swag-thumb swag-thumb-emoji" style="background:${swagBg(item.name)}">${swagEmoji(item.name)}</div>`;
  return `
    <div class="card swag-card${!canAfford?" swag-unaffordable":""}">
      ${thumb}
      <div class="swag-body">
        <div class="swag-name">${esc(item.name)}</div>
        <div class="swag-desc">${esc(item.description)}</div>
        <div class="swag-footer">
          <span class="points-badge">${item.point_cost} pts${stockLabel}</span>
          ${canAfford
            ? `<button class="btn btn-primary redeem-btn" style="font-size:13px;padding:8px 14px"
                data-item-id="${item.id}" data-item-name="${esc(item.name)}" data-cost="${item.point_cost}">Redeem</button>`
            : `<span class="swag-locked">Need ${item.point_cost - spendable} more pts</span>`}
        </div>
      </div>
    </div>`;
}

function orderStepper(o, wfStates) {
  if (!wfStates || !wfStates.length) return "";
  const log = o.transition_log || [];
  const visited = new Set([...log.map(t => t.from), ...log.map(t => t.to)]);
  const current = o.current_state;
  visited.add(current);
  const parts = [];
  wfStates.forEach((s, i) => {
    const isActive = s.id === current;
    const isDone = visited.has(s.id) && !isActive;
    const cls = `os-step${isActive?" os-active":isDone?" os-done":" os-future"}`;
    const col = (isActive || isDone) ? (s.color || "#888") : "#ddd";
    parts.push(`<div class="${cls}"><div class="os-dot" style="background:${col};border-color:${col}"></div><div class="os-label">${esc(s.name)}</div></div>`);
    if (i < wfStates.length - 1) {
      parts.push(`<div class="os-connector${isDone?" os-line-done":""}"></div>`);
    }
  });
  return `<div class="os-stepper">${parts.join("")}</div>`;
}

function orderCard(o, wfStates) {
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
      ${orderStepper(o, wfStates)}
    </div>`;
}

// ---- Admin ----
ROUTES.admin = async (view, arg) => {
  if (!state.me.is_admin) { view.innerHTML = empty("🔒","Admins only."); return; }
  const subTab = arg || "settings";
  const isSuperAdmin = state.me.role === "superadmin";
  const [settings, pendingOrders, allOrders, wf, allUsers] = await Promise.all([
    api.get("/api/settings"),
    api.get("/api/swag/orders/pending"),
    api.get("/api/swag/orders/all"),
    api.get("/api/workflow"),
    isSuperAdmin ? api.get("/api/users") : Promise.resolve([]),
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
      ${isSuperAdmin ? `<div class="tab ${subTab==="users"?"active":""}" data-atab="users">Users</div>` : ""}
    </div>
    <div id="atab-settings" class="${subTab!=="settings"?"hidden":""}"></div>
    <div id="atab-crm" class="${subTab!=="crm"?"hidden":""}"></div>
    <div id="atab-orders" class="${subTab!=="orders"?"hidden":""}"></div>
    <div id="atab-workflow" class="${subTab!=="workflow"?"hidden":""}"></div>
    <div id="atab-catalog" class="${subTab!=="catalog"?"hidden":""}"></div>
    ${isSuperAdmin ? `<div id="atab-users" class="${subTab!=="users"?"hidden":""}"></div>` : ""}`;
  view.querySelectorAll("[data-atab]").forEach(t => t.addEventListener("click", () => go("admin", t.dataset.atab)));
  renderAdminSettings(document.getElementById("atab-settings"), settings);
  renderCRMSimulator(document.getElementById("atab-crm"));
  renderAdminOrders(document.getElementById("atab-orders"), pendingOrders, allOrders, wf.states);
  renderWorkflowEditor(document.getElementById("atab-workflow"));
  renderSwagCatalog(document.getElementById("atab-catalog"));
  if (isSuperAdmin) renderUserManagement(document.getElementById("atab-users"), allUsers);
};

// ---- Notifications stream ----
ROUTES.notifications = async (view) => {
  const notifs = await api.get("/api/notifications");
  if (state.me.unread_notifications > 0) {
    await api.post("/api/notifications/read");
    state.me.unread_notifications = 0;
    renderTopbar();
  }
  const kindIcon = { warning: "⚠️", success: "✅", info: "ℹ️" };
  view.innerHTML = `
    <div class="page-head"><h2>Notifications</h2></div>
    <div class="notif-stream">
      ${notifs.length
        ? notifs.map(n => `
          <div class="card notif-stream-item${n.read ? "" : " notif-unread"}" data-link="${esc(n.link || "")}">
            <div class="notif-stream-body">
              <span class="notif-stream-icon">${kindIcon[n.kind] || "🔔"}</span>
              <span class="notif-stream-msg">${esc(n.message)}</span>
            </div>
            <div class="notif-time">${timeAgo(n.created_at)}</div>
          </div>`).join("")
        : empty("🔔", "You're all caught up!")}
    </div>`;
  view.querySelectorAll(".notif-stream-item[data-link]").forEach(el => {
    const link = el.dataset.link;
    if (link) el.addEventListener("click", () => navigateTo(link));
  });
};

// ---- Admin: Settings ----
function renderAdminSettings(el, s) {
  el.innerHTML = `
    <div class="card admin-card">
      <form id="settings-form">
        <div class="admin-group-title">Point weights &amp; allowances</div>
        <div class="weight-field">
          <div><div class="wf-label">Monthly giving allowance</div><div class="wf-desc">Points each employee can give per month</div></div>
          <input type="number" id="monthly_allowance" min="0" max="100000" value="${s.monthly_allowance}" style="width:96px">
        </div>
        <div class="admin-group-title">GitHub activity</div>
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
        <div class="admin-group-title">CRM activity</div>
        <div class="weight-field">
          <div>
            <div class="wf-label">CRM auto-accumulation</div>
            <div class="wf-desc">When ON: CRM webhook events auto-award points. When OFF: CRM events are informational only; points come from manual kudos.</div>
          </div>
          <label class="toggle-label">
            <input type="checkbox" id="crm_accumulation_enabled" ${s.crm_accumulation_enabled!==false?"checked":""}>
            <span class="toggle-track"></span>
          </label>
        </div>
        <div class="admin-group-title">CRM event weights</div>
        ${(state.config.crm_event_types||[]).map(et => `
          <div class="weight-field">
            <div><div class="wf-label">${esc(et.label)}</div><div class="wf-desc">${esc(et.desc)}</div></div>
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
        crm_accumulation_enabled: document.getElementById("crm_accumulation_enabled").checked,
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
        <div class="field"><span>Artifact URL (optional)</span>
          <input type="url" id="crm-artifact" placeholder="https://crm.example.com/opportunities/OPP-8821" class="select" value=""></div>
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
        artifact_url: document.getElementById("crm-artifact").value,
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
function renderAdminOrders(el, pendingOrders, allOrders, wfStates) {
  el.innerHTML = `
    <div class="admin-orders-wrap">
      <div class="tabs" style="margin-bottom:16px">
        <div class="tab active" data-otab="pending">Pending (${pendingOrders.length})</div>
        <div class="tab" data-otab="all">All orders (${allOrders.length})</div>
      </div>
      <div id="otab-pending">${renderOrderList(pendingOrders, true, wfStates)}</div>
      <div id="otab-all" class="hidden">${renderOrderList(allOrders, true, wfStates)}</div>
    </div>`;
  el.querySelectorAll("[data-otab]").forEach(t => t.addEventListener("click", () => {
    el.querySelectorAll("[data-otab]").forEach(x=>x.classList.remove("active")); t.classList.add("active");
    document.getElementById("otab-pending").classList.toggle("hidden", t.dataset.otab!=="pending");
    document.getElementById("otab-all").classList.toggle("hidden", t.dataset.otab!=="all");
  }));
  wireOrderActions(el);
}

function renderOrderList(orders, isAdmin = false, wfStates = []) {
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
        ${orderStepper(o, wfStates)}
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
        <div id="wf-canvas"></div>
        <div class="wf-diagram-hint" id="wf-hint">Click a state to select it, then click another to draw a transition · Hover to delete</div>
      </div>
      <div class="wf-panel">
        <h4 style="margin:0 0 12px">Add State</h4>
        <form id="add-state-form" style="margin-bottom:16px">
          <div style="display:flex;gap:8px;align-items:center;margin-bottom:8px">
            <input type="text" id="ns-name" placeholder="State name" class="select" style="flex:1">
            <input type="color" id="ns-color" value="#4D75FE" style="width:38px;height:38px;border-radius:8px;border:1px solid var(--line);padding:2px;cursor:pointer">
          </div>
          <div style="display:flex;justify-content:space-between;align-items:center">
            <label style="font-size:13px;display:flex;align-items:center;gap:6px;cursor:pointer">
              <input type="checkbox" id="ns-terminal"> terminal state
            </label>
            <button class="btn btn-primary" type="submit" style="padding:8px 16px;font-size:13px">Add state</button>
          </div>
        </form>
        <hr style="border:0;border-top:1px solid var(--line);margin:0 0 14px">
        <h4 style="margin:0 0 10px">States</h4>
        <div id="wf-states-list">
          ${wf.states.map(s => `
            <div class="wf-state-row" style="border-left:3px solid ${s.color}">
              <span class="wf-state-chip" style="background:${s.color}20;color:${s.color}">${esc(s.name)}</span>
              <span style="font-size:11px;color:var(--muted);margin-left:auto">${s.is_initial?"initial":""}${s.is_terminal?" terminal":""}</span>
            </div>`).join("")}
        </div>
        <hr style="border:0;border-top:1px solid var(--line);margin:14px 0">
        <h4 style="margin:0 0 10px">Transitions</h4>
        <div id="wf-trans-list" style="font-size:13px;color:var(--muted)">
          ${wf.transitions.map(t => {
            const fs = wf.states.find(s=>s.id===t.from)||{name:t.from,color:"#888"};
            const ts2 = wf.states.find(s=>s.id===t.to)||{name:t.to,color:"#888"};
            return `<div style="padding:5px 0;border-bottom:1px solid var(--line);display:flex;align-items:center;gap:6px">
              <span style="color:${fs.color};font-weight:600">${esc(fs.name)}</span>
              <span>→</span>
              <span style="color:${ts2.color};font-weight:600">${esc(ts2.name)}</span>
              <span style="flex:1;color:var(--muted);font-size:12px"> (${esc(t.label)})</span>
            </div>`;
          }).join("") || '<div style="color:var(--muted);font-size:13px">No transitions yet.</div>'}
        </div>
      </div>
    </div>`;

  // Mount interactive SVG diagram
  const canvas = document.getElementById("wf-canvas");
  const hintEl = document.getElementById("wf-hint");
  canvas.appendChild(buildWFDiagram(wf, {
    onDeleteState: async id => {
      try { await api.delete(`/api/workflow/states/${id}`); renderWorkflowEditor(el); }
      catch(e) { toast(e.message, "error"); }
    },
    onDeleteTransition: async id => {
      try { await api.delete("/api/workflow/transitions", {transition_id: id}); renderWorkflowEditor(el); }
      catch(e) { toast(e.message, "error"); }
    },
    onCreateTransition: async (fromId, toId, label, requiresReason) => {
      try {
        await api.post("/api/workflow/transitions", {
          from_state: fromId, to_state: toId, label,
          requires_admin: true, requires_reason: requiresReason,
        });
        renderWorkflowEditor(el);
      } catch(e) { toast(e.message, "error"); }
    },
    onHint: text => { hintEl.textContent = text; },
  }));

  // Add state form
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
}

function showTransitionDialog(fromName, toName, onConfirm, onCancel) {
  const overlay = document.createElement("div");
  overlay.className = "modal-overlay";
  overlay.innerHTML = `
    <div class="modal-card">
      <div style="font-size:13px;color:var(--muted);margin-bottom:4px">${esc(fromName)} → ${esc(toName)}</div>
      <h3 style="margin:0 0 20px;color:var(--navy)">New Transition</h3>
      <div class="field" style="margin-bottom:16px">
        <span>Label</span>
        <input type="text" id="wftd-label" class="select" placeholder="e.g. Approve, Reject…">
      </div>
      <label class="toggle-label" style="gap:10px">
        <input type="checkbox" id="wftd-reason">
        <span class="toggle-track"></span>
        <span style="font-size:14px">Requires a reason</span>
      </label>
      <div style="display:flex;justify-content:flex-end;gap:10px;margin-top:24px">
        <button class="btn btn-ghost" id="wftd-cancel">Cancel</button>
        <button class="btn btn-primary" id="wftd-create">Create</button>
      </div>
    </div>`;
  document.body.appendChild(overlay);
  const input = overlay.querySelector("#wftd-label");
  setTimeout(() => input.focus(), 50);

  const dismiss = cb => { overlay.remove(); cb(); };
  overlay.querySelector("#wftd-cancel").addEventListener("click", () => dismiss(onCancel));
  overlay.addEventListener("click", e => { if (e.target === overlay) dismiss(onCancel); });
  overlay.querySelector("#wftd-create").addEventListener("click", () => {
    const label = input.value.trim();
    if (!label) { input.focus(); return; }
    dismiss(() => onConfirm(label, overlay.querySelector("#wftd-reason").checked));
  });
  input.addEventListener("keydown", e => {
    if (e.key === "Enter") overlay.querySelector("#wftd-create").click();
    if (e.key === "Escape") overlay.querySelector("#wftd-cancel").click();
  });
}

// Builds and returns an interactive SVG workflow diagram DOM element.
// Interaction model:
//   • Hover a state  → delete button (×) appears at top-right corner
//   • Click a state  → selects it (blue ring); hint updates
//   • Click another  → opens dialog for transition label → creates transition
//   • Click bg       → deselects
//   • Hover a transition arrow → label highlights red, × delete button appears
function buildWFDiagram(wf, {onDeleteState, onDeleteTransition, onCreateTransition, onHint}) {
  const NS = "http://www.w3.org/2000/svg";
  const states = wf.states, transitions = wf.transitions;
  const W = 136, H = 50, GX = 90, GY = 92;
  const cols = Math.min(Math.max(states.length, 1), 3);
  const rows = Math.ceil(states.length / cols);
  const SVG_W = cols * W + (cols - 1) * GX + 48;
  const SVG_H = rows * H + (rows - 1) * GY + 56;

  // Compute grid positions
  const pos = {};
  states.forEach((s, i) => {
    pos[s.id] = {x: 24 + (i % cols) * (W + GX), y: 20 + Math.floor(i / cols) * (H + GY)};
  });

  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("width", SVG_W); svg.setAttribute("height", SVG_H);
  svg.setAttribute("viewBox", `0 0 ${SVG_W} ${SVG_H}`);
  svg.style.cssText = "max-width:100%;cursor:default;display:block;overflow:visible";

  // Arrow marker defs
  const defs = document.createElementNS(NS, "defs");
  ["wfarr","wfarr-red"].forEach((id, ri) => {
    const m = document.createElementNS(NS, "marker");
    m.setAttribute("id", id); m.setAttribute("markerWidth","8");
    m.setAttribute("markerHeight","6"); m.setAttribute("refX","6");
    m.setAttribute("refY","3"); m.setAttribute("orient","auto");
    const p = document.createElementNS(NS, "path");
    p.setAttribute("d","M0,0 L8,3 L0,6 Z");
    p.setAttribute("fill", ri===0?"#ccc":"#d6502f");
    m.appendChild(p); defs.appendChild(m);
  });
  svg.appendChild(defs);

  // Layers: transitions behind states
  const tLayer = document.createElementNS(NS, "g");
  const sLayer = document.createElementNS(NS, "g");
  svg.appendChild(tLayer); svg.appendChild(sLayer);

  let selectedId = null;

  function hint(text) { if (onHint) onHint(text); }
  function deselect() {
    selectedId = null;
    svg.style.cursor = "default";
    sLayer.querySelectorAll(".sel-ring").forEach(r => r.setAttribute("display","none"));
    hint("Click a state to select it, then click another to draw a transition · Hover to delete");
  }

  // ---- Draw transitions ----
  function drawTransitions() {
    while (tLayer.firstChild) tLayer.removeChild(tLayer.lastChild);
    transitions.forEach(t => {
      const fp = pos[t.from], tp = pos[t.to];
      if (!fp || !tp) return;

      // Compute bezier path from bottom-centre of `from` to top-centre of `to`
      let d, lx, ly;
      if (t.from === t.to) {
        // Self-loop
        const cx = fp.x + W, cy = fp.y + H / 2;
        d = `M${fp.x+W-4},${fp.y+H/2-8} C${cx+48},${cy-40} ${cx+48},${cy+40} ${fp.x+W-4},${fp.y+H/2+8}`;
        lx = cx + 54; ly = cy;
      } else {
        const ox = fp.x + W/2, oy = fp.y + H;
        const ix = tp.x + W/2, iy = tp.y;
        const mx = (ox+ix)/2, my = (oy+iy)/2;
        const dxn = ix-ox, dyn = iy-oy;
        const len = Math.sqrt(dxn*dxn+dyn*dyn)||1;
        const bend = Math.min(len*0.28, 55);
        const cx = mx - (dyn/len)*bend, cy = my + (dxn/len)*bend;
        d = `M${ox},${oy} Q${cx},${cy} ${ix},${iy}`;
        lx = (ox + 2*cx + ix)/4; ly = (oy + 2*cy + iy)/4;
      }

      const g = document.createElementNS(NS, "g");
      g.style.cursor = "pointer";

      const path = document.createElementNS(NS, "path");
      path.setAttribute("d",d); path.setAttribute("fill","none");
      path.setAttribute("stroke","#ccc"); path.setAttribute("stroke-width","2");
      path.setAttribute("marker-end","url(#wfarr)");

      // Wide transparent hit-area
      const hit = path.cloneNode();
      hit.setAttribute("stroke","transparent"); hit.setAttribute("stroke-width","14");
      hit.removeAttribute("marker-end");

      // Label background + text
      const tw = Math.max(t.label.length * 6.8 + 16, 40);
      const lbg = document.createElementNS(NS, "rect");
      lbg.setAttribute("x",lx-tw/2); lbg.setAttribute("y",ly-9);
      lbg.setAttribute("width",tw); lbg.setAttribute("height",17);
      lbg.setAttribute("rx","5"); lbg.setAttribute("fill","#fff");
      lbg.setAttribute("stroke","#e5e5e5");
      const ltxt = document.createElementNS(NS, "text");
      ltxt.setAttribute("x",lx); ltxt.setAttribute("y",ly+4);
      ltxt.setAttribute("text-anchor","middle"); ltxt.setAttribute("font-size","11");
      ltxt.setAttribute("fill","#888"); ltxt.setAttribute("pointer-events","none");
      ltxt.textContent = t.label;

      // Delete × circle (hidden by default)
      const delG = document.createElementNS(NS, "g");
      delG.setAttribute("display","none"); delG.style.cursor = "pointer";
      const dc = document.createElementNS(NS, "circle");
      dc.setAttribute("cx", lx+tw/2+10); dc.setAttribute("cy", ly-8);
      dc.setAttribute("r","9"); dc.setAttribute("fill","#d6502f");
      const dt = document.createElementNS(NS, "text");
      dt.setAttribute("x", lx+tw/2+10); dt.setAttribute("y", ly-3);
      dt.setAttribute("text-anchor","middle"); dt.setAttribute("font-size","13");
      dt.setAttribute("fill","#fff"); dt.setAttribute("font-weight","bold");
      dt.setAttribute("pointer-events","none"); dt.textContent="×";
      delG.appendChild(dc); delG.appendChild(dt);
      delG.addEventListener("click", e => {
        e.stopPropagation();
        if (confirm(`Delete transition "${t.label}"?`)) onDeleteTransition(t.id);
      });

      g.appendChild(path); g.appendChild(hit); g.appendChild(lbg); g.appendChild(ltxt); g.appendChild(delG);
      g.addEventListener("mouseenter", () => {
        path.setAttribute("stroke","#d6502f"); path.setAttribute("stroke-width","2.5");
        path.setAttribute("marker-end","url(#wfarr-red)");
        ltxt.setAttribute("fill","#d6502f"); delG.setAttribute("display","");
      });
      g.addEventListener("mouseleave", () => {
        path.setAttribute("stroke","#ccc"); path.setAttribute("stroke-width","2");
        path.setAttribute("marker-end","url(#wfarr)");
        ltxt.setAttribute("fill","#888"); delG.setAttribute("display","none");
      });
      tLayer.appendChild(g);
    });
  }

  // ---- Draw states ----
  states.forEach(s => {
    const p = pos[s.id];
    const g = document.createElementNS(NS, "g");
    g.style.cursor = "pointer";

    // Initial-state indicator triangle
    if (s.is_initial) {
      const tri = document.createElementNS(NS, "polygon");
      tri.setAttribute("points",`${p.x-15},${p.y+H/2} ${p.x-4},${p.y+H/2-8} ${p.x-4},${p.y+H/2+8}`);
      tri.setAttribute("fill",s.color); tri.setAttribute("pointer-events","none");
      g.appendChild(tri);
    }

    // Main rectangle
    const rect = document.createElementNS(NS, "rect");
    rect.setAttribute("x",p.x); rect.setAttribute("y",p.y);
    rect.setAttribute("width",W); rect.setAttribute("height",H);
    rect.setAttribute("rx","13"); rect.setAttribute("fill",s.color+"1e");
    rect.setAttribute("stroke",s.color); rect.setAttribute("stroke-width","2");

    // Selection ring (shown when selected)
    const selRing = document.createElementNS(NS, "rect");
    selRing.classList.add("sel-ring");
    selRing.setAttribute("x",p.x-4); selRing.setAttribute("y",p.y-4);
    selRing.setAttribute("width",W+8); selRing.setAttribute("height",H+8);
    selRing.setAttribute("rx","17"); selRing.setAttribute("fill","none");
    selRing.setAttribute("stroke","#4D75FE"); selRing.setAttribute("stroke-width","2.5");
    selRing.setAttribute("stroke-dasharray","6 4"); selRing.setAttribute("display","none");
    selRing.setAttribute("pointer-events","none");

    // Name label
    const txt = document.createElementNS(NS, "text");
    txt.setAttribute("x",p.x+W/2); txt.setAttribute("y",p.y+H/2+5);
    txt.setAttribute("text-anchor","middle"); txt.setAttribute("font-size","13");
    txt.setAttribute("font-weight","700"); txt.setAttribute("fill",s.color);
    txt.setAttribute("pointer-events","none"); txt.textContent=s.name;

    // Terminal state double-ring at top-right
    if (s.is_terminal) {
      [9,5].forEach((r,i) => {
        const c = document.createElementNS(NS,"circle");
        c.setAttribute("cx",p.x+W-13); c.setAttribute("cy",p.y+13);
        c.setAttribute("r",r); c.setAttribute("pointer-events","none");
        i===0 ? (c.setAttribute("fill","none"),c.setAttribute("stroke",s.color),c.setAttribute("stroke-width","1.5"))
               : c.setAttribute("fill",s.color);
        g.appendChild(c);
      });
    }

    // Delete button (non-initial only)
    const delG = document.createElementNS(NS, "g");
    delG.setAttribute("display","none"); delG.style.cursor="pointer";
    if (!s.is_initial) {
      const dc = document.createElementNS(NS,"circle");
      dc.setAttribute("cx",p.x+W+2); dc.setAttribute("cy",p.y-2);
      dc.setAttribute("r","10"); dc.setAttribute("fill","#d6502f");
      const dt = document.createElementNS(NS,"text");
      dt.setAttribute("x",p.x+W+2); dt.setAttribute("y",p.y+3);
      dt.setAttribute("text-anchor","middle"); dt.setAttribute("font-size","14");
      dt.setAttribute("fill","#fff"); dt.setAttribute("font-weight","bold");
      dt.setAttribute("pointer-events","none"); dt.textContent="×";
      delG.appendChild(dc); delG.appendChild(dt);
      delG.addEventListener("click", e => {
        e.stopPropagation();
        if (confirm(`Delete state "${s.name}"?`)) onDeleteState(s.id);
      });
    }

    // "Connect" ring shown when another state is selected
    const connRing = document.createElementNS(NS, "rect");
    connRing.setAttribute("x",p.x-6); connRing.setAttribute("y",p.y-6);
    connRing.setAttribute("width",W+12); connRing.setAttribute("height",H+12);
    connRing.setAttribute("rx","19"); connRing.setAttribute("fill","#4D75FE18");
    connRing.setAttribute("stroke","#4D75FE"); connRing.setAttribute("stroke-width","2");
    connRing.setAttribute("stroke-dasharray","5 3"); connRing.setAttribute("display","none");
    connRing.setAttribute("pointer-events","none");

    g.appendChild(selRing); g.appendChild(connRing); g.appendChild(rect);
    g.appendChild(txt); g.appendChild(delG);

    g.addEventListener("mouseenter", () => {
      if (selectedId !== s.id) rect.setAttribute("stroke-width","3");
      if (!selectedId && !s.is_initial) delG.setAttribute("display","");
      if (selectedId && selectedId !== s.id) connRing.setAttribute("display","");
    });
    g.addEventListener("mouseleave", () => {
      if (selectedId !== s.id) rect.setAttribute("stroke-width","2");
      delG.setAttribute("display","none"); connRing.setAttribute("display","none");
    });
    g.addEventListener("click", e => {
      e.stopPropagation();
      if (selectedId && selectedId !== s.id) {
        // Create transition: selectedId → s.id
        const fromName = states.find(x=>x.id===selectedId)?.name||selectedId;
        showTransitionDialog(fromName, s.name,
          (label, requiresReason) => { onCreateTransition(selectedId, s.id, label, requiresReason); deselect(); },
          () => deselect()
        );
      } else if (selectedId === s.id) {
        deselect();
      } else {
        selectedId = s.id;
        svg.style.cursor = "crosshair";
        sLayer.querySelectorAll(".sel-ring").forEach(r => r.setAttribute("display","none"));
        selRing.setAttribute("display","");
        rect.setAttribute("stroke-width","3");
        hint(`"${s.name}" selected — click another state to connect, or click again to deselect`);
      }
    });

    sLayer.appendChild(g);
  });

  // Hint text at bottom of diagram
  const hintTxt = document.createElementNS(NS,"text");
  hintTxt.setAttribute("x", SVG_W/2); hintTxt.setAttribute("y", SVG_H-6);
  hintTxt.setAttribute("text-anchor","middle"); hintTxt.setAttribute("font-size","11");
  hintTxt.setAttribute("fill","#bbb"); hintTxt.setAttribute("pointer-events","none");
  hintTxt.textContent="diagram";
  svg.appendChild(hintTxt);

  svg.addEventListener("click", deselect);
  drawTransitions();
  return svg;
}

// ---- Admin: Swag catalog management ----
async function renderSwagCatalog(el) {
  const {items} = await api.get("/api/swag");
  el.innerHTML = `
    <div class="card admin-card" style="max-width:860px">
      <h3 style="margin-top:0">Swag Catalog</h3>
      <div class="swag-catalog-grid" id="catalog-list">
        <div class="swag-grid-header">Item</div>
        <div class="swag-grid-header">Description</div>
        <div class="swag-grid-header">Cost</div>
        <div class="swag-grid-header">Stock</div>
        <div class="swag-grid-header">Avail</div>
        <div class="swag-grid-header"></div>
        ${items.map(item => `
          <div class="swag-admin-row" data-item-id="${item.id}">
            <div class="swag-item-name">${esc(item.name)}</div>
            <textarea class="select sedit-desc" rows="2" style="resize:vertical">${esc(item.description)}</textarea>
            <input type="number" class="select sedit-cost" value="${item.point_cost}" min="1" title="Points cost">
            <div style="display:flex;gap:4px;align-items:center">
              <select class="select sedit-stock-mode" style="flex:1;min-width:0">
                <option value="unlimited" ${item.stock==null?"selected":""}>Unlimited</option>
                <option value="tracked" ${item.stock!=null?"selected":""}>Track stock</option>
              </select>
              <input type="number" class="select sedit-stock-qty" value="${item.stock!=null?item.stock:""}" min="0" placeholder="Qty" style="width:52px${item.stock==null?";display:none":""}">
            </div>
            <label class="toggle-label" style="margin:0" title="Available">
              <input type="checkbox" class="sedit-avail" ${item.is_available?"checked":""}>
              <span class="toggle-track"></span>
            </label>
            <button class="btn btn-primary sedit-save" style="font-size:13px;padding:8px 14px">Save</button>
            <div class="swag-row-sep"></div>
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

  // Show/hide qty input when stock mode changes
  el.querySelectorAll(".sedit-stock-mode").forEach(sel => {
    sel.addEventListener("change", () => {
      const qty = sel.parentElement.querySelector(".sedit-stock-qty");
      qty.style.display = sel.value === "tracked" ? "" : "none";
      if (sel.value === "tracked" && !qty.value) qty.value = "0";
    });
  });

  el.querySelectorAll(".sedit-save").forEach(btn => {
    const row = btn.closest(".swag-admin-row");
    const itemId = row.dataset.itemId;
    const origItem = items.find(i => String(i.id) === String(itemId));
    btn.addEventListener("click", async () => {
      const stockMode = row.querySelector(".sedit-stock-mode").value;
      const stockQty = row.querySelector(".sedit-stock-qty").value;
      try {
        await api.put(`/api/swag/${itemId}`, {
          name: origItem.name,
          description: row.querySelector(".sedit-desc").value,
          point_cost: parseInt(row.querySelector(".sedit-cost").value, 10),
          stock: stockMode === "tracked" && stockQty !== "" ? parseInt(stockQty, 10) : null,
          is_available: row.querySelector(".sedit-avail").checked,
          image_url: origItem.image_url || "",
        });
        toast("Item updated", "success");
      } catch(err) { toast(err.message, "error"); }
    });
  });

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

// ---- Admin: User Management (SuperAdmin only) ----
function renderUserManagement(el, users) {
  if (!el) return;
  const ROLES = ["user", "admin", "superadmin"];
  const roleLabel = { user: "User", admin: "Admin", superadmin: "SuperAdmin" };
  el.innerHTML = `
    <div class="card admin-card">
      <div class="admin-group-title">User Roles</div>
      <table class="user-mgmt-table">
        <thead><tr><th>Name</th><th>Title</th><th>Role</th></tr></thead>
        <tbody>
          ${users.map(u => `
            <tr>
              <td>${esc(u.name)}</td>
              <td style="color:var(--muted);font-size:13px">${esc(u.title || "")}</td>
              <td>
                <select class="role-select wf-input" data-uid="${u.id}"
                  ${u.id === state.me.id ? 'disabled title="Cannot change your own role"' : ""}>
                  ${ROLES.map(r => `<option value="${r}" ${u.role === r ? "selected" : ""}>${roleLabel[r]}</option>`).join("")}
                </select>
              </td>
            </tr>`).join("")}
        </tbody>
      </table>
    </div>`;
  el.querySelectorAll(".role-select:not([disabled])").forEach(sel => {
    const originalRole = sel.value;
    sel.addEventListener("change", async () => {
      try {
        await api.put(`/api/users/${sel.dataset.uid}/role`, { role: sel.value });
        toast(`Role updated to ${roleLabel[sel.value] || sel.value}`, "success");
      } catch (err) {
        toast(err.message || "Failed to update role", "error");
        sel.value = originalRole;
      }
    });
  });
}

// --------------------------------------------------------------------------
// Notification bell
// --------------------------------------------------------------------------
$("#notif-btn").addEventListener("click", () => go("notifications"));

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
