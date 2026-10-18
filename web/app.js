(function () {
  "use strict";
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const DPR = Math.max(1, window.devicePixelRatio || 1);

  // ---------- helpers ----------
  function rate(bps) {
    if (bps == null) return "—";
    if (bps < 1) return "0 B/s";
    const u = ["B", "KB", "MB", "GB"]; let n = bps, i = 0;
    while (n >= 1024 && i < 3) { n /= 1024; i++; }
    return (i ? n.toFixed(1) : n.toFixed(0)) + " " + u[i] + "/s";
  }
  function bytes(n) {
    n = n || 0; const u = ["B", "KB", "MB", "GB", "TB"]; let i = 0;
    while (n >= 1024 && i < 4) { n /= 1024; i++; }
    return (i ? n.toFixed(1) : n.toFixed(0)) + " " + u[i];
  }
  function notify(title, body) {
    try { if (window.Notification && Notification.permission === "granted") new Notification(title, { body }); } catch (e) { }
  }
  function esc(s) { return (s || "").replace(/[<>&"]/g, c => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;", '"': "&quot;" }[c])); }
  function hexA(hex, a) { const n = parseInt(hex.slice(1), 16); return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`; }

  function toast(msg, kind) {
    const t = document.createElement("div");
    t.className = "toast " + (kind || "");
    t.textContent = msg;
    $("#toast-root").appendChild(t);
    setTimeout(() => { t.style.opacity = "0"; t.style.transition = ".3s"; setTimeout(() => t.remove(), 300); }, 2200);
  }

  async function api(action, extra) {
    try {
      const r = await fetch("/api/action", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(Object.assign({ action }, extra || {}))
      });
      return await r.json();
    } catch (e) { toast("Gagal: " + e, "err"); }
  }

  // ---------- nav ----------
  $$(".nav-item").forEach(b => b.onclick = () => {
    $$(".nav-item").forEach(x => x.classList.remove("active"));
    b.classList.add("active");
    const v = b.dataset.view;
    $$(".view").forEach(x => x.classList.add("hidden"));
    const sec = $("#view-" + v);
    sec.classList.remove("hidden", "view"); void sec.offsetWidth; sec.classList.add("view");
    $("#page-title").textContent = b.textContent.trim();
  });

  // ---------- chart ----------
  const cv = $("#chart"), ctx = cv.getContext("2d");
  let DL = new Array(80).fill(0), UL = new Array(80).fill(0);
  function resizeCanvas() {
    const r = cv.getBoundingClientRect();
    cv.width = Math.max(10, r.width * DPR); cv.height = Math.max(10, r.height * DPR);
  }
  window.addEventListener("resize", resizeCanvas);
  function pushRate(up, down) {
    DL.push(down); DL.shift(); UL.push(up); UL.shift();
    $("#cur-dl").textContent = rate(down); $("#cur-ul").textContent = rate(up);
  }
  function drawSeries(arr, mx, color, alpha) {
    const w = cv.width, h = cv.height, padT = 8 * DPR, padB = 6 * DPR, us = h - padT - padB;
    const step = w / (arr.length - 1);
    const pts = arr.map((v, i) => [i * step, h - padB - (v / mx) * us]);
    ctx.beginPath(); ctx.moveTo(0, h - padB);
    pts.forEach(p => ctx.lineTo(p[0], p[1])); ctx.lineTo(w, h - padB); ctx.closePath();
    const g = ctx.createLinearGradient(0, padT, 0, h);
    g.addColorStop(0, hexA(color, alpha)); g.addColorStop(1, hexA(color, 0));
    ctx.fillStyle = g; ctx.fill();
    ctx.beginPath(); pts.forEach((p, i) => i ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1]));
    ctx.strokeStyle = color; ctx.lineWidth = 2 * DPR;
    ctx.shadowColor = color; ctx.shadowBlur = 8 * DPR; ctx.stroke(); ctx.shadowBlur = 0;
  }
  function drawChart() {
    if (cv.width < 10) resizeCanvas();
    const w = cv.width, h = cv.height, padT = 8 * DPR, padB = 6 * DPR;
    ctx.clearRect(0, 0, w, h);
    const mx = Math.max(Math.max(...DL), Math.max(...UL), 1024) * 1.25;
    ctx.strokeStyle = "rgba(90,160,220,.08)"; ctx.lineWidth = 1;
    for (let i = 1; i < 4; i++) { const y = padT + (h - padT - padB) * i / 4; ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke(); }
    drawSeries(DL, mx, "#3d8bfd", 0.30);
    drawSeries(UL, mx, "#f59e0b", 0.22);
    requestAnimationFrame(drawChart);
  }

  // ---------- number animation ----------
  function animNum(el, to) {
    const from = parseInt(el.textContent) || 0;
    if (from === to) { el.textContent = to; return; }
    const t0 = performance.now(), d = 420;
    function step(t) {
      const k = Math.min(1, (t - t0) / d);
      el.textContent = Math.round(from + (to - from) * (1 - Math.pow(1 - k, 3)));
      if (k < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }

  // ---------- renderers ----------
  function renderStats(s) {
    for (const k in s) { const el = $(`[data-v="${k}"]`); if (el) animNum(el, s[k]); }
  }
  function renderNet(n) {
    if (!n) return;
    const dot = $("#conn-dot");
    if (n.ok) { $("#net-summary").textContent = `${n.iface}  •  IP ${n.ip}  •  GW ${n.gateway}  •  ${n.cidr}`; }
    else { $("#net-summary").textContent = n.error || "jaringan tidak terbaca"; }
    $("#net-foot").textContent = n.ok ? `${n.iface}\nIP ${n.ip}\nGW ${n.gateway}` : "offline";
  }
  function devCard(d) {
    const st = d.status;
    const nm = esc(d.name || (d.you ? "PC Ini" : d.gateway ? "Gateway" : d.ip));
    let actions = "";
    if (st === "safe") {
      actions = `<span class="muted" style="font-size:11px">dilindungi otomatis</span>`;
    } else {
      const cutBtn = st === "cut"
        ? `<button class="btn" data-act="restore" data-mac="${d.mac}">✓ Pulihkan</button>`
        : `<button class="btn btn-danger" data-act="cut" data-mac="${d.mac}">✂ Putus</button>`;
      actions = cutBtn +
        `<button class="btn" data-act="manage" data-mac="${d.mac}">◎ Kelola</button>` +
        `<button class="btn" data-act="throttle" data-mac="${d.mac}">\u{1F422} Limit</button>` +
        `<button class="btn" data-act="block" data-mac="${d.mac}">⛔ Blokir</button>` +
        `<button class="btn" data-act="rename" data-mac="${d.mac}">✎</button>` +
        `<button class="btn" data-act="schedule" data-mac="${d.mac}">⏰</button>`;
    }
    return `<div class="dev s-${st}">
      <div class="dev-top">
        <div class="dev-emoji">${d.emoji || "\u{1F5A5}"}</div>
        <div class="dev-id">
          <div class="dev-name">${nm}</div>
          <div class="dev-ip">${d.ip}${d.you ? " · kamu" : d.gateway ? " · router" : ""}</div>
        </div>
        <span class="pill ${st}">${st}</span>
      </div>
      <div class="dev-meta">
        <span>${esc(d.vendor || "")} · ${esc(d.type || "")}${d.total ? " · " + bytes(d.total) : ""}</span>
        <span class="dev-rate"><span class="d">↓ ${rate(d.down)}</span> &nbsp; <span class="u">↑ ${rate(d.up)}</span></span>
      </div>
      ${d.activity && d.activity.length ? `<div class="dev-act">▸ ${d.activity.map(esc).join(" · ")}</div>` : ""}
      ${st !== "safe" ? `<div class="dev-role">Role <select class="role-sel" data-mac="${d.mac}">
        <option value="guest"${d.role === "guest" ? " selected" : ""}>Guest</option>
        <option value="staff"${d.role === "staff" ? " selected" : ""}>Staff</option>
        <option value="blocked"${d.role === "blocked" ? " selected" : ""}>Block</option>
      </select></div>` : ""}
      <div class="dev-actions">${actions}</div>
    </div>`;
  }
  let allDevices = [], devFilter = "";
  function renderDevices(devs) {
    allDevices = devs;
    const g = $("#device-grid");
    $("#dev-count").textContent = devs.length + " perangkat";
    if (!devs.length) { g.innerHTML = `<div class="empty big">Belum ada perangkat. Klik <b>Scan Jaringan</b>.</div>`; return; }
    const list = devFilter
      ? devs.filter(d => ((d.name || "") + d.ip + (d.vendor || "")).toLowerCase().includes(devFilter))
      : devs;
    g.innerHTML = list.length ? list.map(devCard).join("")
      : `<div class="empty big">Tidak ada yang cocok dengan "${esc(devFilter)}".</div>`;
  }
  function renderInsight(ins) {
    const el = $("#insight");
    if (!ins) { el.innerHTML = ""; return; }
    if (ins.hint) {
      el.className = "insight hint";
      el.innerHTML = `<div class="ins-ic">◎</div><div class="ins-b"><div class="ins-t">Analisis per-perangkat</div><div class="ins-s">${esc(ins.hint)}</div></div>`;
      return;
    }
    el.className = "insight live";
    const act = ins.activity && ins.activity.length ? ins.activity.map(esc).join(" · ") : "menganalisis…";
    el.innerHTML = `<div class="ins-ic">\u{1F4E1}</div><div class="ins-b">
      <div class="ins-t">${ins.emoji || ""} <b>${esc(ins.name)}</b> memakai bandwidth tertinggi — ${rate(ins.rate)}</div>
      <div class="ins-s">Sedang akses: <b>${act}</b>${ins.blocked ? ` · ${ins.blocked} diblokir` : ""}</div>
    </div>`;
  }
  function renderTalkers(devs) {
    const box = $("#talkers");
    const act = devs.map(d => ({ d, t: (d.up || 0) + (d.down || 0) })).filter(x => x.t > 0)
      .sort((a, b) => b.t - a.t).slice(0, 5);
    if (!act.length) { box.innerHTML = `<div class="empty">Kelola perangkat untuk melihat pemakaian per-device.</div>`; return; }
    const mx = act[0].t || 1;
    box.innerHTML = act.map(({ d, t }) => `<div class="talker">
      <div class="nm">${d.emoji || ""} ${esc(d.name || d.ip)}</div>
      <div class="track"><div class="fill" style="width:${Math.round(t / mx * 100)}%"></div></div>
      <div class="rt">${rate(t)}</div></div>`).join("");
  }
  function renderFirewall(fw) {
    if (!fw) return;
    $("#categories").innerHTML = fw.categories.map(c => `<div class="cat">
      <div><span class="cn">${esc(c.name)}</span><span class="cc">${c.count} domain</span></div>
      <label class="switch"><input type="checkbox" data-cat="${esc(c.name)}" ${c.on ? "checked" : ""}><span class="slider"></span></label>
    </div>`).join("");
    $("#fw-list").innerHTML = fw.global.length
      ? fw.global.map(d => `<span class="chip">${esc(d)} <b data-unblock="${esc(d)}">×</b></span>`).join("")
      : `<div class="empty">Belum ada domain kustom.</div>`;
  }
  function renderSchedules(list) {
    const box = $("#sched-list");
    if (!list || !list.length) { box.innerHTML = `<div class="empty">Belum ada jadwal. Tambah dari kartu perangkat → ⏰.</div>`; return; }
    box.innerHTML = list.map(r => `<div class="sched">
      <span><b>${esc(r.name)}</b> — ${r.action === "cut" ? "Putus" : "Blokir situs"} · ${r.start}–${r.end} · ${r.days.join(",")}</span>
      <button class="btn sm" data-delsched="${r.id}">Hapus</button></div>`).join("");
  }
  let lastProtFocus = false;
  function renderProtection(active) {
    const sw = $("#prot-switch");
    if (document.activeElement !== sw) sw.checked = !!active;
    $("#prot-stat").textContent = active ? "AKTIF — memantau gateway" : "Nonaktif";
    $("#prot-stat").style.color = active ? "var(--cyan)" : "var(--text)";
  }
  function pushFeed(id, html, cls) {
    const f = $(id); if (!f) return;
    const ln = document.createElement("div"); ln.className = "ln " + (cls || ""); ln.innerHTML = html;
    f.appendChild(ln);
    while (f.children.length > 80) f.removeChild(f.firstChild);
    f.scrollTop = f.scrollHeight;
  }
  function applyEvents(evs) {
    (evs || []).forEach(e => {
      if (e.type === "attack") {
        pushAlert(`<span class="sev sev-hi">ARP</span> Penyerang ${esc(e.mac)} meniru gateway ${esc(e.ip)}`, "alert");
        pushFeed("#attack-feed", `Penyerang ${esc(e.mac)} meniru gateway ${esc(e.ip)}`, "alert");
        toast("⚠ Serangan ARP terdeteksi!", "err");
        notify("Serangan ARP terdeteksi", "Penyerang " + e.mac);
        alertCount++; setT("#sv-alerts", alertCount);
      } else if (e.type === "block") {
        pushAlert(`<span class="sev sev-md">BLOCK</span> ${esc(e.ip)} → ${esc(e.domain)}`, "block");
        alertCount++; setT("#sv-alerts", alertCount);
      } else if (e.type === "newdevice") {
        pushAlert(`<span class="sev sev-lo">NEW</span> Perangkat baru: ${esc(e.name || e.ip)}`);
        toast("Perangkat baru: " + (e.name || e.ip), "ok");
        notify("Perangkat baru terhubung", (e.name || e.ip));
        alertCount++; setT("#sv-alerts", alertCount);
      }
    });
  }

  function renderSettings(s) {
    if (!s) return;
    const set = (id, val) => { const e = $(id); if (e && document.activeElement !== e) { if (e.type === "checkbox") e.checked = !!val; else e.value = val; } };
    set("#s-autoblock", s.auto_block_new); set("#s-kbps", s.guest_kbps);
    set("#s-mb", s.quota_mb); set("#s-min", s.quota_minutes);
  }
  const PCOLORS = ["#3d8bfd", "#22c55e", "#f59e0b", "#ef4444", "#14b8a6", "#a855f7", "#ec4899", "#8a93a6"];
  function setT(sel, v) { const e = $(sel); if (e) e.textContent = v; }
  function renderDonut(protos) {
    const cv = $("#donut"); if (!cv) return;
    const ctx = cv.getContext("2d"); const w = cv.width, h = cv.height, cx = w / 2, cy = h / 2;
    const r = Math.min(w, h) / 2 - 6, lw = r * 0.42, rr = r - lw / 2;
    ctx.clearRect(0, 0, w, h);
    const total = protos.reduce((s, p) => s + p.count, 0) || 1;
    let a = -Math.PI / 2;
    protos.forEach((p, i) => {
      const a2 = a + (p.count / total) * 2 * Math.PI;
      ctx.beginPath(); ctx.arc(cx, cy, rr, a, a2);
      ctx.strokeStyle = PCOLORS[i % PCOLORS.length]; ctx.lineWidth = lw; ctx.stroke(); a = a2;
    });
    const lg = $("#donut-legend");
    if (lg) lg.innerHTML = protos.length
      ? protos.map((p, i) => `<div class="dl"><span class="ddot" style="background:${PCOLORS[i % PCOLORS.length]}"></span>${esc(p.name)} <b>${p.pct}%</b></div>`).join("")
      : '<div class="empty">Tidak ada trafik teramati.</div>';
  }
  function renderRank(sel, items) {
    const el = $(sel); if (!el) return;
    if (!items || !items.length) { el.innerHTML = '<div class="empty">—</div>'; return; }
    const mx = Math.max(...items.map(i => i.value)) || 1;
    el.innerHTML = items.map((it, n) => `<div class="rk"><span class="rk-n">${n + 1}</span><span class="rk-l">${it.label}</span><div class="rk-bar"><div style="width:${Math.round(it.value / mx * 100)}%"></div></div><span class="rk-v">${it.vtext != null ? it.vtext : it.value}</span></div>`).join("");
  }
  function renderTopHosts(devs) {
    const items = devs.filter(d => !d.gateway).map(d => ({ label: (d.emoji || "") + " " + esc(d.name || d.ip), value: d.total || 0, vtext: bytes(d.total || 0) }))
      .sort((a, b) => b.value - a.value).slice(0, 6);
    renderRank("#top-hosts", items);
  }
  function renderActivity(devs) {
    const el = $("#activity-grid"); if (!el) return;
    const managed = devs.filter(d => d.status === "managed" || d.status === "throttled");
    if (!managed.length) {
      el.innerHTML = '<div class="empty big">Belum ada perangkat yang diawasi. Buka <b>Perangkat → Awasi Semua</b> (atau Kelola satu perangkat), dan aktifkan <b>IP Forwarding</b> di Setelan.</div>';
      return;
    }
    el.innerHTML = managed.map(d => {
      const sites = d.sites || [];
      const mx = Math.max(...sites.map(s => s.b), 1);
      const rows = sites.length
        ? sites.map(s => `<div class="rk"><span class="rk-l">${esc(s.d)}</span><div class="rk-bar"><div style="width:${Math.round(s.b / mx * 100)}%"></div></div><span class="rk-v">${bytes(s.b)}</span></div>`).join("")
        : '<div class="empty">menunggu trafik… (pastikan IP Forwarding aktif)</div>';
      return `<div class="dev"><div class="dev-top"><div class="dev-emoji">${d.emoji || "\u{1F5A5}"}</div>
        <div class="dev-id"><div class="dev-name">${esc(d.name || d.ip)}</div>
        <div class="dev-ip">${d.ip} · ↓${rate(d.down)} ↑${rate(d.up)}</div></div>
        <span class="pill ${d.status}">${d.status}</span></div>
        <div class="act-list">${rows}</div></div>`;
    }).join("");
  }
  function renderIface(net) {
    const el = $("#iface-status"); if (!el || !net) return;
    el.innerHTML = `<div class="if-top"><span class="dot ${net.ok ? "ok" : ""}"></span><b>${esc((net.iface || "?").replace("\\\\Device\\\\NPF_", "NPF "))}</b></div>
      <div class="if-grid"><span>IP</span><b>${esc(net.ip || "-")}</b><span>Gateway</span><b>${esc(net.gateway || "-")}</b><span>Subnet</span><b>${esc(net.cidr || "-")}</b><span>Status</span><b style="color:var(--ok)">${net.ok ? "Up" : "Down"}</b></div>`;
  }
  let alertCount = 0;
  function pushAlert(html, cls) {
    const f = $("#alerts-list"); if (!f) return;
    if (f.querySelector(".empty")) f.innerHTML = "";
    const t = new Date().toLocaleTimeString();
    const ln = document.createElement("div"); ln.className = "aln " + (cls || "");
    ln.innerHTML = `<span class="at">${t}</span> ${html}`;
    f.insertBefore(ln, f.firstChild);
    while (f.children.length > 40) f.removeChild(f.lastChild);
  }
  function applySnapshot(d) {
    if (d.net) { renderNet(d.net); renderIface(d.net); }
    if (d.stats) renderStats(d.stats);
    if (d.devices) { renderDevices(d.devices); renderTopHosts(d.devices); renderActivity(d.devices); }
    if (typeof d.up === "number") { pushRate(d.up, d.down); setT("#sv-tput", rate((d.up || 0) + (d.down || 0))); }
    if (d.observed) {
      setT("#sv-flows", d.observed.active_flows);
      setT("#sv-proto", d.observed.protocols.length);
      renderDonut(d.observed.protocols);
      renderRank("#top-endpoints", d.observed.endpoints.map(e => ({ label: esc(e.ip), value: e.count, vtext: e.count + " flows" })));
    }
    if (d.apps) renderRank("#top-apps", d.apps.map(a => ({ label: esc(a.name), value: a.bytes, vtext: bytes(a.bytes) })));
    if ("protection" in d) renderProtection(d.protection);
    if (d.firewall) renderFirewall(d.firewall);
    if (d.schedules) renderSchedules(d.schedules);
    if (d.settings) renderSettings(d.settings);
    applyEvents(d.events);
  }

  // ---------- WebSocket ----------
  function connect() {
    const ws = new WebSocket((location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/ws");
    ws.onopen = () => { $("#conn-dot").classList.add("ok"); $("#conn-text").textContent = "tersambung"; };
    ws.onclose = () => { $("#conn-dot").classList.remove("ok"); $("#conn-text").textContent = "terputus…"; setTimeout(connect, 1500); };
    ws.onmessage = ev => { try { applySnapshot(JSON.parse(ev.data)); } catch (e) { } };
  }

  // ---------- scan ----------
  $("#btn-scan").onclick = async () => {
    const b = $("#btn-scan"); b.classList.add("spin"); b.disabled = true;
    try { const r = await fetch("/api/scan", { method: "POST" }); const d = await r.json(); applySnapshot(d); toast("Scan selesai: " + (d.devices ? d.devices.length : 0) + " perangkat", "ok"); }
    catch (e) { toast("Scan gagal", "err"); }
    b.classList.remove("spin"); b.disabled = false;
  };

  // ---------- modals ----------
  function modal(html) {
    const bg = document.createElement("div"); bg.className = "modal-bg";
    bg.innerHTML = `<div class="modal">${html}</div>`;
    $("#modal-root").appendChild(bg);
    bg.addEventListener("click", e => { if (e.target === bg) bg.remove(); });
    return bg;
  }
  function askThrottle(mac) {
    const m = modal(`<h3>Batasi Kecepatan</h3><div class="sub">Batas unduhan untuk perangkat ini.</div>
      <label>Batas (kbps, 0 = tanpa batas)</label><input class="input" id="m-kbps" type="number" value="1024" min="0">
      <div class="m-actions"><button class="btn" id="m-cancel">Batal</button><button class="btn btn-primary" id="m-ok">Terapkan</button></div>`);
    $("#m-cancel", m).onclick = () => m.remove();
    $("#m-ok", m).onclick = async () => { await api("throttle", { mac, kbps: parseInt($("#m-kbps", m).value) || 0 }); m.remove(); toast("Batas kecepatan diterapkan", "ok"); };
  }
  function askBlock(mac) {
    const m = modal(`<h3>Blokir Situs</h3><div class="sub">Domain yang diblokir untuk perangkat ini.</div>
      <label>Domain</label><input class="input" id="m-dom" placeholder="mis. tiktok.com">
      <div class="m-actions"><button class="btn" id="m-cancel">Batal</button><button class="btn btn-primary" id="m-ok">Blokir</button></div>`);
    $("#m-cancel", m).onclick = () => m.remove();
    $("#m-ok", m).onclick = async () => { const d = $("#m-dom", m).value.trim(); if (d) { await api("block_device", { mac, domain: d }); toast("'" + d + "' diblokir", "ok"); } m.remove(); };
  }
  function askRename(mac) {
    const m = modal(`<h3>Beri Nama</h3><div class="sub">Alias tersimpan untuk perangkat ini.</div>
      <label>Nama</label><input class="input" id="m-nm" placeholder="mis. HP Budi">
      <div class="m-actions"><button class="btn" id="m-cancel">Batal</button><button class="btn btn-primary" id="m-ok">Simpan</button></div>`);
    $("#m-cancel", m).onclick = () => m.remove();
    $("#m-ok", m).onclick = async () => { await api("rename", { mac, name: $("#m-nm", m).value }); m.remove(); toast("Nama disimpan", "ok"); };
  }
  function askSchedule(mac) {
    const days = ["Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min"];
    const m = modal(`<h3>Jadwalkan</h3><div class="sub">Aksi otomatis pada hari & jam tertentu.</div>
      <label>Aksi</label><select class="input" id="m-act"><option value="cut">Putus internet</option><option value="block">Blokir situs (sesuai daftar)</option></select>
      <label>Hari</label><div class="days" id="m-days">${days.map((d, i) => `<span class="day${i < 5 ? " on" : ""}" data-d="${i}">${d}</span>`).join("")}</div>
      <div class="inline2"><div><label>Dari</label><input class="input" id="m-start" type="time" value="21:00"></div><div><label>Sampai</label><input class="input" id="m-end" type="time" value="06:00"></div></div>
      <div class="m-actions"><button class="btn" id="m-cancel">Batal</button><button class="btn btn-primary" id="m-ok">Tambah</button></div>`);
    $$(".day", m).forEach(d => d.onclick = () => d.classList.toggle("on"));
    $("#m-cancel", m).onclick = () => m.remove();
    $("#m-ok", m).onclick = async () => {
      const days2 = $$(".day.on", m).map(d => parseInt(d.dataset.d));
      if (!days2.length) { toast("Pilih minimal satu hari", "err"); return; }
      await api("schedule_add", { mac, sched_action: $("#m-act", m).value, days: days2, start: $("#m-start", m).value, end: $("#m-end", m).value });
      m.remove(); toast("Jadwal ditambahkan", "ok");
    };
  }

  // ---------- global click delegation ----------
  document.addEventListener("click", async (e) => {
    const el = e.target.closest("[data-act],[data-unblock],[data-delsched]");
    if (!el) return;
    if (el.dataset.unblock != null) { await api("unblock_global", { domain: el.dataset.unblock }); return; }
    if (el.dataset.delsched != null) { await api("schedule_del", { id: parseInt(el.dataset.delsched) }); return; }
    const act = el.dataset.act, mac = el.dataset.mac;
    if (act === "throttle") return askThrottle(mac);
    if (act === "block") return askBlock(mac);
    if (act === "rename") return askRename(mac);
    if (act === "schedule") return askSchedule(mac);
    if (act === "cutall") { if (!confirm("Putus internet semua perangkat (kecuali PC & gateway)?")) return; }
    await api(act, { mac });
    if (act === "cut") toast("Perangkat diputus", "ok");
    if (act === "manage") toast("Perangkat dikelola (MITM)", "ok");
    if (act === "monitor_all") toast("Mengawasi semua perangkat", "ok");
    if (act === "unmonitor_all") toast("Berhenti mengawasi", "ok");
  });

  // category toggles + firewall add + protection + forwarding
  document.addEventListener("change", (e) => {
    if (e.target.dataset && e.target.dataset.cat != null) api("category", { name: e.target.dataset.cat, on: e.target.checked });
    if (e.target.id === "prot-switch") { api("protect", { on: e.target.checked }); }
    if (e.target.classList && e.target.classList.contains("role-sel")) {
      api("set_role", { mac: e.target.dataset.mac, role: e.target.value });
      toast("Role diubah ke " + e.target.value, "ok");
    }
  });
  $("#s-save").onclick = async () => {
    await api("settings", { settings: {
      auto_block_new: $("#s-autoblock").checked,
      guest_kbps: parseInt($("#s-kbps").value) || 0,
      quota_mb: parseInt($("#s-mb").value) || 0,
      quota_minutes: parseInt($("#s-min").value) || 0,
    }});
    toast("Kebijakan hotspot disimpan", "ok");
    fetch("/api/snapshot").then(r => r.json()).then(applySnapshot).catch(() => { });
  };
  $("#fw-add").onclick = async () => { const v = $("#fw-input").value.trim(); if (v) { await api("block_global", { domain: v }); $("#fw-input").value = ""; } };
  $("#fw-input").addEventListener("keydown", e => { if (e.key === "Enter") $("#fw-add").click(); });
  $("#btn-fwd").onclick = async () => { await api("forwarding"); $("#fwd-stat").textContent = "diaktifkan (jika belum bekerja, restart 1x)"; toast("IP forwarding diaktifkan", "ok"); };
  $("#btn-quit").onclick = () => {
    if (!confirm("Matikan server NetHawk? Dashboard berhenti & semua ARP dipulihkan.")) return;
    api("quit");
    document.body.innerHTML = '<div style="color:#8fa6c4;font:15px sans-serif;display:grid;place-items:center;height:100vh;background:#05070d">NetHawk dimatikan. Kamu bisa menutup tab ini.</div>';
  };

  // ---------- boot ----------
  $("#dev-search").addEventListener("input", e => { devFilter = e.target.value.toLowerCase(); renderDevices(allDevices); });
  try { if (window.Notification && Notification.permission === "default") Notification.requestPermission(); } catch (e) { }
  resizeCanvas();
  requestAnimationFrame(drawChart);
  fetch("/api/snapshot").then(r => r.json()).then(applySnapshot).catch(() => { });
  connect();
})();
