/*
  Afarinick Tracker — frontend logic.

  Per the brief I built this with plain jQuery + AJAX against the JSON API, with no
  Django Forms involved: every form here is hand-written HTML in the template, and I
  gather values and POST them myself. I kept the code organised by resource
  (farmers, plots, harvests, import) so each feature is easy to follow.
*/
(function () {
  "use strict";

  var API = "/api";
  var farmersCache = [];
  var plotsCache = [];
  var map, markerLayer;

  // ---- tiny helpers -------------------------------------------------------
  function toast(msg, isErr) {
    var $t = $('<div class="toast"></div>').text(msg);
    if (isErr) $t.addClass("err");
    $("#toastStack").append($t);
    setTimeout(function () { $t.fadeOut(200, function () { $t.remove(); }); }, 3200);
  }

  // I centralise every API call here so error handling and JSON parsing are
  // consistent. It returns a jQuery promise.
  function api(method, path, body, isForm) {
    var opts = { url: API + path, method: method, dataType: "json" };
    if (body && isForm) {
      opts.data = body; opts.processData = false; opts.contentType = false;
    } else if (body) {
      opts.data = JSON.stringify(body); opts.contentType = "application/json";
    }
    return $.ajax(opts);
  }

  // I turn the API's {errors:{field:msg}} shape into inline messages under the
  // matching inputs, and fall back to a toast for anything unmapped.
  function showErrors($modal, errors) {
    $modal.find(".field").removeClass("invalid");
    var handled = {};
    $modal.find("[data-err]").each(function () {
      var key = $(this).data("err");
      if (errors[key]) {
        $(this).text(errors[key]).closest(".field").addClass("invalid");
        handled[key] = true;
      } else {
        $(this).text("");
      }
    });
    Object.keys(errors).forEach(function (k) {
      if (!handled[k]) toast(errors[k], true);
    });
  }
  function clearErrors($modal) {
    $modal.find(".field").removeClass("invalid");
    $modal.find("[data-err]").text("");
  }

  function openModal(id) { $("#" + id).addClass("open"); }
  function closeModal($el) { $el.removeClass("open"); }

  function fmt(n) {
    // I format kilograms with thousands separators and up to 2 decimals for a
    // clean, ledger-like readout.
    return Number(n).toLocaleString(undefined, { maximumFractionDigits: 2 });
  }

  // ---- overview cards -----------------------------------------------------
  function loadOverview() {
    api("GET", "/overview/").done(function (d) {
      $("#statFarmers").text(d.farmers);
      $("#statPlots").text(d.plots);
      $("#statHarvests").text(d.harvest_records);
      $("#statWeight").html(fmt(d.total_harvest_kg) + '<span class="unit">kg</span>');
    });
  }

  // ---- farmers ------------------------------------------------------------
  function loadFarmers() {
    return api("GET", "/farmers/").done(function (d) {
      farmersCache = d.results;
      renderFarmers();
      populateFarmerSelect();
    });
  }

  function renderFarmers() {
    var $body = $("#farmersTable tbody").empty();
    if (!farmersCache.length) {
      $body.html('<tr><td colspan="6"><div class="empty"><div class="big">No farmers yet</div>Register your first contracted farmer to get started.</div></td></tr>');
      return;
    }
    farmersCache.forEach(function (f) {
      var $tr = $("<tr>");
      $tr.append($('<td class="cell-strong">').attr("data-label", "Name").text(f.name));
      $tr.append($("<td>").attr("data-label", "Phone").text(f.phone_number));
      $tr.append($("<td>").attr("data-label", "Community").text(f.community));
      $tr.append($("<td>").attr("data-label", "Registered").text(f.date_registered));
      $tr.append($("<td>").attr("data-label", "Plots").text(f.plot_count));
      var $act = $('<div class="row-actions">');
      $act.append($('<button class="btn btn-ghost btn-sm">Edit</button>').on("click", function () { editFarmer(f); }));
      $act.append($('<button class="btn btn-danger-ghost btn-sm">Delete</button>').on("click", function () { deleteFarmer(f); }));
      $tr.append($('<td data-label="Actions">').append($act));
      $body.append($tr);
    });
  }

  function populateFarmerSelect() {
    var $sel = $("#pFarmer").empty();
    if (!farmersCache.length) {
      $sel.append('<option value="">— register a farmer first —</option>');
      return;
    }
    farmersCache.forEach(function (f) {
      $sel.append($("<option>").val(f.id).text(f.name + " · " + f.community));
    });
  }

  function openFarmerModal() {
    clearErrors($("#farmerModal"));
    $("#farmerId").val("");
    $("#fName,#fPhone,#fCommunity,#fDate").val("");
    $("#farmerModalTitle").text("Register farmer");
    openModal("farmerModal");
  }
  function editFarmer(f) {
    clearErrors($("#farmerModal"));
    $("#farmerId").val(f.id);
    $("#fName").val(f.name); $("#fPhone").val(f.phone_number);
    $("#fCommunity").val(f.community); $("#fDate").val(f.date_registered);
    $("#farmerModalTitle").text("Edit farmer");
    openModal("farmerModal");
  }
  function saveFarmer() {
    var id = $("#farmerId").val();
    var payload = {
      name: $("#fName").val(), phone_number: $("#fPhone").val(),
      community: $("#fCommunity").val()
    };
    if ($("#fDate").val()) payload.date_registered = $("#fDate").val();
    var req = id ? api("PUT", "/farmers/" + id + "/", payload) : api("POST", "/farmers/", payload);
    req.done(function () {
      closeModal($("#farmerModal"));
      toast(id ? "Farmer updated" : "Farmer registered");
      loadFarmers(); loadOverview();
    }).fail(function (xhr) {
      showErrors($("#farmerModal"), (xhr.responseJSON && xhr.responseJSON.errors) || { detail: "Something went wrong." });
    });
  }
  function deleteFarmer(f) {
    if (!confirm('Delete "' + f.name + '"? This also removes their plots and harvests.')) return;
    api("DELETE", "/farmers/" + f.id + "/").done(function () {
      toast("Farmer deleted");
      loadFarmers(); loadPlots(); loadOverview();
    });
  }

  // ---- plots --------------------------------------------------------------
  function loadPlots() {
    return api("GET", "/plots/").done(function (d) {
      plotsCache = d.results;
      renderPlots();
      renderMap();
    });
  }

  function renderPlots() {
    var $body = $("#plotsTable tbody").empty();
    if (!plotsCache.length) {
      $body.html('<tr><td colspan="6"><div class="empty"><div class="big">No plots yet</div>Register a plot to start logging harvests.</div></td></tr>');
      return;
    }
    plotsCache.forEach(function (p) {
      var $tr = $("<tr>");
      $tr.append($('<td class="cell-strong cell-mono">').attr("data-label", "Plot code").text(p.plot_code));
      $tr.append($("<td>").attr("data-label", "Farmer").text(p.farmer_name));
      $tr.append($("<td>").attr("data-label", "Size (ha)").text(p.size_hectares));
      $tr.append($("<td>").attr("data-label", "Variety").text(p.cocoa_variety || "—"));
      $tr.append($("<td>").attr("data-label", "Harvests").text(p.harvest_count));
      var $act = $('<div class="row-actions">');
      $act.append($('<button class="btn btn-gold btn-sm">Log harvest</button>').on("click", function () { openHarvestModal(p); }));
      $act.append($('<button class="btn btn-ghost btn-sm">Summary</button>').on("click", function () { openSummary(p); }));
      $act.append($('<button class="btn btn-ghost btn-sm">Edit</button>').on("click", function () { editPlot(p); }));
      $act.append($('<button class="btn btn-danger-ghost btn-sm">Delete</button>').on("click", function () { deletePlot(p); }));
      $tr.append($('<td data-label="Actions">').append($act));
      $body.append($tr);
    });
  }

  function openPlotModal() {
    clearErrors($("#plotModal"));
    if (!farmersCache.length) { toast("Please register a farmer first.", true); return; }
    $("#plotId").val("");
    $("#pCode,#pSize,#pVariety,#pLat,#pLng").val("");
    $("#locStatus").text("");
    $("#plotModalTitle").text("Register plot");
    openModal("plotModal");
  }
  function editPlot(p) {
    clearErrors($("#plotModal"));
    $("#locStatus").text("");
    $("#plotId").val(p.id);
    $("#pFarmer").val(p.farmer_id);
    $("#pCode").val(p.plot_code); $("#pSize").val(p.size_hectares);
    $("#pVariety").val(p.cocoa_variety || "");
    $("#pLat").val(p.latitude != null ? p.latitude : "");
    $("#pLng").val(p.longitude != null ? p.longitude : "");
    $("#plotModalTitle").text("Edit plot");
    openModal("plotModal");
  }
  function savePlot() {
    var id = $("#plotId").val();
    var payload = {
      farmer_id: $("#pFarmer").val(), plot_code: $("#pCode").val(),
      size_hectares: $("#pSize").val(), cocoa_variety: $("#pVariety").val(),
      latitude: $("#pLat").val(), longitude: $("#pLng").val()
    };
    var req = id ? api("PUT", "/plots/" + id + "/", payload) : api("POST", "/plots/", payload);
    req.done(function () {
      closeModal($("#plotModal"));
      toast(id ? "Plot updated" : "Plot registered");
      loadPlots(); loadFarmers(); loadOverview();
    }).fail(function (xhr) {
      showErrors($("#plotModal"), (xhr.responseJSON && xhr.responseJSON.errors) || { detail: "Something went wrong." });
    });
  }
  function deletePlot(p) {
    if (!confirm('Delete plot "' + p.plot_code + '"? This also removes its harvest records.')) return;
    api("DELETE", "/plots/" + p.id + "/").done(function () {
      toast("Plot deleted");
      loadPlots(); loadFarmers(); loadOverview();
    });
  }

  // ---- harvests -----------------------------------------------------------
  function openHarvestModal(p) {
    clearErrors($("#harvestModal"));
    $("#harvestPlotId").val(p.id);
    $("#harvestPlotLabel").text("Plot " + p.plot_code + " · " + p.farmer_name);
    $("#hDate").val(new Date().toISOString().slice(0, 10));
    $("#hWeight").val(""); $("#hGrade").val("A");
    openModal("harvestModal");
  }
  function saveHarvest() {
    var payload = {
      plot_id: $("#harvestPlotId").val(),
      harvest_date: $("#hDate").val(),
      weight_kg: $("#hWeight").val(),
      quality_grade: $("#hGrade").val()
    };
    api("POST", "/harvests/", payload).done(function () {
      closeModal($("#harvestModal"));
      toast("Harvest logged");
      loadPlots(); loadOverview();
    }).fail(function (xhr) {
      showErrors($("#harvestModal"), (xhr.responseJSON && xhr.responseJSON.errors) || { detail: "Something went wrong." });
    });
  }

  // ---- summary + prediction ----------------------------------------------
  function openSummary(p) {
    $("#summaryTitle").text("Plot " + p.plot_code + " — summary");
    $("#sumTotal,#sumCount,#sumAvg,#predVal").text("…");
    $("#predMethod").text("");
    openModal("summaryModal");
    api("GET", "/plots/" + p.id + "/summary/").done(function (s) {
      $("#sumTotal").text(fmt(s.total_harvest_weight_kg) + " kg");
      $("#sumCount").text(s.harvest_record_count);
      $("#sumAvg").text(fmt(s.average_weight_per_harvest_kg) + " kg");
    });
    api("GET", "/plots/" + p.id + "/predict/").done(function (pr) {
      if (pr.estimated_next_harvest_kg == null) {
        $("#predVal").text("No history yet");
        $("#predMethod").text(pr.note || "");
      } else {
        $("#predVal").text(fmt(pr.estimated_next_harvest_kg) + " kg");
        var label = pr.method === "linear_trend" ? "Linear trend over " + pr.based_on_records + " records"
          : pr.method === "single_record_carry_forward" ? "Carried forward from 1 record"
          : pr.method;
        $("#predMethod").text(label + (pr.historical_average_kg != null ? " · avg " + fmt(pr.historical_average_kg) + " kg" : ""));
      }
    });
  }

  // ---- CSV / Excel import -------------------------------------------------
  function bindImport() {
    var $file = $("#importFile"), $zone = $("#dropzone");
    $("#chooseFileBtn").on("click", function () { $file.trigger("click"); });
    $file.on("change", function () {
      if (this.files.length) {
        $("#chosenName").text("Selected: " + this.files[0].name);
        $("#uploadBtn").prop("disabled", false);
      }
    });
    // I support drag-and-drop as well as the picker; it's a nicer field-officer UX.
    ["dragenter", "dragover"].forEach(function (e) {
      $zone.on(e, function (ev) { ev.preventDefault(); $zone.addClass("drag"); });
    });
    ["dragleave", "drop"].forEach(function (e) {
      $zone.on(e, function (ev) { ev.preventDefault(); $zone.removeClass("drag"); });
    });
    $zone.on("drop", function (ev) {
      var files = ev.originalEvent.dataTransfer.files;
      if (files.length) {
        $file[0].files = files;
        $("#chosenName").text("Selected: " + files[0].name);
        $("#uploadBtn").prop("disabled", false);
      }
    });
    $("#uploadBtn").on("click", uploadImport);
  }

  function uploadImport() {
    var file = $("#importFile")[0].files[0];
    if (!file) return;
    var fd = new FormData();
    fd.append("file", file);
    $("#uploadBtn").prop("disabled", true).text("Importing…");
    api("POST", "/harvests/import/", fd, true).always(function (res, status, xhr) {
      $("#uploadBtn").prop("disabled", false).text("Upload & import");
      var data = res && res.created !== undefined ? res : (res.responseJSON || {});
      if (data.errors) { renderImportError(data.errors); return; }
      renderImportReport(data);
      loadPlots(); loadOverview();
    });
  }

  function renderImportError(errors) {
    var msg = errors.file || errors.detail || "Import failed.";
    $("#importReport").html('<div class="pill pill-fail">' + msg + "</div>");
  }

  function renderImportReport(d) {
    var html = '<div class="report-line">';
    html += '<span class="pill pill-ok">' + d.created + " created</span>";
    html += '<span class="pill ' + (d.failed ? "pill-fail" : "pill-ok") + '">' + d.failed + " failed</span>";
    html += '<span class="pill" style="background:var(--parchment);color:var(--muted)">' + d.total_rows + " rows read</span>";
    html += "</div>";
    if (d.failures && d.failures.length) {
      html += '<div class="table-wrap"><table class="data fail-table"><thead><tr><th>Row</th><th>Why it failed</th></tr></thead><tbody>';
      d.failures.forEach(function (f) {
        html += "<tr><td data-label='Row' class='cell-mono'>" + f.row + "</td><td data-label='Why it failed'>" + f.errors.join(" ") + "</td></tr>";
      });
      html += "</tbody></table></div>";
    }
    if (d.created) toast(d.created + " harvest record(s) imported");
    $("#importReport").html(html);
  }

  // ---- map (GIS bonus) ----------------------------------------------------
  function renderMap() {
    var located = plotsCache.filter(function (p) { return p.latitude != null && p.longitude != null; });
    if (!map) {
      // I centre the map on the Volta Region (Kpando area) where Afarinick's
      // plantation sits, so an empty map still shows the right place.
      map = L.map("map", { scrollWheelZoom: false }).setView([7.0, 0.35], 9);
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 18, attribution: "&copy; OpenStreetMap contributors"
      }).addTo(map);
      markerLayer = L.layerGroup().addTo(map);
    }
    markerLayer.clearLayers();
    var bounds = [];
    located.forEach(function (p) {
      var m = L.marker([p.latitude, p.longitude]).bindPopup(
        "<b>" + p.plot_code + "</b><br>" + p.farmer_name + "<br>" + p.size_hectares + " ha" +
        (p.cocoa_variety ? "<br>" + p.cocoa_variety : "")
      );
      markerLayer.addLayer(m);
      bounds.push([p.latitude, p.longitude]);
    });
    if (bounds.length) map.fitBounds(bounds, { padding: [40, 40], maxZoom: 12 });
    // I invalidate size after the panel becomes visible so Leaflet renders tiles
    // correctly even though the map started inside a hidden-ish container.
    setTimeout(function () { map.invalidateSize(); }, 100);
  }

  // ---- geolocation (auto-fill a plot's coordinates from the device GPS) ------
  function captureLocation() {
    var $status = $("#locStatus");
    if (!navigator.geolocation) {
      $status.text("Geolocation isn't supported on this device.");
      return;
    }
    var $btn = $("#useLocationBtn").prop("disabled", true);
    $status.text("Locating…");
    navigator.geolocation.getCurrentPosition(
      function (pos) {
        // I round to 5 decimal places (~1 metre), which is plenty for a plot marker.
        $("#pLat").val(pos.coords.latitude.toFixed(5));
        $("#pLng").val(pos.coords.longitude.toFixed(5));
        var acc = Math.round(pos.coords.accuracy);
        $status.text("Captured (±" + acc + " m accuracy)");
        $btn.prop("disabled", false);
      },
      function (err) {
        // I surface the reason (denied, unavailable, timeout) so the user knows
        // whether to retry or just type the coordinates by hand.
        $status.text("Couldn't get location: " + err.message);
        $btn.prop("disabled", false);
      },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
    );
  }

  // ---- wiring -------------------------------------------------------------
  function bindTabs() {
    $(".tab").on("click", function () {
      $(".tab").removeClass("active");
      $(this).addClass("active");
      $(".panel").removeClass("active");
      $("#panel-" + $(this).data("tab")).addClass("active");
      if ($(this).data("tab") === "plots" && map) setTimeout(function () { map.invalidateSize(); }, 60);
    });
  }
  function bindModals() {
    $("[data-close]").on("click", function () { closeModal($(this).closest(".modal-backdrop")); });
    $(".modal-backdrop").on("click", function (e) { if (e.target === this) closeModal($(this)); });
    $(document).on("keydown", function (e) { if (e.key === "Escape") $(".modal-backdrop.open").removeClass("open"); });

    $("#addFarmerBtn").on("click", openFarmerModal);
    $("#saveFarmerBtn").on("click", saveFarmer);
    $("#addPlotBtn").on("click", openPlotModal);
    $("#savePlotBtn").on("click", savePlot);
    $("#useLocationBtn").on("click", captureLocation);
    $("#saveHarvestBtn").on("click", saveHarvest);
  }

  $(function () {
    bindTabs();
    bindModals();
    bindImport();
    loadOverview();
    loadFarmers();
    loadPlots();
  });
})();
