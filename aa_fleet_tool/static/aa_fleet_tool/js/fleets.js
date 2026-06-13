/* Active Fleets page — live member table, composition graphs and all
 * live-fleet ESI actions (kick/move/invite, wing/squad, MOTD, FAT/SRP, ping).
 *
 * URLs, translated strings and per-fleet flags are injected via window.FT_PAGE
 * in a small inline <script> the template renders before this file.
 */
(function () {
  "use strict";

  const C = window.FT_PAGE || {};
  const U = C.urls || {};
  const I = C.i18n || {};
  const FLAGS = C.flags || {};

  const csrfToken = document.cookie.match(/csrftoken=([^;]+)/)?.[1] ?? "";
  const currentUrl = new URL(window.location.href);
  const fleetPk = currentUrl.searchParams.get("fleet");
  const doctrinePk = currentUrl.searchParams.get("doctrine");
  const NO_NAME = I.noName;

  function post(url, data) {
    const fd = new FormData();
    fd.append("csrfmiddlewaretoken", csrfToken);
    for (const [k, v] of Object.entries(data)) fd.append(k, v);
    return fetch(url, { method: "POST", body: fd })
      .then(r => r.json())
      .catch(err => { console.error("POST failed:", url, err); return { ok: false, error: I.serverError }; });
  }

  function reload() {
    const ws = document.getElementById("wing-structure");
    if (ws?.classList.contains("show")) sessionStorage.setItem("wing_open", "1");
    window.location.reload();
  }
  function navTo(params) {
    const u = new URL(window.location.href);
    for (const [k, v] of Object.entries(params)) {
      if (v) u.searchParams.set(k, v);
      else u.searchParams.delete(k);
    }
    window.location.href = u.toString();
  }

  // ── Composition graphs (DPS / Logi over the fleet's lifetime) ──────────
  // Two charts with identical logic: the whole fleet and only members
  // undocked in the FC's solar system.
  let compChart = null, compChartSystem = null;
  function fmtTime(iso) {
    try { return new Date(iso).toISOString().slice(11, 16); } catch (e) { return ""; }
  }
  function buildCompChart(canvasId, initial, keys) {
    const canvas = document.getElementById(canvasId);
    if (!canvas || typeof Chart === "undefined") return null;
    return new Chart(canvas, {
      type: "line",
      data: {
        labels: initial.map(s => fmtTime(s.timestamp)),
        datasets: [
          { label: "DPS", data: initial.map(s => s[keys.dps]), borderColor: "#dc3545", backgroundColor: "rgba(220,53,69,.12)", tension: .3, fill: true, pointRadius: 0, borderWidth: 2 },
          { label: "Logi", data: initial.map(s => s[keys.logi]), borderColor: "#198754", backgroundColor: "rgba(25,135,84,.12)", tension: .3, fill: true, pointRadius: 0, borderWidth: 2 },
          { label: I.total, data: initial.map(s => s[keys.total]), borderColor: "#6c757d", borderDash: [4, 4], tension: .3, fill: false, pointRadius: 0, borderWidth: 1 },
        ],
      },
      options: {
        responsive: true, maintainAspectRatio: false, animation: false,
        interaction: { mode: "index", intersect: false },
        scales: { y: { beginAtZero: true, ticks: { precision: 0 } }, x: { ticks: { maxTicksLimit: 6, maxRotation: 0 } } },
        plugins: { legend: { position: "top", labels: { boxWidth: 12 } } },
      },
    });
  }
  function initCompChart() {
    let initial = [];
    try { initial = JSON.parse(document.getElementById("snapshot-data")?.textContent || "[]"); } catch (e) {}
    compChart = buildCompChart("comp-chart", initial, { dps: "dps", logi: "logi", total: "total" });
    compChartSystem = buildCompChart("comp-chart-system", initial, { dps: "in_system_dps", logi: "in_system_logi", total: "in_system_total" });
  }
  function applyHistory(chart, history, keys) {
    if (!chart || !history) return;
    chart.data.labels = history.map(s => fmtTime(s.t));
    chart.data.datasets[0].data = history.map(s => s[keys.dps]);
    chart.data.datasets[1].data = history.map(s => s[keys.logi]);
    chart.data.datasets[2].data = history.map(s => s[keys.total]);
    chart.update();
  }
  function updateCompChart(history) {
    applyHistory(compChart, history, { dps: "dps", logi: "logi", total: "total" });
    applyHistory(compChartSystem, history, { dps: "sys_dps", logi: "sys_logi", total: "sys_total" });
  }

  // DataTables init
  document.addEventListener("DOMContentLoaded", function () {
    initCompChart();
    if (sessionStorage.getItem("wing_open") === "1") {
      sessionStorage.removeItem("wing_open");
      const ws = document.getElementById("wing-structure");
      if (ws) new bootstrap.Collapse(ws, { toggle: false }).show();
    }

    try {
      if (document.getElementById("tbl-commanders")) {
        $("#tbl-commanders").DataTable({ pageLength: 25 });
      }
      if (document.getElementById("tbl-members")) {
        dtMembers = $("#tbl-members").DataTable({ pageLength: 50, order: [[3, "asc"]], stateSave: true, stateDuration: 300 });
      }
    } catch (e) {
      console.error("DataTable init error:", e);
    }

    if (fleetPk) {
      // Match the 5s backend sync so the table and graphs stay near-live.
      setInterval(refreshMembersLive, 5000);
    }
  });

  // Doctrine selector — preserve current fleet type in URL
  document.getElementById("doctrine-select")?.addEventListener("change", function () {
    const ft = document.getElementById("fleet-type-select")?.value || "";
    navTo({ fleet: fleetPk, doctrine: this.value, fleet_type: ft || null });
  });

  // Fleet type selector — update URL without reload so it survives doctrine changes
  document.getElementById("fleet-type-select")?.addEventListener("change", function () {
    const u = new URL(window.location.href);
    if (this.value) u.searchParams.set("fleet_type", this.value);
    else u.searchParams.delete("fleet_type");
    history.replaceState({}, "", u.toString());
  });

  function _getSelectedFleetTypeName() {
    return document.getElementById("fleet-type-select")?.value || "";
  }
  function _getSelectedFleetTypePk() {
    const sel = document.getElementById("fleet-type-select");
    return sel?.options[sel.selectedIndex]?.dataset.pk || "";
  }

  // Sync button
  document.getElementById("btn-sync")?.addEventListener("click", function () {
    post(U.triggerSync, {}).then(() => {
      this.innerHTML = '<i class="fas fa-check"></i> ' + I.syncStarted;
      setTimeout(() => { this.innerHTML = '<i class="fas fa-sync"></i> ' + I.sync; }, 3000);
    });
  });

  // Remove FC
  document.querySelectorAll(".btn-remove-fc").forEach(btn => {
    btn.addEventListener("click", function () {
      if (!confirm(I.removeFc)) return;
      post(U.removeFc, { fc_pk: this.dataset.pk }).then(reload);
    });
  });

  // Free Move toggle
  document.getElementById("btn-toggle-freemove")?.addEventListener("click", function () {
    const url = U.setFreeMove.replace("/0/", "/" + this.dataset.fleet + "/");
    post(url, { value: this.dataset.value }).then(r => { if (r.ok) reload(); else alert(r.error); });
  });

  // ── MOTD ──────────────────────────────────────────────────────────────

  function stripEveTags(raw) {
    const tmp = document.createElement("div");
    tmp.innerHTML = (raw || "").replace(/<br\s*\/?>/gi, "\n");
    return tmp.textContent || tmp.innerText || "";
  }

  function updateMotdDisplay(raw) {
    const disp = document.getElementById("motd-display-text");
    const block = document.getElementById("motd-display-block");
    if (disp) disp.textContent = stripEveTags(raw);
    if (block) block.classList.toggle("d-none", !(raw || "").trim());
  }

  // MOTD inline save
  document.getElementById("btn-save-motd")?.addEventListener("click", function () {
    const url = U.setMotd.replace("/0/", "/" + this.dataset.fleet + "/");
    const motd = document.getElementById("motd-text").value;
    post(url, { motd }).then(r => {
      if (r.ok) {
        updateMotdDisplay(motd);
        bootstrap.Collapse.getInstance(document.getElementById("motd-editor"))?.hide();
      } else alert(r.error);
    });
  });

  // MOTD Library data (from JSON script tag — no data-text attribute needed)
  const _motdTplData = JSON.parse(document.getElementById("motd-tpl-data")?.textContent || "[]");

  // Load MOTD modal
  let _loadMotdModal = null;
  document.getElementById("btn-open-load-motd")?.addEventListener("click", function () {
    const current = document.getElementById("motd-text")?.value || "";
    document.getElementById("motd-load-text").value = current;
    document.querySelectorAll(".motd-tpl-btn").forEach(b => b.classList.remove("active"));
    _loadMotdModal = new bootstrap.Modal(document.getElementById("modal-load-motd"));
    _loadMotdModal.show();
  });
  document.querySelectorAll(".motd-tpl-btn").forEach(btn => {
    btn.addEventListener("click", function () {
      const tpl = _motdTplData.find(t => t.pk === parseInt(this.dataset.pk));
      if (tpl) document.getElementById("motd-load-text").value = tpl.text;
      document.querySelectorAll(".motd-tpl-btn").forEach(b => b.classList.remove("active"));
      this.classList.add("active");
    });
  });
  document.getElementById("btn-submit-load-motd")?.addEventListener("click", function () {
    const fleet = document.getElementById("btn-open-load-motd")?.dataset.fleet;
    if (!fleet) return;
    const url = U.setMotd.replace("/0/", "/" + fleet + "/");
    const motd = document.getElementById("motd-load-text").value;
    this.disabled = true;
    post(url, { motd }).then(r => {
      this.disabled = false;
      if (r.ok) {
        updateMotdDisplay(motd);
        const inline = document.getElementById("motd-text");
        if (inline) inline.value = motd;
        _loadMotdModal?.hide();
      } else alert(r.error);
    });
  });

  // ── Live member table ────────────────────────────────────────────────

  const ROLE_LABEL = { fleet_commander: "FC", wing_commander: "WC", squad_commander: "SC", squad_member: "Member" };
  const ROLE_COLOR = { fleet_commander: "danger", wing_commander: "warning", squad_commander: "info", squad_member: "secondary" };
  const isMyFleet = FLAGS.isMyFleet;
  const fleetPkForButtons = FLAGS.selectedFleetPk;
  const FLEET_HAS_FAT = FLAGS.fleetHasFat;
  const FLEET_HAS_SRP = FLAGS.fleetHasSrp;

  let dtMembers = null;

  function buildMemberRow(m, doctrineMatch) {
    const roleLabel = ROLE_LABEL[m.role] || m.role;
    const roleColor = ROLE_COLOR[m.role] || "secondary";
    const docCell = doctrinePk
      ? (doctrineMatch[String(m.character_id)]
          ? '<span class="badge bg-success"><i class="fas fa-check"></i></span>'
          : '<span class="badge bg-danger"><i class="fas fa-times"></i></span>')
      : "";
    const warpCell = m.takes_fleet_warp
      ? '<span class="text-muted small"><i class="fas fa-check"></i></span>'
      : `<span class="badge bg-warning text-dark" title="${I.noFleetWarp}"><i class="fas fa-ban"></i></span>`;
    const joinTime = m.join_time
      ? new Date(m.join_time).toISOString().slice(11, 16)
      : "";
    const actCell = isMyFleet
      ? `<td class="text-end text-nowrap">
          <button class="btn btn-sm btn-outline-warning btn-move-member me-1"
                  data-fleet="${fleetPkForButtons}" data-char="${m.character_id}" data-charname="${m.character_name}">
            <i class="fas fa-arrows-alt"></i>
          </button>
          <button class="btn btn-sm btn-outline-danger btn-kick-member"
                  data-fleet="${fleetPkForButtons}" data-char="${m.character_id}" data-charname="${m.character_name}">
            <i class="fas fa-times"></i>
          </button>
        </td>` : "";
    const dockedCell = m.station_id
      ? `<span class="badge bg-secondary" title="Station ID: ${m.station_id}"><i class="fas fa-anchor me-1"></i>${I.docked}</span>`
      : "";
    return `<tr>
      <td>${m.character_name}</td>
      <td>${m.ship_name}</td>
      <td>${m.system_name}</td>
      <td>${dockedCell}</td>
      <td><span class="badge bg-${roleColor}">${roleLabel}</span></td>
      <td><small class="text-muted">${m.wing_squad_label || ""}</small></td>
      <td>${warpCell}</td>
      <td>${docCell}</td>
      <td><small class="text-muted">${joinTime}</small></td>
      ${actCell}
    </tr>`;
  }

  function refreshMembersLive() {
    if (!fleetPk) return;
    let url = U.fleetMembersJson.replace("/0/", "/" + fleetPk + "/");
    if (doctrinePk) url += "?doctrine=" + doctrinePk;
    fetch(url)
      .then(r => r.json())
      .then(data => {
        if (!data.ok) return;

        // Fleet role counts (always)
        if (data.fleet_role_counts) {
          const rc = data.fleet_role_counts;
          for (const role of ["fleet_commander", "wing_commander", "squad_commander", "squad_member"]) {
            const el = document.getElementById("role-count-" + role);
            if (el) el.textContent = rc[role] || 0;
          }
          const tot = document.getElementById("total-count");
          if (tot) tot.textContent = data.member_count;
          const mb = document.getElementById("member-count-badge");
          if (mb) mb.textContent = data.member_count;
        }

        // Doctrine badge
        const dm = data.doctrine_match || {};
        const badge = document.querySelector(".on-doctrine-badge");
        if (badge && doctrinePk) {
          const onDoc = Object.values(dm).filter(Boolean).length;
          badge.innerHTML = `<i class="fas fa-check me-1"></i>${onDoc} / ${data.member_count} on-doctrine`;
          badge.classList.remove("d-none");
        }

        // Ship composition bars (always visible now)
        if (data.role_breakdown) {
          const rb = data.role_breakdown;
          for (const role of ["dps", "logi", "booster", "ewar", "other"]) {
            const d = rb[role] || {count: 0, pct: 0};
            const cEl = document.getElementById("comp-" + role + "-count");
            const pEl = document.getElementById("comp-" + role + "-pct");
            const bEl = document.getElementById("comp-" + role + "-bar");
            if (cEl) cEl.textContent = d.count;
            if (pEl) pEl.textContent = d.pct;
            if (bEl) bEl.style.width = d.pct + "%";
          }
        }

        // Composition graph (DPS / Logi over time)
        if (data.history) updateCompChart(data.history);

        // Rebuild member table
        const tbody = document.getElementById("member-tbody");
        if (!tbody) return;
        if (dtMembers) dtMembers.destroy();
        // Leave tbody empty when there are no members — DataTables renders its
        // own "no data" message. A colspan placeholder row would break the grid.
        tbody.innerHTML = data.members.length
          ? data.members.map(m => buildMemberRow(m, dm)).join("")
          : "";
        dtMembers = $("#tbl-members").DataTable({ pageLength: 50, order: [[3, "asc"]], stateSave: true, stateDuration: 300 });

        // Sync time + live indicator
        if (data.last_updated) {
          const syncEl = document.getElementById("sync-time");
          if (syncEl) syncEl.textContent = new Date(data.last_updated).toISOString().slice(11, 19);
        }
        const ind = document.getElementById("live-indicator");
        if (ind) { ind.style.color = "#0f0"; setTimeout(() => { ind.style.color = "#198754"; }, 500); }
      })
      .catch(() => {});
  }

  // Event delegation for kick/move
  let _moveMemberModal = null;
  let _moveFleet = null;
  let _moveChar = null;

  document.addEventListener("click", function (e) {
    const kickBtn = e.target.closest(".btn-kick-member");
    if (kickBtn) {
      if (!confirm(I.kickMember)) return;
      const url = U.kickMember.replace("/0/", "/" + kickBtn.dataset.fleet + "/");
      post(url, { character_id: kickBtn.dataset.char }).then(r => {
        if (r.ok) refreshMembersLive();
        else alert(r.error);
      });
      return;
    }
    const moveBtn = e.target.closest(".btn-move-member");
    if (moveBtn) {
      _moveFleet = moveBtn.dataset.fleet;
      _moveChar = moveBtn.dataset.char;
      document.getElementById("move-char-name").textContent = moveBtn.dataset.charname;
      _moveMemberModal = new bootstrap.Modal(document.getElementById("modal-move-member"));
      _moveMemberModal.show();
    }
  });
  document.getElementById("btn-submit-move")?.addEventListener("click", function () {
    const url = U.moveMember.replace("/0/", "/" + _moveFleet + "/");
    post(url, {
      character_id: _moveChar,
      role: document.getElementById("move-role").value,
      wing_id: document.getElementById("move-wing").value,
      squad_id: document.getElementById("move-squad").value,
    }).then(r => {
      if (r.ok) { _moveMemberModal?.hide(); reload(); }
      else alert(r.error);
    });
  });

  // Invite member
  let _inviteModal = null;
  let _inviteFleet = null;
  document.getElementById("btn-invite")?.addEventListener("click", function () {
    _inviteFleet = this.dataset.fleet;
    document.getElementById("invite-char-id").value = "";
    _inviteModal = new bootstrap.Modal(document.getElementById("modal-invite"));
    _inviteModal.show();
  });
  document.getElementById("btn-submit-invite")?.addEventListener("click", function () {
    const url = U.inviteMember.replace("/0/", "/" + _inviteFleet + "/");
    post(url, {
      character_id: document.getElementById("invite-char-id").value,
      role: document.getElementById("invite-role").value,
    }).then(r => {
      if (r.ok) { _inviteModal?.hide(); reload(); }
      else alert(I.inviteFailed + " " + r.error);
    });
  });

  // ── Wing management ───────────────────────────────────────────────────

  document.querySelectorAll(".btn-create-wing").forEach(btn => {
    btn.addEventListener("click", function () {
      const url = U.createWing.replace("/0/", "/" + this.dataset.fleet + "/");
      post(url, {}).then(r => { if (r.ok) reload(); else alert(r.error); });
    });
  });

  let _renameWingModal = null, _renameWingUrl = null;
  document.querySelectorAll(".btn-rename-wing").forEach(btn => {
    btn.addEventListener("click", function () {
      _renameWingUrl = this.dataset.url;
      document.getElementById("rename-wing-input").value = this.dataset.name;
      _renameWingModal = new bootstrap.Modal(document.getElementById("modal-rename-wing"));
      _renameWingModal.show();
    });
  });
  document.getElementById("btn-submit-rename-wing")?.addEventListener("click", function () {
    post(_renameWingUrl, { name: document.getElementById("rename-wing-input").value }).then(r => {
      if (r.ok) { _renameWingModal?.hide(); reload(); } else alert(r.error);
    });
  });

  document.querySelectorAll(".btn-delete-wing").forEach(btn => {
    btn.addEventListener("click", function () {
      if (!confirm(I.deleteWing)) return;
      post(this.dataset.url, {}).then(r => { if (r.ok) reload(); else alert(r.error); });
    });
  });

  // ── Squad management ──────────────────────────────────────────────────

  document.querySelectorAll(".btn-create-squad").forEach(btn => {
    btn.addEventListener("click", function () {
      post(this.dataset.url, {}).then(r => { if (r.ok) reload(); else alert(r.error); });
    });
  });

  let _renameSquadModal = null, _renameSquadUrl = null, _renameSquadWing = null;
  document.querySelectorAll(".btn-rename-squad").forEach(btn => {
    btn.addEventListener("click", function () {
      _renameSquadUrl = this.dataset.url;
      _renameSquadWing = this.dataset.wing;
      document.getElementById("rename-squad-input").value = this.dataset.name;
      _renameSquadModal = new bootstrap.Modal(document.getElementById("modal-rename-squad"));
      _renameSquadModal.show();
    });
  });
  document.getElementById("btn-submit-rename-squad")?.addEventListener("click", function () {
    post(_renameSquadUrl, { name: document.getElementById("rename-squad-input").value, wing_id: _renameSquadWing }).then(r => {
      if (r.ok) { _renameSquadModal?.hide(); reload(); } else alert(r.error);
    });
  });

  document.querySelectorAll(".btn-delete-squad").forEach(btn => {
    btn.addEventListener("click", function () {
      if (!confirm(I.deleteSquad)) return;
      post(this.dataset.url, {}).then(r => { if (r.ok) reload(); else alert(r.error); });
    });
  });

  // Apply Layout (button in fleet detail)
  let _applyLayoutModal = null;
  document.getElementById("btn-open-apply-layout")?.addEventListener("click", function () {
    document.getElementById("apply-layout-select").value = "";
    _applyLayoutModal = new bootstrap.Modal(document.getElementById("modal-apply-layout"));
    _applyLayoutModal.show();
  });
  document.getElementById("btn-submit-apply-layout")?.addEventListener("click", function () {
    const sel = document.getElementById("apply-layout-select");
    const layoutPk = sel.value;
    if (!layoutPk) { alert(I.selectLayout); return; }
    const tmplUrl = sel.options[sel.selectedIndex].dataset.url;
    const url = tmplUrl.replace("/0/", "/" + fleetPk + "/");
    this.disabled = true;
    post(url, {}).then(r => {
      this.disabled = false;
      if (r.ok) {
        _applyLayoutModal?.hide();
        if (r.warnings?.length) alert(I.doneWithWarnings + "\n" + r.warnings.join("\n"));
        reload();
      } else {
        alert(r.error || I.errorApplyingLayout);
      }
    }).catch(() => { this.disabled = false; alert(I.networkError); });
  });

  // ── Fleet name inline edit ───────────────────────────────────────────

  document.getElementById("btn-edit-fleet-name")?.addEventListener("click", function () {
    const display = document.getElementById("fleet-name-display");
    const current = display?.textContent.trim() === NO_NAME ? "" : (display?.textContent.trim() || "");
    const newName = prompt(I.fleetNamePrompt, current);
    if (newName === null) return;
    const url = U.setFleetName.replace("/0/", "/" + fleetPk + "/");
    post(url, { name: newName.trim() }).then(r => {
      if (r.ok) {
        if (display) {
          display.textContent = r.name || NO_NAME;
          display.style.color = r.name ? "" : "var(--bs-secondary)";
        }
      } else alert(r.error);
    });
  });

  function _getFleetName() {
    const el = document.getElementById("fleet-name-display");
    const raw = el?.textContent.trim() || "";
    return raw === NO_NAME ? "" : raw;
  }

  function _getSelectedDoctrineName() {
    const sel = document.getElementById("doctrine-select");
    if (!sel || !sel.value) return "";
    const opt = sel.options[sel.selectedIndex];
    // Strip trailing " (N ships)" or " (N fits)"
    return opt.text.replace(/\s*\(\d+.*?\)\s*$/, "").trim();
  }

  // ── FAT Link ─────────────────────────────────────────────────────────

  let _fatLinkModal = null;
  document.getElementById("btn-open-fat-link")?.addEventListener("click", function () {
    const ftName = _getSelectedFleetTypeName();
    if (!ftName) { alert(I.fleetTypeNotSelected); return; }
    document.getElementById("fat-link-result")?.classList.add("d-none");
    document.getElementById("fat-link-form-body")?.classList.remove("d-none");
    const footer = document.getElementById("fat-link-footer");
    if (footer) footer.style.display = "";
    // Reset to clickable
    const radio = document.getElementById("fat-type-clickable");
    if (radio) { radio.checked = true; document.getElementById("fat-link-duration-row")?.classList.remove("d-none"); }
    // Pre-fill from global selectors
    const nameEl = document.getElementById("fat-link-name");
    if (nameEl) nameEl.value = _getFleetName();
    const docEl = document.getElementById("fat-link-doctrine");
    if (docEl) docEl.value = _getSelectedDoctrineName();
    const ftDisplay = document.getElementById("fat-link-fleet-type-display");
    if (ftDisplay) ftDisplay.value = ftName;
    _fatLinkModal = new bootstrap.Modal(document.getElementById("modal-fat-link"));
    _fatLinkModal.show();
  });
  // Show/hide duration row based on link type
  document.querySelectorAll("input[name='fat-link-type']").forEach(r => {
    r.addEventListener("change", function () {
      const dRow = document.getElementById("fat-link-duration-row");
      if (dRow) dRow.classList.toggle("d-none", this.value === "esi");
    });
  });
  document.getElementById("btn-submit-fat-link")?.addEventListener("click", function () {
    const name = document.getElementById("fat-link-name")?.value.trim();
    if (!name) { alert(I.fleetNameRequired); return; }
    const linkType = document.querySelector("input[name='fat-link-type']:checked")?.value || "clickable";
    const url = U.createFatLink.replace("/0/", "/" + fleetPk + "/");
    const doctrineEl = document.getElementById("fat-link-doctrine");
    this.disabled = true;
    post(url, {
      name,
      link_type: linkType,
      fleet_type_name: document.getElementById("fat-link-fleet-type-display")?.value || "",
      doctrine_name: doctrineEl?.value || "",
      duration: document.getElementById("fat-link-duration")?.value || "60",
    }).then(r => {
      this.disabled = false;
      if (r.ok) {
        let fullUrl, titleText, msgText;
        if (r.link_type === "esi") {
          fullUrl = window.location.origin + r.details_url;
          titleText = I.esiFatCreated;
          msgText = I.esiFatMsg;
        } else {
          fullUrl = window.location.origin + r.register_url;
          titleText = I.fatCreated;
          msgText = I.fatMsg;
        }
        const titleEl = document.getElementById("fat-link-result-title");
        const msgEl = document.getElementById("fat-link-result-msg");
        const linkEl = document.getElementById("fat-link-url");
        if (titleEl) titleEl.textContent = titleText;
        if (msgEl) msgEl.textContent = msgText;
        if (linkEl) { linkEl.href = fullUrl; linkEl.textContent = fullUrl; }
        document.getElementById("fat-link-result")?.classList.remove("d-none");
        document.getElementById("fat-link-form-body")?.classList.add("d-none");
        const footer = document.getElementById("fat-link-footer");
        if (footer) footer.innerHTML = '<button type="button" class="btn btn-secondary" data-bs-dismiss="modal">' + I.close + '</button>';
      } else {
        alert(I.fatError + " " + r.error);
      }
    });
  });
  document.getElementById("btn-copy-fat-link")?.addEventListener("click", function () {
    const url = document.getElementById("fat-link-url")?.textContent;
    if (url) navigator.clipboard.writeText(url).then(() => {
      this.innerHTML = '<i class="fas fa-check"></i> ' + I.copied;
      setTimeout(() => { this.innerHTML = '<i class="fas fa-copy"></i> ' + I.copy; }, 2000);
    });
  });

  // ── SRP Link ─────────────────────────────────────────────────────────

  let _srpLinkModal = null;
  document.getElementById("btn-open-srp-link")?.addEventListener("click", function () {
    const ftName = _getSelectedFleetTypeName();
    if (!ftName) { alert(I.fleetTypeNotSelected); return; }
    document.getElementById("srp-link-result")?.classList.add("d-none");
    document.getElementById("srp-link-form-body")?.classList.remove("d-none");
    const footer = document.getElementById("srp-link-footer");
    if (footer) footer.style.display = "";
    // Pre-fill from global selectors
    const nameEl = document.getElementById("srp-link-name");
    if (nameEl) nameEl.value = _getFleetName();
    const docEl = document.getElementById("srp-link-doctrine");
    if (docEl) docEl.value = _getSelectedDoctrineName();
    const ftDisplay = document.getElementById("srp-link-fleet-type-display");
    if (ftDisplay) ftDisplay.value = ftName;
    _srpLinkModal = new bootstrap.Modal(document.getElementById("modal-srp-link"));
    _srpLinkModal.show();
  });
  document.getElementById("btn-submit-srp-link")?.addEventListener("click", function () {
    const srp_name = document.getElementById("srp-link-name")?.value.trim();
    const fleet_doctrine = document.getElementById("srp-link-doctrine")?.value.trim();
    if (!srp_name) { alert(I.srpNameRequired); return; }
    if (!fleet_doctrine) { alert(I.doctrineRequired); return; }
    const url = U.createSrpLink.replace("/0/", "/" + fleetPk + "/");
    this.disabled = true;
    post(url, {
      srp_name,
      fleet_doctrine,
      fleet_type_name: document.getElementById("srp-link-fleet-type-display")?.value || "",
      aar_link: document.getElementById("srp-link-aar")?.value.trim() || "",
    }).then(r => {
      this.disabled = false;
      if (r.ok) {
        const fullUrl = window.location.origin + r.request_url;
        const linkEl = document.getElementById("srp-link-url");
        if (linkEl) { linkEl.href = fullUrl; linkEl.textContent = fullUrl; }
        document.getElementById("srp-link-result")?.classList.remove("d-none");
        document.getElementById("srp-link-form-body")?.classList.add("d-none");
        const footer = document.getElementById("srp-link-footer");
        if (footer) footer.innerHTML = '<button type="button" class="btn btn-secondary" data-bs-dismiss="modal">' + I.close + '</button>';
      } else {
        alert(I.srpError + " " + r.error);
      }
    });
  });
  document.getElementById("btn-copy-srp-link")?.addEventListener("click", function () {
    const url = document.getElementById("srp-link-url")?.textContent;
    if (url) navigator.clipboard.writeText(url).then(() => {
      this.innerHTML = '<i class="fas fa-check"></i> ' + I.copied;
      setTimeout(() => { this.innerHTML = '<i class="fas fa-copy"></i> ' + I.copy; }, 2000);
    });
  });

  // ── Fleet Ping ───────────────────────────────────────────────────────

  let _fleetPingModal = null;
  function _buildPingPreview() {
    const tSel = document.getElementById("ping-fleet-type");
    const sSel = document.getElementById("ping-staging");
    const type = tSel?.options[tSel.selectedIndex]?.textContent.trim() || "—";
    const staging = sSel?.options[sSel.selectedIndex]?.dataset.system || "—";
    const note = document.getElementById("ping-note")?.value.trim() || "";
    const dash = "—";
    const yes = I.included;
    const lines = [
      I.lblFleetType + ": " + type,
      I.lblStaging + ": " + staging,
      I.lblDoctrine + ": Read MOTD",
      I.lblFatLink + ": " + (FLEET_HAS_FAT ? yes : dash),
      I.lblSrpLink + ": " + (FLEET_HAS_SRP ? yes : dash),
    ];
    if (note) lines.push(I.lblNote + ": " + note);
    const prev = document.getElementById("ping-preview");
    if (prev) prev.textContent = lines.join("\n");
  }
  document.getElementById("btn-open-fleet-ping")?.addEventListener("click", function () {
    // Pre-select the fleet type chosen in the header, if any.
    const headerPk = _getSelectedFleetTypePk();
    const pSel = document.getElementById("ping-fleet-type");
    if (pSel && headerPk) pSel.value = headerPk;
    document.getElementById("ping-note").value = "";
    _buildPingPreview();
    _fleetPingModal = new bootstrap.Modal(document.getElementById("modal-fleet-ping"));
    _fleetPingModal.show();
  });
  ["ping-fleet-type", "ping-staging", "ping-note"].forEach(id => {
    document.getElementById(id)?.addEventListener("input", _buildPingPreview);
    document.getElementById(id)?.addEventListener("change", _buildPingPreview);
  });
  document.getElementById("btn-submit-fleet-ping")?.addEventListener("click", function () {
    const typePk = document.getElementById("ping-fleet-type")?.value;
    if (!typePk) { alert(I.selectFleetType); return; }
    const url = U.sendFleetPing.replace("/0/", "/" + fleetPk + "/");
    this.disabled = true;
    post(url, {
      fleet_type_pk: typePk,
      staging_pk: document.getElementById("ping-staging")?.value || "",
      note: document.getElementById("ping-note")?.value.trim() || "",
      doctrine_name: _getSelectedDoctrineName(),
    }).then(r => {
      this.disabled = false;
      if (r.ok) {
        _fleetPingModal?.hide();
        this.innerHTML = '<i class="fas fa-check"></i> ' + I.sent;
      } else {
        alert(I.pingFailed + " " + r.error);
      }
    });
  });

}());
