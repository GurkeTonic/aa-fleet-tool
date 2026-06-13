/* Fleet Layouts page — layout / wing / squad CRUD. */
(function () {
  "use strict";

  const C = window.FT_PAGE || {};
  const U = C.urls || {};
  const I = C.i18n || {};

  let _newLayoutModal = null;
  document.getElementById("btn-new-layout")?.addEventListener("click", function () {
    document.getElementById("new-layout-name").value = "";
    document.getElementById("new-layout-desc").value = "";
    _newLayoutModal = new bootstrap.Modal(document.getElementById("modal-new-layout"));
    _newLayoutModal.show();
  });
  document.getElementById("btn-submit-new-layout")?.addEventListener("click", function () {
    const name = document.getElementById("new-layout-name").value.trim();
    if (!name) { alert(I.nameRequired); return; }
    ftPost(U.createLayout, {
      name, description: document.getElementById("new-layout-desc").value.trim(),
    }).then(r => { if (r.ok) { _newLayoutModal?.hide(); ftReload(); } else alert(r.error); });
  });
  document.querySelectorAll(".btn-delete-layout").forEach(btn => {
    btn.addEventListener("click", function () {
      if (!confirm(I.deleteLayout)) return;
      const url = U.deleteLayout.replace("/0/", "/" + this.dataset.pk + "/");
      ftPost(url, {}).then(r => { if (r.ok) ftReload(); else alert(r.error); });
    });
  });
  let _addLayoutWingPk = null, _addLayoutWingModal = null;
  document.querySelectorAll(".btn-add-layout-wing").forEach(btn => {
    btn.addEventListener("click", function () {
      _addLayoutWingPk = this.dataset.pk;
      document.getElementById("add-layout-wing-name").value = "";
      _addLayoutWingModal = new bootstrap.Modal(document.getElementById("modal-add-layout-wing"));
      _addLayoutWingModal.show();
    });
  });
  document.getElementById("btn-submit-add-layout-wing")?.addEventListener("click", function () {
    const name = document.getElementById("add-layout-wing-name").value.trim();
    if (!name) { alert(I.nameRequired); return; }
    const url = U.addLayoutWing.replace("/0/", "/" + _addLayoutWingPk + "/");
    ftPost(url, { name }).then(r => { if (r.ok) { _addLayoutWingModal?.hide(); ftReload(); } else alert(r.error); });
  });
  let _renameLayoutWingPk = null, _renameLayoutWingModal = null;
  document.querySelectorAll(".btn-rename-layout-wing").forEach(btn => {
    btn.addEventListener("click", function () {
      _renameLayoutWingPk = this.dataset.pk;
      document.getElementById("rename-layout-wing-name").value = this.dataset.name;
      _renameLayoutWingModal = new bootstrap.Modal(document.getElementById("modal-rename-layout-wing"));
      _renameLayoutWingModal.show();
    });
  });
  document.getElementById("btn-submit-rename-layout-wing")?.addEventListener("click", function () {
    const name = document.getElementById("rename-layout-wing-name").value.trim();
    if (!name) { alert(I.nameRequired); return; }
    const url = U.renameLayoutWing.replace("/0/", "/" + _renameLayoutWingPk + "/");
    ftPost(url, { name }).then(r => { if (r.ok) { _renameLayoutWingModal?.hide(); ftReload(); } else alert(r.error); });
  });
  document.querySelectorAll(".btn-delete-layout-wing").forEach(btn => {
    btn.addEventListener("click", function () {
      if (!confirm(I.deleteWing)) return;
      const url = U.deleteLayoutWing.replace("/0/", "/" + this.dataset.pk + "/");
      ftPost(url, {}).then(r => { if (r.ok) ftReload(); else alert(r.error); });
    });
  });
  let _addLayoutSquadWingPk = null, _addLayoutSquadModal = null;
  document.querySelectorAll(".btn-add-layout-squad").forEach(btn => {
    btn.addEventListener("click", function () {
      _addLayoutSquadWingPk = this.dataset.pk;
      document.getElementById("add-layout-squad-name").value = "";
      _addLayoutSquadModal = new bootstrap.Modal(document.getElementById("modal-add-layout-squad"));
      _addLayoutSquadModal.show();
    });
  });
  document.getElementById("btn-submit-add-layout-squad")?.addEventListener("click", function () {
    const name = document.getElementById("add-layout-squad-name").value.trim();
    if (!name) { alert(I.nameRequired); return; }
    const url = U.addLayoutSquad.replace("/0/", "/" + _addLayoutSquadWingPk + "/");
    ftPost(url, { name }).then(r => { if (r.ok) { _addLayoutSquadModal?.hide(); ftReload(); } else alert(r.error); });
  });
  let _renameLayoutSquadPk = null, _renameLayoutSquadModal = null;
  document.querySelectorAll(".btn-rename-layout-squad").forEach(btn => {
    btn.addEventListener("click", function () {
      _renameLayoutSquadPk = this.dataset.pk;
      document.getElementById("rename-layout-squad-name").value = this.dataset.name;
      _renameLayoutSquadModal = new bootstrap.Modal(document.getElementById("modal-rename-layout-squad"));
      _renameLayoutSquadModal.show();
    });
  });
  document.getElementById("btn-submit-rename-layout-squad")?.addEventListener("click", function () {
    const name = document.getElementById("rename-layout-squad-name").value.trim();
    if (!name) { alert(I.nameRequired); return; }
    const url = U.renameLayoutSquad.replace("/0/", "/" + _renameLayoutSquadPk + "/");
    ftPost(url, { name }).then(r => { if (r.ok) { _renameLayoutSquadModal?.hide(); ftReload(); } else alert(r.error); });
  });
  document.querySelectorAll(".btn-delete-layout-squad").forEach(btn => {
    btn.addEventListener("click", function () {
      if (!confirm(I.deleteSquad)) return;
      const url = U.deleteLayoutSquad.replace("/0/", "/" + this.dataset.pk + "/");
      ftPost(url, {}).then(r => { if (r.ok) ftReload(); else alert(r.error); });
    });
  });
}());
