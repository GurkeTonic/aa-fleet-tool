/* Fleet Commanders page — Fleet Start/Stop, sync, remove FC. */
(function () {
  "use strict";

  const C = window.FT_PAGE || {};
  const U = C.urls || {};
  const I = C.i18n || {};

  document.getElementById("btn-sync")?.addEventListener("click", function () {
    ftPost(U.triggerSync, {}).then(() => {
      this.innerHTML = '<i class="fas fa-check"></i> ' + I.syncStarted;
      setTimeout(() => { this.innerHTML = '<i class="fas fa-sync"></i> ' + I.sync; }, 3000);
    });
  });
  document.querySelectorAll(".btn-start-fleet").forEach(btn => {
    btn.addEventListener("click", function () {
      this.disabled = true;
      ftPost(U.startFleet, { fc_pk: this.dataset.pk }).then(ftReload);
    });
  });
  document.querySelectorAll(".btn-stop-fleet").forEach(btn => {
    btn.addEventListener("click", function () {
      this.disabled = true;
      ftPost(U.stopFleet, { fc_pk: this.dataset.pk }).then(ftReload);
    });
  });
  document.querySelectorAll(".btn-remove-fc").forEach(btn => {
    btn.addEventListener("click", function () {
      if (!confirm(I.removeFc)) return;
      ftPost(U.removeFc, { fc_pk: this.dataset.pk }).then(ftReload);
    });
  });
  if (document.getElementById("tbl-commanders")) $("#tbl-commanders").DataTable({ pageLength: 25 });
}());
