/* MOTD Library page — shared + private template CRUD. */
(function () {
  "use strict";

  const C = window.FT_PAGE || {};
  const U = C.urls || {};
  const I = C.i18n || {};

  const _motdTplData = JSON.parse(document.getElementById("motd-tpl-data")?.textContent || "[]");
  let _newMotdTplModal = null;
  let _newIsPublic = false;

  document.querySelectorAll(".btn-new-motd").forEach(btn => {
    btn.addEventListener("click", function () {
      _newIsPublic = this.dataset.public === "true";
      document.getElementById("new-motd-tpl-name").value = "";
      document.getElementById("new-motd-tpl-text").value = "";
      document.getElementById("new-motd-scope").textContent = _newIsPublic ? I.scopeShared : I.scopePrivate;
      _newMotdTplModal = new bootstrap.Modal(document.getElementById("modal-new-motd-tpl"));
      _newMotdTplModal.show();
    });
  });
  document.getElementById("btn-submit-new-motd-tpl")?.addEventListener("click", function () {
    const name = document.getElementById("new-motd-tpl-name").value.trim();
    if (!name) { alert(I.nameRequired); return; }
    ftPost(U.createMotdTemplate, {
      name,
      text: document.getElementById("new-motd-tpl-text").value,
      is_public: _newIsPublic,
    }).then(r => { if (r.ok) { _newMotdTplModal?.hide(); ftReload(); } else alert(r.error); });
  });

  let _editMotdTplModal = null;
  document.querySelectorAll(".btn-edit-motd-tpl").forEach(btn => {
    btn.addEventListener("click", function () {
      const tpl = _motdTplData.find(t => t.pk === parseInt(this.dataset.pk));
      if (!tpl) return;
      document.getElementById("edit-motd-tpl-pk").value = tpl.pk;
      document.getElementById("edit-motd-tpl-name").value = tpl.name;
      document.getElementById("edit-motd-tpl-text").value = tpl.text;
      _editMotdTplModal = new bootstrap.Modal(document.getElementById("modal-edit-motd-tpl"));
      _editMotdTplModal.show();
    });
  });
  document.getElementById("btn-submit-edit-motd-tpl")?.addEventListener("click", function () {
    const pk = document.getElementById("edit-motd-tpl-pk").value;
    const name = document.getElementById("edit-motd-tpl-name").value.trim();
    if (!name) { alert(I.nameRequired); return; }
    const url = U.updateMotdTemplate.replace("/0/", "/" + pk + "/");
    ftPost(url, { name, text: document.getElementById("edit-motd-tpl-text").value })
      .then(r => { if (r.ok) { _editMotdTplModal?.hide(); ftReload(); } else alert(r.error); });
  });
  document.querySelectorAll(".btn-delete-motd-tpl").forEach(btn => {
    btn.addEventListener("click", function () {
      if (!confirm(I.deleteTemplate)) return;
      const url = U.deleteMotdTemplate.replace("/0/", "/" + this.dataset.pk + "/");
      ftPost(url, {}).then(r => { if (r.ok) ftReload(); });
    });
  });
}());
