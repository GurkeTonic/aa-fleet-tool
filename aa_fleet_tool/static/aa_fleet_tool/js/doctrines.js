/* Doctrines page — doctrine CRUD and SDE ship typeahead. */
(function () {
  "use strict";

  const C = window.FT_PAGE || {};
  const U = C.urls || {};
  const I = C.i18n || {};

  let _newDoctrineModal = null;
  document.getElementById("btn-new-doctrine")?.addEventListener("click", function () {
    _newDoctrineModal = new bootstrap.Modal(document.getElementById("modal-new-doctrine"));
    _newDoctrineModal.show();
  });
  document.getElementById("btn-submit-new-doctrine")?.addEventListener("click", function () {
    ftPost(U.createDoctrine, {
      name: document.getElementById("new-doctrine-name").value,
      description: document.getElementById("new-doctrine-desc").value,
    }).then(r => { if (r.ok) { _newDoctrineModal?.hide(); ftReload(); } else alert(r.error); });
  });
  document.querySelectorAll(".btn-delete-doctrine").forEach(btn => {
    btn.addEventListener("click", function () {
      if (!confirm(I.deleteDoctrine)) return;
      const url = U.deleteDoctrine.replace("/0/", "/" + this.dataset.pk + "/");
      ftPost(url, {}).then(r => { if (r.ok) ftReload(); });
    });
  });

  // Ship typeahead
  let _shipSearchTimer = null;
  const _shipSearchInput = document.getElementById("doctrine-ship-search");
  const _shipResultsDiv = document.getElementById("ship-search-results");
  if (_shipSearchInput) {
    _shipSearchInput.addEventListener("input", function () {
      clearTimeout(_shipSearchTimer);
      document.getElementById("doctrine-ship-type-id").value = "";
      document.getElementById("doctrine-ship-name").value = "";
      const q = this.value.trim();
      if (q.length < 2) { _shipResultsDiv.style.display = "none"; return; }
      _shipSearchTimer = setTimeout(() => {
        fetch(U.shipSearch + "?q=" + encodeURIComponent(q))
          .then(r => r.json())
          .then(data => {
            _shipResultsDiv.innerHTML = "";
            if (!data.results.length) { _shipResultsDiv.style.display = "none"; return; }
            data.results.forEach(ship => {
              const btn = document.createElement("button");
              btn.type = "button";
              btn.className = "list-group-item list-group-item-action py-1 small";
              btn.textContent = ship.name;
              btn.addEventListener("click", function () {
                _shipSearchInput.value = ship.name;
                document.getElementById("doctrine-ship-type-id").value = ship.type_id;
                document.getElementById("doctrine-ship-name").value = ship.name;
                _shipResultsDiv.style.display = "none";
              });
              _shipResultsDiv.appendChild(btn);
            });
            _shipResultsDiv.style.display = "block";
          });
      }, 300);
    });
  }
  document.addEventListener("click", function (e) {
    if (!e.target.closest("#modal-add-doctrine-ship") && _shipResultsDiv) _shipResultsDiv.style.display = "none";
  });

  let _addShipDocPk = null, _addShipModal = null;
  document.querySelectorAll(".btn-add-doctrine-ship").forEach(btn => {
    btn.addEventListener("click", function () {
      _addShipDocPk = this.dataset.pk;
      if (_shipSearchInput) _shipSearchInput.value = "";
      document.getElementById("doctrine-ship-type-id").value = "";
      document.getElementById("doctrine-ship-name").value = "";
      document.getElementById("add-ship-error").classList.add("d-none");
      if (_shipResultsDiv) _shipResultsDiv.style.display = "none";
      _addShipModal = new bootstrap.Modal(document.getElementById("modal-add-doctrine-ship"));
      _addShipModal.show();
    });
  });
  document.getElementById("btn-submit-add-ship")?.addEventListener("click", function () {
    const typeId = document.getElementById("doctrine-ship-type-id").value;
    const shipName = document.getElementById("doctrine-ship-name").value;
    const errDiv = document.getElementById("add-ship-error");
    if (!typeId) { errDiv.textContent = I.selectShip; errDiv.classList.remove("d-none"); return; }
    errDiv.classList.add("d-none");
    const url = U.addDoctrineShip.replace("/0/", "/" + _addShipDocPk + "/");
    ftPost(url, {
      ship_type_id: typeId, ship_name: shipName,
      role_hint: document.getElementById("doctrine-ship-role").value,
    }).then(r => {
      if (r.ok) { _addShipModal?.hide(); ftReload(); }
      else { errDiv.textContent = r.error || I.error; errDiv.classList.remove("d-none"); }
    });
  });
  document.querySelectorAll(".btn-remove-doctrine-ship").forEach(btn => {
    btn.addEventListener("click", function () {
      const url = U.removeDoctrineShip.replace("/0/", "/" + this.dataset.pk + "/");
      ftPost(url, {}).then(r => { if (r.ok) ftReload(); });
    });
  });
}());
