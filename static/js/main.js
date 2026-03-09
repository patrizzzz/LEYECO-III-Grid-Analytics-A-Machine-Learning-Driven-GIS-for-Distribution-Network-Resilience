document.addEventListener('DOMContentLoaded', function () {
  const mapEl = document.getElementById('map');
  if (!mapEl) {
    console.warn('main.js: #map element not found.');
    return;
  }

  function showMapError(msg) {
    mapEl.innerHTML = '<div style="padding:2rem;text-align:center;color:#666;">' + msg + '</div>';
    mapEl.style.background = '#f8f9fa';
    console.error('Map init:', msg);
  }

  // Leaflet must be loaded before we use L
  if (typeof L === 'undefined') {
    showMapError('Map library failed to load. Check your connection or try again.');
    return;
  }

  if (window._mapInstance) {
    setTimeout(function () { try { window._mapInstance.invalidateSize(); } catch (e) { } }, 100);
    return;
  }

  // Base Layers (Defined outside try block for scope access)
  const osmLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '© OpenStreetMap contributors',
  });

  const satelliteLayer = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
    attribution: 'Tiles © Esri — Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community'
  });

  const terrainLayer = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}', {
    attribution: 'Tiles © Esri — Esri, DeLorme, NAVTEQ, TomTom, Intermap, iPC, USGS, FAO, NPS, NRCAN, GeoBase, Kadaster NL, Ordnance Survey, Esri Japan, METI, Esri China (Hong Kong), and the GIS User Community'
  });

  var map;
  try {
    map = L.map(mapEl).setView([12.8797, 121.7740], 6);
    window._mapInstance = map;

    // If a specific post location was passed via URL params, remember it
    const targetLat = window._targetLat;
    const targetLng = window._targetLng;
    const targetPostId = window._targetPostId;
    if (Number.isFinite(targetLat) && Number.isFinite(targetLng)) {
      map.setView([targetLat, targetLng], 15); // Zoom to level 15 for post location
    }

    // Default to OSM
    osmLayer.addTo(map);

    try { map._container.style.borderRadius = '8px'; } catch (e) { }
    try { map._container.style.boxShadow = '0 4px 6px -1px rgba(0,0,0,0.1)'; } catch (e) { }
  } catch (err) {
    showMapError('Map could not start: ' + (err.message || err));
    return;
  }

  const postsLayer = L.layerGroup();
  const latlongLayer = L.layerGroup();
  const connectionsLayer = L.layerGroup();
  const networkLinesLayer = L.layerGroup();

  // Maps and Bounds - Must be defined here
  const postMarkers = {}; // map post_id -> marker
  const busToPostMap = {}; // map bus_id -> post data
  const poleToPostMap = {}; // map pole_number -> post data
  const bounds = L.latLngBounds();

  const baseLayers = {
    'Standard': osmLayer,
    'Satellite': satelliteLayer,
    'Terrain': terrainLayer
  };

  const overlays = {
    'Posts (canonical)': postsLayer,
    'LatLongData (raw)': latlongLayer,
    'Network lines (DB)': networkLinesLayer
  };

  // --- Global Line Color State ---
  let globalLineColor = localStorage.getItem('globalLineColor') || null;
  let usePhasingColor = localStorage.getItem('usePhasingColor') === 'true' || false;

  // --- Feeder filter state ---
  let knownFeeders = new Set();
  let activeFeeders = new Set(); // feeders currently visible – starts with all enabled

  // --- Phase filter state ---
  // Categories: '1' (Single Phase), '2' (Double Phase), '3' (Three Phase), '0' (Other/Unknown)
  let activePhaseCategories = new Set(['1', '2', '3', '0']);

  // --- Line Type filter state ---
  let activeLineTypes = new Set(['primary', 'transformer', 'secondary', 'service_drop', 'unknown']);

  // --- Transformer filter state ---
  let activeTransformersOnly = false;

  // --- Analysis Cache ---
  window._mlRiskMap = {};
  window._loadStressMap = {};

  const _allPostMarkers = []; // keeps references to ALL markers even when removed from layer
  let feederList = null; // Scoped for applyFeederFilter

  function applyFeederFilter() {
    // Show all when: no feeders known, OR "Show All" checkbox is checked, OR we haven't built the UI yet (initial load)
    const showAllCb = feederList ? feederList.querySelector('.msp-feeder-all input') : null;
    const showAllFeeds = (knownFeeders.size === 0) || (showAllCb ? showAllCb.checked : true);

    // Engineers want to see "lines only" when posts are hidden.
    // Virtual nodes and customers are markers, so we hide them if postsLayer is off.
    const postsVisible = map.hasLayer(postsLayer);

    _allPostMarkers.forEach(function (marker) {
      if (!marker._postData) return;
      const f = String(marker._postData.feeder || '').trim();
      const shouldShowFeeder = showAllFeeds || activeFeeders.has(f);

      // Transformer Filter
      const hasTransformer = marker._postData.kva_rating != null && marker._postData.kva_rating !== '';
      const shouldShowTransformer = !activeTransformersOnly || hasTransformer;

      const shouldShow = shouldShowFeeder && shouldShowTransformer;

      if (shouldShow) {
        if (!postsLayer.hasLayer(marker)) postsLayer.addLayer(marker);
      } else {
        if (postsLayer.hasLayer(marker)) postsLayer.removeLayer(marker);
      }
    });

    // Ensure networkLinesLayer is on map so its content is visible
    if (!map.hasLayer(networkLinesLayer)) networkLinesLayer.addTo(map);

    const allLines = [];
    networkLinesLayer.eachLayer(function (layer) { allLines.push(layer); });
    if (!window._hiddenNetworkLines) window._hiddenNetworkLines = [];
    const allNetLines = allLines.concat(window._hiddenNetworkLines);
    window._hiddenNetworkLines = [];

    allNetLines.forEach(function (layer) {
      if (layer instanceof L.Polyline) {
        // Feeder Check
        const f = String(layer._feederName || '').trim();
        const isFeederVisible = showAllFeeds || activeFeeders.has(f);

        // Phase Check
        let isPhaseVisible = true;
        // Check if all phases are active (size 4), otherwise filter
        if (activePhaseCategories.size < 4) {
          const pStr = String(layer.phasingType || '').toUpperCase().trim();
          // Count unique phases (A, B, C)
          let distinctPhases = 0;
          if (pStr.includes('A')) distinctPhases++;
          if (pStr.includes('B')) distinctPhases++;
          if (pStr.includes('C')) distinctPhases++;

          // Determine category
          let category = '0'; // default Other
          if (distinctPhases === 1) category = '1';
          else if (distinctPhases === 2) category = '2';
          else if (distinctPhases === 3) category = '3';

          isPhaseVisible = activePhaseCategories.has(category);
        }

        // Line Type Check
        const lType = layer.lineCategory || 'unknown';
        const isLineTypeVisible = activeLineTypes.has(lType);

        if (isFeederVisible && isPhaseVisible && isLineTypeVisible) {
          if (!networkLinesLayer.hasLayer(layer)) networkLinesLayer.addLayer(layer);
        } else {
          if (networkLinesLayer.hasLayer(layer)) networkLinesLayer.removeLayer(layer);
          window._hiddenNetworkLines.push(layer);
        }
      } else if (layer instanceof L.Marker) {
        // Feeder Check for Virtual Nodes / Customers
        const f = String(layer._feederName || '').trim();
        const isFeederVisible = showAllFeeds || activeFeeders.has(f);

        if (isFeederVisible && postsVisible) {
          if (!networkLinesLayer.hasLayer(layer)) networkLinesLayer.addLayer(layer);
        } else {
          if (networkLinesLayer.hasLayer(layer)) networkLinesLayer.removeLayer(layer);
          window._hiddenNetworkLines.push(layer);
        }
      }
    });
  }

  // Expose function so it can be called after data loads
  window._refreshFeederList = function () { };

  // --- Unified Map Settings (Sidebar) ---
  const sidebarSettingsContainer = document.getElementById('sidebar-map-settings');
  const sidebarSettingsWrapper = document.getElementById('sidebar-map-settings-wrapper');
  const sidebarToggle = document.getElementById('sidebar-map-settings-toggle');

  if (sidebarToggle && sidebarSettingsWrapper) {
    sidebarToggle.addEventListener('click', function (e) {
      e.preventDefault();
      const isVisible = sidebarSettingsWrapper.style.display !== 'none';
      sidebarSettingsWrapper.style.display = isVisible ? 'none' : '';
      const arrow = sidebarToggle.querySelector('.sidebar-msp-arrow');
      if (arrow) arrow.classList.toggle('expanded', !isVisible);
    });
  }

  // Build settings sections inside the sidebar
  if (sidebarSettingsContainer) {
    // === Section 1: Base Map ===
    const baseSection = document.createElement('div');
    baseSection.className = 'msp-section';
    baseSection.innerHTML = '<div class="msp-section-title">Base Map</div>';
    const baseList = document.createElement('div');
    baseList.className = 'msp-option-list';

    let currentBase = 'Standard';
    Object.keys(baseLayers).forEach(function (name) {
      const row = document.createElement('label');
      row.className = 'msp-option';
      const radio = document.createElement('input');
      radio.type = 'radio';
      radio.name = 'base-map';
      radio.checked = name === 'Standard';
      radio.addEventListener('change', function () {
        if (this.checked) {
          if (currentBase && baseLayers[currentBase]) map.removeLayer(baseLayers[currentBase]);
          baseLayers[name].addTo(map);
          currentBase = name;
        }
      });
      const span = document.createElement('span');
      span.textContent = name;
      row.appendChild(radio);
      row.appendChild(span);
      baseList.appendChild(row);
    });
    baseSection.appendChild(baseList);

    // === Section 2: Layers ===
    const layerSection = document.createElement('div');
    layerSection.className = 'msp-section';
    layerSection.innerHTML = '<div class="msp-section-title">Layers</div>';
    const layerList = document.createElement('div');
    layerList.className = 'msp-option-list';

    const layerDefaults = {
      'Posts (canonical)': true,
      'LatLongData (raw)': false,
      'Network lines (DB)': true
    };

    Object.keys(overlays).forEach(function (name) {
      const row = document.createElement('label');
      row.className = 'msp-option';
      const cb = document.createElement('input');
      cb.type = 'checkbox';
      const isOn = layerDefaults[name] !== false;
      cb.checked = isOn;
      if (isOn) overlays[name].addTo(map);
      cb.addEventListener('change', function () {
        if (this.checked) { overlays[name].addTo(map); }
        else { map.removeLayer(overlays[name]); }

        // If Posts or Network lines toggle, re-run filter to sync virtual nodes
        applyFeederFilter();
      });
      const span = document.createElement('span');
      span.textContent = name;
      row.appendChild(cb);
      row.appendChild(span);
      layerList.appendChild(row);
    });
    layerSection.appendChild(layerList);

    // === Section 3: Feeder Filter ===
    const feederSection = document.createElement('div');
    feederSection.className = 'msp-section';
    feederSection.innerHTML = '<div class="msp-section-title">Feeder Filter</div>';
    feederList = document.createElement('div');
    feederList.className = 'msp-option-list msp-feeder-list';
    feederList.innerHTML = '<span class="msp-hint">Loading feeders…</span>';
    feederSection.appendChild(feederList);

    // Refresh feeder list after post data is loaded
    window._refreshFeederList = function () {
      if (!feederList) return;
      const showAllWasChecked = feederList.querySelector('.msp-feeder-all input') ? feederList.querySelector('.msp-feeder-all input').checked : true;

      feederList.innerHTML = '';
      if (knownFeeders.size === 0) {
        feederList.innerHTML = '<span class="msp-hint">No feeders found</span>';
        return;
      }
      // "Show All" option
      const allRow = document.createElement('label');
      allRow.className = 'msp-option msp-feeder-all';
      const allCb = document.createElement('input');
      allCb.type = 'checkbox';
      allCb.checked = showAllWasChecked;
      const allSpan = document.createElement('span');
      allSpan.textContent = 'Show All';
      allSpan.style.fontWeight = '600';
      allRow.appendChild(allCb);
      allRow.appendChild(allSpan);
      feederList.appendChild(allRow);

      const feederCbs = [];
      const sortedFeeders = Array.from(knownFeeders).sort();
      sortedFeeders.forEach(function (fname) {
        // Automatically activate new feeders if "Show All" is checked
        if (showAllWasChecked && !activeFeeders.has(fname)) {
          activeFeeders.add(fname);
        }

        const row = document.createElement('label');
        row.className = 'msp-option';
        const cb = document.createElement('input');
        cb.type = 'checkbox';
        cb.checked = activeFeeders.has(fname);
        cb.dataset.feeder = fname;
        cb.addEventListener('change', function () {
          if (this.checked) { activeFeeders.add(fname); }
          else { activeFeeders.delete(fname); }
          // Sync "Show All"
          allCb.checked = activeFeeders.size === knownFeeders.size;
          applyFeederFilter();
        });
        const span = document.createElement('span');
        span.textContent = fname;
        row.appendChild(cb);
        row.appendChild(span);
        feederList.appendChild(row);
        feederCbs.push(cb);
      });

      allCb.addEventListener('change', function () {
        feederCbs.forEach(function (cb) {
          cb.checked = allCb.checked;
          if (allCb.checked) { activeFeeders.add(cb.dataset.feeder); }
          else { activeFeeders.delete(cb.dataset.feeder); }
        });
        applyFeederFilter();
      });
    };

    // === Section 3.5: Phase Filter ===
    const phaseSection = document.createElement('div');
    phaseSection.className = 'msp-section';
    phaseSection.innerHTML = '<div class="msp-section-title">Phase Filter</div>';
    const phaseList = document.createElement('div');
    phaseList.className = 'msp-option-list';

    const phases = [
      { id: '1', label: 'Single Phase' },
      { id: '2', label: 'Double Phase' },
      { id: '3', label: 'Three Phase' },
      { id: '0', label: 'Other' }
    ];

    phases.forEach(function (p) {
      const row = document.createElement('label');
      row.className = 'msp-option';
      const cb = document.createElement('input');
      cb.type = 'checkbox';
      cb.checked = activePhaseCategories.has(p.id);
      cb.addEventListener('change', function () {
        if (this.checked) activePhaseCategories.add(p.id);
        else activePhaseCategories.delete(p.id);
        applyFeederFilter(); // Re-run filter logic
      });
      const span = document.createElement('span');
      span.textContent = p.label;
      row.appendChild(cb);
      row.appendChild(span);
      phaseList.appendChild(row);
    });
    phaseSection.appendChild(phaseList);

    // === Section 3.6: Line Type Filter ===
    const lineTypeSection = document.createElement('div');
    lineTypeSection.className = 'msp-section';
    lineTypeSection.innerHTML = '<div class="msp-section-title">Line Type Filter</div>';
    const lineTypeList = document.createElement('div');
    lineTypeList.className = 'msp-option-list';

    const allLineCb = document.createElement('input');
    allLineCb.type = 'checkbox';
    allLineCb.checked = true;

    const allLineRow = document.createElement('label');
    allLineRow.className = 'msp-option';
    allLineRow.innerHTML = '<span><strong style="color:#0056b3;">Show All</strong></span>';
    allLineRow.prepend(allLineCb);
    lineTypeList.appendChild(allLineRow);

    const lineTypes = [
      { id: 'primary', label: 'Primary / Distribution Line' },
      { id: 'secondary', label: 'Secondary Line' }
    ];

    const ltCheckboxes = [];

    lineTypes.forEach(function (lt) {
      const row = document.createElement('label');
      row.className = 'msp-option';

      const cb = document.createElement('input');
      cb.type = 'checkbox';
      cb.dataset.linetype = lt.id;
      cb.checked = activeLineTypes.has(lt.id);
      ltCheckboxes.push(cb);

      cb.addEventListener('change', function () {
        if (this.checked) activeLineTypes.add(lt.id);
        else activeLineTypes.delete(lt.id);

        allLineCb.checked = ltCheckboxes.every(c => c.checked);
        applyFeederFilter();
      });

      const span = document.createElement('span');
      span.textContent = lt.label;

      row.appendChild(cb);
      row.appendChild(span);
      lineTypeList.appendChild(row);
    });

    allLineCb.addEventListener('change', function () {
      const isChecked = this.checked;
      ltCheckboxes.forEach(cb => {
        cb.checked = isChecked;
        if (isChecked) activeLineTypes.add(cb.dataset.linetype);
        else activeLineTypes.delete(cb.dataset.linetype);
      });
      if (isChecked) activeLineTypes.add('unknown');
      else activeLineTypes.delete('unknown');
      applyFeederFilter();
    });

    lineTypeSection.appendChild(lineTypeList);

    // === Section 3.7: Transformer Filter ===
    const transFilterSection = document.createElement('div');
    transFilterSection.className = 'msp-section';
    transFilterSection.innerHTML = '<div class="msp-section-title">Analysis Filters</div>';
    const transFilterList = document.createElement('div');
    transFilterList.className = 'msp-option-list';

    const transRow = document.createElement('label');
    transRow.className = 'msp-option';
    const transCb = document.createElement('input');
    transCb.type = 'checkbox';
    transCb.checked = activeTransformersOnly;
    transCb.addEventListener('change', function () {
      activeTransformersOnly = this.checked;
      applyFeederFilter();
    });
    const transSpan = document.createElement('span');
    transSpan.innerHTML = 'Show Transformers Only <img src="/static/img/transformer_pole.svg" style="width:14px;height:14px;vertical-align:middle;margin-left:4px;">';
    transRow.appendChild(transCb);
    transRow.appendChild(transSpan);
    transFilterList.appendChild(transRow);
    transFilterSection.appendChild(transFilterList);

    // === Section 4: Visualization ===
    const vizSection = document.createElement('div');
    vizSection.className = 'msp-section';
    vizSection.innerHTML = '<div class="msp-section-title">Visualization</div>';

    // Global color picker row
    const colorRow = document.createElement('div');
    colorRow.className = 'msp-color-row';

    const colorLabel = document.createElement('span');
    colorLabel.textContent = 'Line Color';
    colorLabel.className = 'msp-color-label';

    const colorInput = document.createElement('input');
    colorInput.type = 'color';
    colorInput.className = 'msp-color-input';
    colorInput.value = globalLineColor || '#000000';

    const resetBtn = document.createElement('button');
    resetBtn.className = 'msp-reset-btn';
    resetBtn.textContent = '✕';
    resetBtn.title = 'Reset to default';
    resetBtn.style.display = globalLineColor ? '' : 'none';

    colorRow.appendChild(colorLabel);
    colorRow.appendChild(colorInput);
    colorRow.appendChild(resetBtn);

    // Phasing toggle row
    const phasingRow = document.createElement('label');
    phasingRow.className = 'msp-option';

    const phasingCb = document.createElement('input');
    phasingCb.type = 'checkbox';
    phasingCb.id = 'phasing-color-toggle';
    phasingCb.checked = usePhasingColor;

    const phasingSpan = document.createElement('span');
    phasingSpan.textContent = 'Color by Phasing';
    phasingSpan.style.flex = '1';

    const helpIcon = document.createElement('span');
    helpIcon.className = 'msp-help-icon';
    helpIcon.textContent = '?';
    helpIcon.title = 'Color lines by electrical phase:\nPhase A = Brown\nPhase B = Black\nPhase C = Gray\nMulti-phase = Purple';

    phasingRow.appendChild(phasingCb);
    phasingRow.appendChild(phasingSpan);
    phasingRow.appendChild(helpIcon);

    vizSection.appendChild(colorRow);
    vizSection.appendChild(phasingRow);

    // Event handlers for visualization controls
    colorInput.addEventListener('input', function (e) {
      globalLineColor = e.target.value;
      localStorage.setItem('globalLineColor', globalLineColor);
      resetBtn.style.display = '';
      updateNetworkLineColors();
    });

    resetBtn.addEventListener('click', function (e) {
      e.preventDefault();
      globalLineColor = null;
      localStorage.removeItem('globalLineColor');
      colorInput.value = '#000000';
      resetBtn.style.display = 'none';
      updateNetworkLineColors();
    });

    phasingCb.addEventListener('change', function () {
      usePhasingColor = this.checked;
      localStorage.setItem('usePhasingColor', usePhasingColor);
      updateNetworkLineColors();
    });

    // Assemble all sections into sidebar settings container
    sidebarSettingsContainer.appendChild(baseSection);
    sidebarSettingsContainer.appendChild(layerSection);
    sidebarSettingsContainer.appendChild(feederSection);
    sidebarSettingsContainer.appendChild(phaseSection);
    sidebarSettingsContainer.appendChild(lineTypeSection);
    sidebarSettingsContainer.appendChild(transFilterSection);
    sidebarSettingsContainer.appendChild(vizSection);
  }

  // Force Leaflet to measure container and load tiles (fixes blank map)
  function refreshMapSize() {
    try { map.invalidateSize(); } catch (e) { }
  }
  refreshMapSize();
  map.whenReady(refreshMapSize);
  setTimeout(refreshMapSize, 150);
  setTimeout(refreshMapSize, 600);
  window.addEventListener('resize', refreshMapSize);

  // Fetch current user info and apply client-side UI rules (also enforced on the server)
  window._currentUser = null;
  fetch('/auth/whoami').then(r => r.json()).then(info => {
    if (info && info.authenticated && info.user) {
      window._currentUser = info.user;
      if (info.user.role !== 'admin') {
        const connBtns = document.querySelectorAll('.connection-control .conn-btn');
        connBtns.forEach(b => { try { b.disabled = true; } catch (e) { } });
      }
    }
  }).catch(() => { });

  // Custom electrical-post icon
  const poleIcon = L.icon({
    iconUrl: '/static/img/pole.svg',
    iconSize: [55, 70],
    iconAnchor: [28, 61],
    popupAnchor: [0, -68],
    tooltipAnchor: [0, -44],
    className: 'pole-icon'
  });

  const transformerPoleIcon = L.icon({
    iconUrl: '/static/img/transformer_pole.svg',
    iconSize: [60, 80],
    iconAnchor: [30, 72],
    popupAnchor: [0, -72],
    tooltipAnchor: [0, -55],
    className: 'pole-icon transformer-pole-icon'
  });

  const customerIcon = L.divIcon({
    className: '',
    html: '<div style="background-color:#FF3366; width:12px; height:12px; border-radius:50%; border:2px solid white; box-shadow: 0 0 4px rgba(0,0,0,0.5);"></div>',
    iconSize: [16, 16],
    iconAnchor: [8, 8]
  });

  const virtualNodeIcon = L.divIcon({
    className: '',
    html: '<div style="background-color:#FF9900; width:10px; height:10px; border-radius:50%; border:2px solid white; box-shadow: 0 0 3px rgba(0,0,0,0.5);"></div>',
    iconSize: [14, 14],
    iconAnchor: [7, 7]
  });

  // Connection editing state
  let connectionMode = false;
  let connectionPoints = []; // {post_id, lat, lng}
  let connectionPolyline = null;

  // Layer for connection endpoint markers (small circles placed exactly at numeric coords)
  const endpointsLayer = L.layerGroup().addTo(map);
  // Keep references to endpoint markers for the live editing connection
  let liveEndpointMarkers = [];

  function clearLiveEndpoints() {
    liveEndpointMarkers.forEach(m => endpointsLayer.removeLayer(m));
    liveEndpointMarkers = [];
  }

  function addLiveEndpoint(lat, lng) {
    // Non-interactive endpoint marker so clicks pass through to the polyline underneath
    const m = L.circleMarker([lat, lng], { radius: 6, color: '#ff6600', fillColor: '#fff', weight: 2, interactive: false }).addTo(endpointsLayer);
    liveEndpointMarkers.push(m);
    return m;
  }

  // Clear all map layers (posts, connections, lines)
  function clearAllMapLayers() {
    postsLayer.clearLayers();
    connectionsLayer.clearLayers();
    networkLinesLayer.clearLayers();
    latlongLayer.clearLayers();
    Object.keys(postMarkers).forEach(key => delete postMarkers[key]);
    Object.keys(busToPostMap).forEach(key => delete busToPostMap[key]);
    Object.keys(poleToPostMap).forEach(key => delete poleToPostMap[key]);
    liveEndpointMarkers = [];
    console.log('✓ All map layers cleared');
  }

  // Reload all map data (posts, connections, network geometry) - called after import
  function reloadMapData() {
    console.log('🔄 Reloading map data...');
    clearAllMapLayers();

    // Reload posts, connections, and network geometry with slight delays for sequencing
    setTimeout(function () {
      loadPosts();
    }, 100);

    setTimeout(function () {
      // loadLineConnections(); // DEPRECATED: network-geometry endpoint now handles all connections with filtering support
      loadNetworkGeometry();
    }, 1500);
  }

  // Make it globally accessible for resources page
  window.reloadMapData = reloadMapData;

  // Delete all data from backend (posts, connections, network lines, raw data) and reset IDs
  // Delete all data
  function deleteAllData() {
    return showConfirmModal('⚠️ DELETE ALL DATA?\n\nThis will permanently delete:\n- All posts/poles\n- All connections\n- All network lines\n- All raw coordinates\n\nIDs will reset to 1. This cannot be undone!', {
      title: 'DANGER: Delete All Data',
      okText: 'DELETE EVERYTHING',
      cancelText: 'Cancel'
    }).then(confirmed => {
      if (!confirmed) return { success: false, message: 'Cancelled by user' };

      console.log('Starting deleteAllData request...');
      return fetch('/api/data/delete-all', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      })
        .then(r => {
          if (!r.ok) {
            return r.json().then(data => {
              throw new Error(`Server error (${r.status}): ${data.message || data.error || 'Unknown error'}`);
            });
          }
          return r.json();
        })
        .then(data => {
          if (data.result === 'success') {
            console.log('✓ Backend: All data deleted');
            clearAllMapLayers();
            return { success: true, message: data.message };
          } else {
            return { success: false, message: data.message || 'Unknown error' };
          }
        })
        .catch(err => {
          return { success: false, message: err.message || 'API error' };
        });
    });
  }

  // Delete button handler
  const deleteBtn = document.getElementById('delete-data-btn');
  if (deleteBtn) {
    deleteBtn.addEventListener('click', function (e) {
      e.preventDefault();
      deleteBtn.disabled = true;
      deleteAllData().then(result => {
        deleteBtn.disabled = false;
        if (result.success) {
          showNoticeModal('Success', '✅ ' + result.message);
        } else if (result.message !== 'Cancelled by user') {
          showNoticeModal('Error', '❌ ' + result.message);
        }
      }).catch(err => {
        deleteBtn.disabled = false;
        showNoticeModal('Error', '❌ Error: ' + err);
      });
    });
  }

  function formatMeters(m) {
    if (m >= 1000) return (m / 1000).toFixed(2) + ' km';
    return Math.round(m) + ' m';
  }

  // Track current base layer for adaptive styling
  let currentBaseLayer = 'Standard';

  map.on('baselayerchange', function (e) {
    currentBaseLayer = e.name;
    updateNetworkLineColors();
  });

  // Helper function to determine line color based on Circuit field and Map Layer
  function getLineColor(circuit, phasing) {
    // 1. Phasing Color Mode (Philippine IEC Standard) - High Priority
    if (usePhasingColor && phasing) {
      const p = String(phasing).toUpperCase().trim();
      const hasA = p.includes('A');
      const hasB = p.includes('B');
      const hasC = p.includes('C');

      // Single phase colors
      if (hasA && !hasB && !hasC) return '#8B4513'; // Brown (Phase A only)
      if (hasB && !hasA && !hasC) return '#000000'; // Black (Phase B only)
      if (hasC && !hasA && !hasB) return '#808080'; // Gray (Phase C only)

      // Multi-phase (anything with 2 or 3 phases)
      if ((hasA && hasB) || (hasB && hasC) || (hasC && hasA)) {
        return '#800080'; // Purple for multi-phase
      }

      // Fallback if phasing exists but doesn't match patterns
      return '#666666';
    }

    // 0. Global Override
    if (globalLineColor) return globalLineColor;

    // 2. Satellite Mode: Use bright/neon colors for visibility on dark imagery
    if (currentBaseLayer === 'Satellite') {
      if (!circuit) return '#dddddd';
      const normalizedCircuit = String(circuit).trim().toLowerCase();
      if (normalizedCircuit === '3 phase') return '#00ff00';      // Neon Green
      if (normalizedCircuit === 'single phase') return '#ff3333'; // Bright Red
      if (normalizedCircuit === 'v phase') return '#00ffff';      // Cyan
      return '#dddddd';
    }

    // 3. Standard / Terrain Mode: Use darker, standard colors
    if (!circuit) return '#999'; // Default gray
    const normalizedCircuit = String(circuit).trim().toLowerCase();
    if (normalizedCircuit === '3 phase') return '#228B22'; // Forest Green
    if (normalizedCircuit === 'single phase') return '#d63031'; // Red
    if (normalizedCircuit === 'v phase') return '#0984e3'; // Blue
    return '#999';
  }

  function updateNetworkLineColors() {
    function updateLayer(layer) {
      if (layer instanceof L.Polyline) {
        const color = getLineColor(layer.circuitType, layer.phasingType);
        layer.setStyle({ color: color });
      }
    }
    networkLinesLayer.eachLayer(updateLayer);
    connectionsLayer.eachLayer(updateLayer);
  }

  function haversine(lat1, lon1, lat2, lon2) {
    const R = 6371000; // meters
    const toRad = (deg) => deg * Math.PI / 180;
    const dLat = toRad(lat2 - lat1);
    const dLon = toRad(lon2 - lon1);
    const a = Math.sin(dLat / 2) * Math.sin(dLat / 2) + Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) * Math.sin(dLon / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    return R * c;
  }

  // Helper to add markers to a layer
  function addPostMarker(layer, p) {
    const lat = parseFloat(p.lat);
    const lng = parseFloat(p.lng);
    if (Number.isNaN(lat) || Number.isNaN(lng)) return;

    const hasTransformer = p.kva_rating != null && p.kva_rating !== '';
    const currentIcon = hasTransformer ? transformerPoleIcon : poleIcon;

    let tooltipHtml = `ID: ${p.id}`;
    let healthClass = '';
    let riskInfo = null;
    let stressInfo = null;
    let healthHtml = '';

    if (hasTransformer) {
      tooltipHtml += ` <img src="/static/img/transformer_pole.svg" style="width:18px;height:24px;vertical-align:middle;margin-left:4px;" title="Transformer Pole">`;

      // Look up analysis data using various possible IDs
      const lookupIds = [p.pole_number, p.primary_bus_id, p.id];
      for (const id of lookupIds) {
        if (!id) continue;
        if (window._mlRiskMap && window._mlRiskMap[id]) riskInfo = window._mlRiskMap[id];
        if (window._loadStressMap && window._loadStressMap[id]) stressInfo = window._loadStressMap[id];
      }

      if (riskInfo) {
        const rl = (riskInfo.risk_level || '').toLowerCase();
        if (rl === 'critical') healthClass = 'health-critical';
        else if (rl === 'high') healthClass = 'health-high';
        else healthClass = 'health-normal';
      } else if (stressInfo) {
        const st = (stressInfo.status || '').toLowerCase();
        if (st === 'overloaded') healthClass = 'health-critical';
        else if (st === 'high load') healthClass = 'health-high';
        else healthClass = 'health-normal';
      } else {
        healthClass = 'health-normal';
      }

      // Build Health Info HTML with color-coded border
      let borderCol = 'var(--success)';
      if (healthClass === 'health-critical') borderCol = 'var(--danger)';
      else if (healthClass === 'health-high') borderCol = 'var(--warning)';

      healthHtml = `
        <div class="popup-health-summary" style="margin: 8px 0; padding: 8px; background: rgba(0,0,0,0.03); border-radius: 6px; border-left: 3px solid ${borderCol};">
          <div style="font-weight:700; font-size:0.8rem; margin-bottom:4px;">
            ${riskInfo ? `Impact Rank: #${riskInfo.impact_rank}` : 'Transformer Health'}
          </div>
          ${riskInfo ? `
            <div style="font-size:0.75rem;">Impact Level: <strong style="color:${borderCol}">${riskInfo.risk_level}</strong></div>
            <div style="font-size:0.75rem;">Impact Score: <strong>${riskInfo.impact_score}</strong></div>
            <div style="font-size:0.75rem;">Customers Served: <strong>${riskInfo.customer_count || 0}</strong></div>
            <div style="font-size:0.75rem; margin-top:4px; opacity:0.8;">Technical Anomaly Risk: ${riskInfo.risk_score}%</div>
            <div style="font-size:0.75rem; opacity:0.8;">Load: ${riskInfo.load_status} (${riskInfo.utilization_percent}%)</div>
          ` : (stressInfo ? `
            <div style="font-size:0.75rem;">Load: <strong>${stressInfo.load_status}</strong> (${stressInfo.utilization_percent}%)</div>
          ` : '<div style="font-size:0.75rem; color:var(--success);">Status: Healthy / Normal</div>')}
        </div>
      `;
    }

    const popupHtml = `
      <div class="post-popup-container">
        <div class="post-popup-tabs">
            <button class="tab-link active" data-tab="General-${p.id}">General</button>
            <button class="tab-link" data-tab="Connections-${p.id}">Connections</button>
            <button class="tab-link" data-tab="Assets-${p.id}">Assets</button>
        </div>

        <div id="General-${p.id}" class="tab-content" style="display: block;">
            <div class="popup-post-details">
              <strong>${(p.name || 'Post ' + p.id).replace(/</g, '&lt;')}</strong>${(p.kva_rating != null && p.kva_rating !== '') ? ' <img src="/static/img/transformer_pole.svg" style="width:18px;height:18px;vertical-align:middle;margin-left:4px;" title="Transformer Pole">' : ''}<br>
              Feeder: ${(p.feeder || 'N/A').replace(/</g, '&lt;')}<br>
              Status: ${(p.status || 'N/A').replace(/</g, '&lt;')}<br>
              Coordinates: ${lat.toFixed(6)}, ${lng.toFixed(6)}<br>
              ID: ${p.id}
            </div>
            ${healthHtml}
            <div class="popup-connect-actions">
                <button class="btn btn-outline btn-street-view" data-lat="${lat}" data-lng="${lng}" data-post-id="${p.id}" title="Open Street View">
                  <svg xmlns="http://www.w3.org/2000/svg" height="14" width="14" viewBox="0 -960 960 960" fill="currentColor"><path d="M480-80q-83 0-156-31.5T197-197q-54-54-85.5-127T80-480q0-83 31.5-156T197-763q54-54 127-85.5T480-880q83 0 156 31.5T763-763q54 54 85.5 127T880-480q0 83-31.5 156T763-197q-54 54-127 85.5T480-80Zm-40-82v-78q-33 0-56.5-23.5T360-320v-40L168-552q-3 18-5.5 36t-2.5 36q0 121 79.5 212T440-162Zm276-102q27-35 43.5-76t22.5-86H640v40q0 33 23.5 56.5T720-306v42Z"/></svg>
                  Street View
                </button>
                <button class="btn btn-outline primary-line-overhead-btn" data-post-id="${p.id}">Primary overhead</button>
                <button class="btn btn-outline distribution-transformer-btn" data-post-id="${p.id}">Dist. Transformer</button>
                <button class="btn btn-secondary trace-downstream-btn" data-bus-id="${p.primary_bus_id || p.pole_number}">
                  <svg xmlns="http://www.w3.org/2000/svg" height="14" width="14" viewBox="0 -960 960 960" fill="currentColor"><path d="M480-120 300-300l56-56 124 124 124-124 56 56-180 180ZM240-240v-480h480v480H240Zm80-80h320v-320H320v320Zm-80-480h480-480Z"/></svg>
                  Trace
                </button>
                <button class="btn btn-danger simulate-outage-btn" data-bus-id="${p.primary_bus_id || p.pole_number}">
                  <svg xmlns="http://www.w3.org/2000/svg" height="14" width="14" viewBox="0 -960 960 960" fill="currentColor"><path d="M480-80 310-250l57-57 113 113 113-113 57 57-170 170Zm0-160L310-410l57-57 113 113 113-113 57 57-170 170Zm0-160L310-570l113-113L310-796l57-57 170 170-170 171-57-57 113-113-113-113 113-113 113 113Zm0-160-57-57 57-57 57 57-57 57Z"/></svg>
                  Outage
                </button>
            </div>
        </div>

        <div id="Connections-${p.id}" class="tab-content" style="display: none;">
             <div class="popup-connect-actions">
                <button class="btn btn-outline secondary-lines-btn" data-post-id="${p.id}">Sec. Lines</button>
                <button class="btn btn-outline service-drop-btn" data-post-id="${p.id}">Service Drop</button>
                <button class="btn btn-outline full-width-btn btn-show-connections" data-post-id="${p.id}">View Connections</button>
            </div>
        </div>

        <div id="Assets-${p.id}" class="tab-content" style="display: none;">
            <div class="popup-connect-actions">
              <button class="btn btn-outline voltage-regulator-btn" data-post-id="${p.id}">Regulator</button>
              <button class="btn btn-outline shunt-capacitor-btn" data-post-id="${p.id}">Capacitor</button>
              <button class="btn btn-outline shunt-inductor-btn" data-post-id="${p.id}">Inductor</button>
              <button class="btn btn-outline series-inductor-btn" data-post-id="${p.id}">Inductor</button>
            </div>
        </div>
      </div>
    `;

    const markerOptions = { title: p.name || `Post ${p.id}`, icon: currentIcon };
    if (healthClass) {
      // We append the health class to the icon's class list
      markerOptions.className = (markerOptions.className || '') + ' ' + healthClass;
    }

    const marker = L.marker([lat, lng], markerOptions)
      .bindPopup(popupHtml, { maxWidth: 400, minWidth: 280 });

    marker.bindTooltip(tooltipHtml, { permanent: false, direction: 'top' });

    // Store post data on marker for later access (connections, etc.)
    marker._postData = p;

    // keep a reference for selection / bulk operations
    try { postMarkers[p.id] = marker; } catch (e) { }

    // Also store in lookup maps for connection drawing
    if (p.pole_number) {
      poleToPostMap[p.pole_number] = p;
      busToPostMap[p.pole_number] = p; // Primary bus is usually the pole number
    }
    if (p.feeder) {
      knownFeeders.add(String(p.feeder).trim());
    }
    // Consistently index by primary_bus_id for tracing highlights
    if (p.primary_bus_id) {
      busToPostMap[p.primary_bus_id] = p;
    }

    // Also store in lookup maps for connection drawing
    marker.addTo(layer);
    _allPostMarkers.push(marker);

    // Ensure only one tooltip is visible at a time to prevent overlap
    marker.on('mouseover', function () {
      try {
        if (window._lastTooltipMarker && window._lastTooltipMarker !== marker) {
          window._lastTooltipMarker.closeTooltip();
        }
      } catch (e) { }
      try { marker.openTooltip(); } catch (e) { }
      window._lastTooltipMarker = marker;
    });

    // Small delay on mouseout to avoid flicker when moving between nearby markers
    marker.on('mouseout', function () {
      setTimeout(function () {
        try { marker.closeTooltip(); } catch (e) { }
        if (window._lastTooltipMarker === marker) window._lastTooltipMarker = null;
      }, 250);
    });
    bounds.extend([lat, lng]);

    // support connection mode: click marker to add to connection
    marker.on('click', function (e) {
      // If selection mode is active, toggle selection instead of normal connection flow
      if (window._selectionMode) {
        toggleSelect(p.id, lat, lng, marker);
        return;
      }

      if (connectionMode) {
        addPointToConnection({ post_id: p.id, lat: lat, lng: lng });
      }
    });

    // Attach popup button handlers on popupopen
    marker.on('popupopen', function () {
      const popupEl = marker.getPopup().getElement();
      if (!popupEl) return;

      // Tab switching logic
      const tabLinks = popupEl.querySelectorAll('.tab-link');
      const tabContents = popupEl.querySelectorAll('.tab-content');
      tabLinks.forEach(link => {
        link.addEventListener('click', function (e) {
          e.preventDefault();
          e.stopPropagation();
          // Hide all separate tabs
          tabContents.forEach(c => c.style.display = 'none');
          tabLinks.forEach(l => l.classList.remove('active'));
          // Show target
          const targetId = this.getAttribute('data-tab');
          const target = popupEl.querySelector('#' + targetId);
          if (target) target.style.display = 'block';
          this.classList.add('active');
        });
      });

      // Street View button: open Google Maps Street View at this post's coordinates
      const streetViewBtn = popupEl.querySelector('.btn-street-view');
      if (streetViewBtn) {
        streetViewBtn.onclick = function (e) {
          e.preventDefault();
          e.stopPropagation();
          const svLat = streetViewBtn.getAttribute('data-lat');
          const svLng = streetViewBtn.getAttribute('data-lng');
          if (!svLat || !svLng) return;

          // Google Maps Street View URL (opens directly in Street View mode)
          const streetViewUrl = `https://www.google.com/maps/@${svLat},${svLng},3a,80y,0h,90t/data=!3m4!1e1!3m2!1s!2e0`;

          // Open in new tab — Google blocks iframe embedding of Maps
          window.open(streetViewUrl, '_blank', 'noopener');
        };
      }

      // Primary line-overhead button: show modal with technical data
      const primaryLineBtn = popupEl.querySelector('.primary-line-overhead-btn');
      if (primaryLineBtn) {
        primaryLineBtn.onclick = function () {
          const postId = primaryLineBtn.getAttribute('data-post-id');
          if (!postId) return;

          fetch('/api/posts/' + postId)
            .then(function (r) { return r.json(); })
            .then(function (postData) {
              if (postData && postData.error) return;

              var poleId = postData.pole_number;
              if (!poleId) {
                showNoticeModal('Info', 'No pole ID found for this post to fetch primary line data.');
                return;
              }

              fetch('/api/primary-lines/by-bus/' + encodeURIComponent(poleId))
                .then(function (r) { return r.json(); })
                .then(function (result) {
                  if (result && result.error) {
                    showNoticeModal('Error', 'Error: ' + result.error);
                    return;
                  }
                  if (!result.primary_lines || result.primary_lines.length === 0) {
                    showNoticeModal('Info', 'No primary line found connected to Pole ID: ' + poleId);
                    return;
                  }
                  showPrimaryLineOverheadModal(result.primary_lines[0]);
                })
                .catch(function (err) {
                  showNoticeModal('Error', 'Failed to load primary line data: ' + (err && err.message ? err.message : String(err)));
                });
            })
            .catch(function () { });
        };
      }

      // Distribution Transformer button: fetch transformer by bus_id
      const transformerBtn = popupEl.querySelector('.distribution-transformer-btn');
      if (transformerBtn) {
        transformerBtn.onclick = function () {
          const postId = transformerBtn.getAttribute('data-post-id');
          if (!postId) return;
          // First get post to find primary_bus_id
          fetch('/api/posts/' + postId)
            .then(function (r) { return r.json(); })
            .then(function (postData) {
              if (postData && postData.error) return;
              var poleId = postData.pole_number;
              if (!poleId) {
                showNoticeModal('Info', 'No pole ID found for this post');
                return;
              }
              fetch('/api/transformers/by-bus/' + encodeURIComponent(poleId))
                .then(function (r) { return r.json(); })
                .then(function (result) {
                  if (result && result.error) {
                    showNoticeModal('Error', 'Error: ' + result.error);
                    return;
                  }
                  if (!result.transformers || result.transformers.length === 0) {
                    showNoticeModal('Info', 'No transformer found for bus ID: ' + busId);
                    return;
                  }
                  // Show first transformer (or all if multiple)
                  showDistributionTransformerModal(result.transformers[0]);
                })
                .catch(function (err) {
                  showNoticeModal('Error', 'Failed to load transformer: ' + (err && err.message ? err.message : String(err)));
                });
            })
            .catch(function () { });
        };
      }

      // Secondary Lines button: fetch lines via Transformer's secondary bus ID
      const secondaryLinesBtn = popupEl.querySelector('.secondary-lines-btn');
      if (secondaryLinesBtn) {
        secondaryLinesBtn.onclick = function () {
          const postId = secondaryLinesBtn.getAttribute('data-post-id');
          if (!postId) return;

          // 1. Get Post Details to find Primary Bus ID
          fetch('/api/posts/' + postId)
            .then(function (r) { return r.json(); })
            .then(function (postData) {
              if (postData && postData.error) return;

              var primaryBusId = postData.primary_bus_id || postData.pole_number;
              if (!primaryBusId) {
                showNoticeModal('Info', 'No primary bus ID found for this post.');
                return;
              }

              // 2. Find Transformer connected to this Primary Bus
              fetch('/api/transformers/by-bus/' + encodeURIComponent(primaryBusId))
                .then(function (r) { return r.json(); })
                .then(function (transResult) {
                  if (transResult && transResult.error) {
                    console.warn('Transformer fetch error:', transResult.error);
                    showNoticeModal('Info', 'No transformer found connected to this post. Secondary lines must be linked via a Distribution Transformer.');
                    return;
                  }

                  if (!transResult.transformers || transResult.transformers.length === 0) {
                    showNoticeModal('Info', 'No transformer found for bus ID: ' + primaryBusId + '. Cannot resolve secondary lines.');
                    return;
                  }

                  // 3. Get Secondary Bus ID from the first found transformer
                  var transformer = transResult.transformers[0];
                  var secondaryBusId = transformer.to_secondary_bus_id;

                  if (!secondaryBusId) {
                    showNoticeModal('Info', 'Transformer found, but it has no Secondary Bus ID defined.');
                    return;
                  }

                  // 4. Fetch Secondary Lines using the Transformer's Secondary Bus ID
                  fetch('/api/secondary-lines/by-bus/' + encodeURIComponent(secondaryBusId))
                    .then(function (r) { return r.json(); })
                    .then(function (result) {
                      if (result && result.error) {
                        showNoticeModal('Error', 'Error fetching lines: ' + result.error);
                        return;
                      }
                      showSecondaryLineModal(result);
                    })
                    .catch(function (err) {
                      showNoticeModal('Error', 'Failed to load secondary lines: ' + (err.message || String(err)));
                    });

                })
                .catch(function (err) {
                  showNoticeModal('Error', 'Failed to check for transformer: ' + (err.message || String(err)));
                });
            })
            .catch(function (err) {
              console.error('Post details fetch failed:', err);
            });
        };
      }

      // Secondary Service Drop button: fetch drops directly via unified backend endpoint
      const serviceDropBtn = popupEl.querySelector('.service-drop-btn');
      if (serviceDropBtn) {
        serviceDropBtn.onclick = function () {
          const postId = serviceDropBtn.getAttribute('data-post-id');
          if (!postId) return;

          fetch('/api/posts/' + postId + '/service-drops')
            .then(function (r) { return r.json(); })
            .then(function (result) {
              if (result && result.error) {
                showNoticeModal('Error', 'Failed to load service drops: ' + result.error);
                return;
              }
              if (!result || !result.service_drops || result.service_drops.length === 0) {
                showNoticeModal('Info', 'No service drops found for this post.');
                return;
              }
              showServiceDropModal({
                count: result.count || result.service_drops.length,
                service_drops: result.service_drops
              });
            })
            .catch(function (err) {
              showNoticeModal('Error', 'Failed to load service drops: ' + (err.message || String(err)));
            });
        };
      }

      // Trace Downstream button: use BFS topology engine
      const traceBtn = popupEl.querySelector('.trace-downstream-btn');
      if (traceBtn) {
        traceBtn.onclick = function () {
          const busId = traceBtn.getAttribute('data-bus-id');
          if (!busId) return;

          traceBtn.textContent = 'Tracing...';
          traceBtn.disabled = true;

          fetch('/api/network/trace-feeder?start_bus=' + encodeURIComponent(busId))
            .then(r => r.json())
            .then(res => {
              traceBtn.textContent = 'Trace Downstream';
              traceBtn.disabled = false;

              if (res.error) {
                showNoticeModal('Error', 'Trace failed: ' + res.error);
                return;
              }

              if (res.visited_buses && res.visited_buses.length > 0) {
                highlightFeederTrace(res.visited_buses);
                traceBtn.textContent = `Trace Complete (${res.count} Nodes)`;
              } else {
                showNoticeModal('Info', 'No downstream nodes found from this point.');
              }
            })
            .catch(err => {
              traceBtn.textContent = 'Trace Downstream';
              traceBtn.disabled = false;
              showNoticeModal('Error', 'Trace request failed.');
            });
        };
      }

      // Simulate Outage button
      const outageBtn = popupEl.querySelector('.simulate-outage-btn');
      if (outageBtn) {
        outageBtn.onclick = function () {
          const busId = outageBtn.getAttribute('data-bus-id');
          if (!busId) return;

          outageBtn.textContent = 'Analyzing...';
          outageBtn.disabled = true;

          fetch('/api/network/simulate-outage?start_bus=' + encodeURIComponent(busId))
            .then(r => r.json())
            .then(res => {
              outageBtn.textContent = 'Simulate Outage';
              outageBtn.disabled = false;
              if (res.error) {
                showNoticeModal('Error', 'Analysis failed: ' + res.error);
                return;
              }
              showOutageImpactModal(res, busId);
            })
            .catch(err => {
              outageBtn.textContent = 'Simulate Outage';
              outageBtn.disabled = false;
              showNoticeModal('Error', 'Request failed.');
            });
        };
      }

      // Show Connected Lines Button
      const showConnectionsBtn = popupEl.querySelector('.btn-show-connections');
      if (showConnectionsBtn) {
        showConnectionsBtn.onclick = function () {
          const postId = showConnectionsBtn.getAttribute('data-post-id');
          if (!postId) return;

          // Show loading state or similar if desired
          showConnectionsBtn.textContent = 'Loading...';

          fetch('/api/posts/' + postId + '/connections')
            .then(r => r.json())
            .then(connections => {
              showConnectionsBtn.textContent = 'View Connected Lines';
              showConnectionsBtn.textContent = 'View Connected Lines';
              if (!connections) {
                showNoticeModal('Error', 'Failed to load connections.');
                return;
              }
              if (connections.length === 0) {
                showNoticeModal('Info', 'No connections found for this post.');
                return;
              }
              showConnectionsModal(connections, postId);
            })
            .catch(err => {
              console.error('Connection fetch failed:', err);
              showConnectionsBtn.textContent = 'View Connected Lines';
              showNoticeModal('Error', 'Error loading connections.');
            });
        };
      }

      // --- New Asset Handlers ---

      // Voltage Regulator
      const vrBtn = popupEl.querySelector('.voltage-regulator-btn');
      if (vrBtn) {
        vrBtn.onclick = function () {
          const postId = vrBtn.getAttribute('data-post-id');
          if (!postId) return;
          fetch('/api/posts/' + postId)
            .then(r => r.json())
            .then(postData => {
              if (postData.error) return;
              const busId = postData.primary_bus_id || postData.pole_number;
              if (!busId) { showNoticeModal('Info', 'No bus ID found for this post'); return; }
              fetch('/api/voltage-regulators/by-bus/' + encodeURIComponent(busId))
                .then(r => r.json())
                .then(res => {
                  if (res.error) { showNoticeModal('Error', res.error); return; }
                  if (res.count === 0) { showNoticeModal('Info', 'No Voltage Regulators found for bus: ' + busId); return; }
                  showVoltageRegulatorModal(res);
                });
            });
        };
      }

      // Shunt Capacitor
      const scBtn = popupEl.querySelector('.shunt-capacitor-btn');
      if (scBtn) {
        scBtn.onclick = function () {
          const postId = scBtn.getAttribute('data-post-id');
          if (!postId) return;
          fetch('/api/posts/' + postId)
            .then(r => r.json())
            .then(postData => {
              if (postData.error) return;
              const busId = postData.primary_bus_id || postData.pole_number;
              if (!busId) { showNoticeModal('Info', 'No bus ID found for this post'); return; }
              fetch('/api/shunt-capacitors/by-bus/' + encodeURIComponent(busId))
                .then(r => r.json())
                .then(res => {
                  if (res.error) { showNoticeModal('Error', res.error); return; }
                  if (res.count === 0) { showNoticeModal('Info', 'No Shunt Capacitors found for bus: ' + busId); return; }
                  showShuntCapacitorModal(res);
                });
            });
        };
      }

      // Shunt Inductor
      const siBtn = popupEl.querySelector('.shunt-inductor-btn');
      if (siBtn) {
        siBtn.onclick = function () {
          const postId = siBtn.getAttribute('data-post-id');
          if (!postId) return;
          fetch('/api/posts/' + postId)
            .then(r => r.json())
            .then(postData => {
              if (postData.error) return;
              const busId = postData.primary_bus_id || postData.pole_number;
              if (!busId) { showNoticeModal('Info', 'No bus ID found for this post'); return; }
              fetch('/api/shunt-inductors/by-bus/' + encodeURIComponent(busId))
                .then(r => r.json())
                .then(res => {
                  if (res.error) { showNoticeModal('Error', res.error); return; }
                  if (res.count === 0) { showNoticeModal('Info', 'No Shunt Inductors found for bus: ' + busId); return; }
                  showShuntInductorModal(res);
                });
            });
        };
      }

      // Series Inductor
      const eriBtn = popupEl.querySelector('.series-inductor-btn');
      if (eriBtn) {
        eriBtn.onclick = function () {
          const postId = eriBtn.getAttribute('data-post-id');
          if (!postId) return;
          fetch('/api/posts/' + postId)
            .then(r => r.json())
            .then(postData => {
              if (postData.error) return;
              const busId = postData.primary_bus_id || postData.pole_number;
              if (!busId) { showNoticeModal('Info', 'No bus ID found for this post'); return; }
              fetch('/api/series-inductors/by-bus/' + encodeURIComponent(busId))
                .then(r => r.json())
                .then(res => {
                  if (res.error) { showNoticeModal('Error', res.error); return; }
                  if (res.count === 0) { showNoticeModal('Info', 'No Series Inductors found for bus: ' + busId); return; }
                  showSeriesInductorModal(res);
                });
            });
        };
      }

      // Load authoritative post details from the `post` table via API
      try {
        const detailsEl = popupEl.querySelector('.popup-post-details');
        fetch(`/api/posts/${p.id}`)
          .then(r => r.json())
          .then(data => {
            if (!data || data.error) return;

            // Fetch Voltage Regulator to get kVA Rating if available
            const busId = data.primary_bus_id || data.pole_number;
            let vrPromise = Promise.resolve(null);

            if (busId) {
              vrPromise = fetch('/api/voltage-regulators/by-bus/' + encodeURIComponent(busId))
                .then(r => r.json())
                .then(res => {
                  if (res.items && res.items.length > 0) return res.items[0];
                  return null;
                })
                .catch(() => null);
            }

            vrPromise.then(vrData => {
              const latText = (typeof data.lat === 'number') ? data.lat.toFixed(6) : (data.lat || '');
              const lngText = (typeof data.lng === 'number') ? data.lng.toFixed(6) : (data.lng || '');

              // Determine KVA: prefer VR data if available, else Post data
              let kvaDisplay = '—';
              if (vrData && vrData.kva_rating != null) {
                kvaDisplay = vrData.kva_rating;
              } else if (data.kva_rating != null) {
                kvaDisplay = data.kva_rating;
              }

              let infoHtml = `<strong>${(data.name || 'Post ' + data.id).replace(/</g, '&lt;')}</strong>${(data.kva_rating != null && data.kva_rating !== '') ? ' <img src="/static/img/transformer_pole.svg" style="width:18px;height:18px;vertical-align:middle;margin-left:4px;" title="Transformer Pole">' : ''}<br>`;
              infoHtml += `Pole Number: ${data.pole_number || '—'}<br>`;
              infoHtml += `Status: ${data.status || 'N/A'}<br>`;
              infoHtml += `Feeder: ${data.feeder || '—'}<br>`;
              infoHtml += `kVA Rating: ${kvaDisplay}<br>`;

              // Injection of Analysis Data
              const id = data.pole_number || data.primary_bus_id;
              const r = window._mlRiskMap[id];
              const s = window._loadStressMap[id];

              if (r) {
                const color = r.risk_level === 'Critical' ? '#ef4444' : (r.risk_level === 'High' ? '#f59e0b' : '#22c55e');
                infoHtml += `<div style="margin-top:8px; padding:6px; border-radius:6px; background:rgba(0,0,0,0.03); border-left:4px solid ${color};">`;
                infoHtml += `<strong style="color:${color}; font-size:0.8rem;">PREDICTIVE RISK: ${r.risk_level}</strong><br>`;
                infoHtml += `<span style="font-size:0.75rem;">Score: ${r.risk_score.toFixed(4)}</span>`;
                infoHtml += `</div>`;
              }

              if (s) {
                const color = s.status === 'Overloaded' ? '#ef4444' : (s.status === 'High Load' ? '#f59e0b' : '#22c55e');
                infoHtml += `<div style="margin-top:4px; padding:6px; border-radius:6px; background:rgba(0,0,0,0.03); border-left:4px solid ${color};">`;
                infoHtml += `<strong style="color:${color}; font-size:0.8rem;">LOAD FLOW: ${s.status}</strong><br>`;
                infoHtml += `<span style="font-size:0.75rem;">Peak: ${s.peak_load_kw.toFixed(2)} kW (${s.utilization_pct.toFixed(1)}%)</span>`;
                infoHtml += `</div>`;
              }

              infoHtml += `<div style="margin-top:8px; font-size:0.8rem; color:var(--text-secondary);">Coordinates: ${latText}, ${lngText}</div>`;
              if (detailsEl) detailsEl.innerHTML = infoHtml;
            });
          }).catch(() => { });
      } catch (e) { console.error('Failed to fetch post details', e); }

      // Load connections that include this post — section is inside the popup (modal) content
      const connectionsContainer = popupEl.querySelector('.popup-connections-inner');
      if (!connectionsContainer) return;
      connectionsContainer.innerHTML = '';
      fetch(`/api/posts/${p.id}/connections`)
        .then(r => r.json())
        .then(function (conns) {
          if (!conns || !Array.isArray(conns)) conns = (conns && conns.connections) ? conns.connections : [];
          if (conns.length === 0) return;
          const section = document.createElement('div');
          section.className = 'post-connections-section';
          section.setAttribute('aria-label', 'Connections that include this post');
          const title = document.createElement('strong');
          title.textContent = 'Connections that include this post:';
          section.appendChild(title);
          const list = document.createElement('ul');
          list.className = 'post-connections-list';
          conns.forEach(function (c) {
            const li = document.createElement('li');
            const name = (typeof c.name === 'string' && c.name && c.name.indexOf('{') !== 0) ? c.name : ('Connection #' + (c.id != null ? c.id : ''));
            const ids = (c.points || []).map(function (pt) { return pt.post_id ? '#' + pt.post_id : (pt.lat != null && pt.lng != null ? pt.lat.toFixed(6) + ',' + pt.lng.toFixed(6) : ''); }).join(', ');
            li.innerHTML = (name.replace(/</g, '&lt;')) + ' (id ' + (c.id != null ? c.id : '') + ') — ' + formatMeters(c.total_length || 0) + '<br/>IDs: ' + (ids || '—') + ' <button class="btn btn-danger disconnect-from-post" data-conn-id="' + (c.id != null ? c.id : '') + '">Disconnect</button>';
            list.appendChild(li);
          });
          section.appendChild(list);
          connectionsContainer.appendChild(section);

          // attach handlers scoped to the newly created section
          const btns = section.querySelectorAll('.disconnect-from-post');
          btns.forEach(b => {
            b.addEventListener('click', function (ev) {
              ev.preventDefault();
              const id = b.getAttribute('data-conn-id');
              showConfirmModal('Disconnect/delete this connection?', { title: 'Delete connection', okText: 'Delete', cancelText: 'Cancel' })
                .then(function (confirmed) {
                  if (!confirmed) return;
                  fetch('/api/connections/' + id, { method: 'DELETE' })
                    .then(r => r.json())
                    .then(j => {
                      if (j && j.result === 'deleted') {
                        showNoticeModal('Deleted', 'Connection deleted');
                        loadConnections();
                        // remove section item from DOM
                        b.closest('li').remove();
                        // if no more items, remove section entirely
                        if (!section.querySelector('li')) section.remove();
                      } else {
                        showNoticeModal('Delete failed', 'Delete failed: ' + JSON.stringify(j));
                      }
                    }).catch(err => showNoticeModal('Delete failed', 'Delete failed: ' + err));
                });
            });
          });
        }).catch(err => console.error('Failed to load post connections', err));
      const expBtn = popupEl.querySelector('.export-post');
      if (expBtn) {
        expBtn.addEventListener('click', function (ev) {
          ev.preventDefault();
          // trigger file download
          window.location = '/api/export/post/' + p.id;
        });
      }
    });

    return marker;
  }

  function addLatLongMarker(layer, r) {
    const lat = parseFloat(r.lat);
    const lng = parseFloat(r.lng);
    if (Number.isNaN(lat) || Number.isNaN(lng)) return;
    const circle = L.circleMarker([lat, lng], { radius: 6, color: '#007bff', fillColor: '#007bff', fillOpacity: 0.9 })
      .bindPopup(`<strong>Raw: ${r.post_id}</strong><br>Coordinates: ${lat.toFixed(6)}, ${lng.toFixed(6)}`);
    circle.addTo(layer);
    bounds.extend([lat, lng]);
    return circle;
  }

  // Load canonical posts (filtered to PH) by iterating through all pages
  async function fetchAllPosts(inPh = 1) {
    let allPosts = [];
    let page = 1;
    let totalPages = 1;

    try {
      while (page <= totalPages) {
        let response = await fetch(`/api/posts?in_ph=${inPh}&per_page=1000&page=${page}`);
        if (!response.ok) throw new Error(`API error: ${response.status}`);
        let json = await response.json();

        let postsBatch = Array.isArray(json) ? json : (json.data || []);
        allPosts = allPosts.concat(postsBatch);

        if (json.pagination) {
          totalPages = json.pagination.total_pages || 1;
        } else {
          break; // Not paginated response
        }
        page++;
      }
      return allPosts;
    } catch (err) {
      console.error('Failed to fetch all posts:', err);
      return allPosts;
    }
  }

  function loadPosts() {
    console.log('🔄 Loading posts and analysis data...');

    // Fetch all analysis data in parallel with posts
    Promise.all([
      fetchAllPosts(1),
      fetch('/api/ml/transformer-risk').then(r => r.json()).catch(() => ({})),
      fetch('/api/ml/transformer-load-stress').then(r => r.json()).catch(() => ({}))
    ]).then(([posts, mlResults, loadResults]) => {
      // Index ML Risk data for fast lookup
      window._mlRiskMap = {};
      if (mlResults.predictions) {
        mlResults.predictions.forEach(r => {
          const key = r.transformer_id || r.id || r.bus_id;
          if (key) window._mlRiskMap[key] = r;
        });
      }

      // Index Load Flow data
      window._loadStressMap = {};
      if (loadResults.predictions) {
        loadResults.predictions.forEach(s => {
          const key = s.transformer_id || s.bus_id;
          if (key) window._loadStressMap[key] = s;
        });
      }

      console.log('Posts to render on map:', posts.length);

      if (!posts || posts.length === 0) {
        showMapError('No post data available to display.');
        return;
      }

      // Update sidebar analytics after data is loaded
      updateGridAnalytics();
      let addedCount = 0;
      posts.forEach(p => {
        if (p && p.lat && p.lng) {
          addPostMarker(postsLayer, p);
          addedCount++;
        } else {
          console.warn('Skipping post with missing coords:', p);
        }
      });

      console.log(`Added ${addedCount} markers to posts layer`);

      // Add postsLayer to map by default
      postsLayer.addTo(map);
      console.log('Posts layer added to map');

      // Fit map if we added markers (use isValid() guard — isEmpty() isn't available in this Leaflet build)
      if (typeof bounds.isValid === 'function' ? bounds.isValid() : !bounds.isEmpty) {
        try {
          map.fitBounds(bounds.pad(0.12));
          console.log('Map bounds fitted');
        } catch (e) {
          console.warn('Failed to fit bounds:', e);
        }
      } else {
        console.log('Bounds not valid - using default map view');
      }

      // If a target post id was provided via URL params, center/fly to it and open popup
      try {
        const targetId = window._targetPostId;
        if (targetId) {
          const tid = parseInt(targetId, 10);
          console.log('Targeting post ID:', tid);
          // small timeout to ensure markers have been added to the layer
          setTimeout(function () {
            const marker = postMarkers[tid];
            if (marker && marker.getLatLng) {
              try { map.flyTo(marker.getLatLng(), 17); } catch (e) { map.setView(marker.getLatLng(), 17); }
              try { marker.openPopup(); } catch (e) { }
            } else {
              console.warn('Target marker not found:', tid);
            }
          }, 250);
        }
      } catch (e) { console.error('Error in target post handling:', e); }

      // Ensure postsLayer is on map so applyFeederFilter sees it as visible
      if (!map.hasLayer(postsLayer)) postsLayer.addTo(map);

      // Ensure new feeders from posts are reflected in UI and filter
      if (typeof window._refreshFeederList === 'function') window._refreshFeederList();
      applyFeederFilter();
    })
      .catch(err => console.error('Failed to load posts:', err));
  }

  // Initial load
  loadPosts();

  // Load raw latlongdata layer
  fetch('/api/latlongdata')
    .then(r => r.json())
    .then(rows => {
      if (!rows || rows.length === 0) return;
      rows.forEach(r => addLatLongMarker(latlongLayer, r));
      // Do not add latlongLayer by default; user can toggle it on via control
    })
    .catch(err => console.error('Failed to load latlongdata', err));

  // Load and draw inferred line connections
  function loadLineConnections() {
    console.log('Starting loadLineConnections...');

    fetch('/api/line-connections')
      .then(r => {
        if (!r.ok) throw new Error(`API error: ${r.status}`);
        return r.json();
      })
      .then(data => {
        const connections = data.connections || [];
        console.log(`API returned ${connections.length} connections`);

        if (!connections || connections.length === 0) {
          console.log('No line connections to display');
          return;
        }

        // Build a numeric pole -> marker lookup map
        const poleMap = {};
        for (const postId in postMarkers) {
          const marker = postMarkers[postId];
          if (marker._postData && marker._postData.pole_number) {
            const poleNum = parseInt(marker._postData.pole_number.replace(/\D/g, '') || -1);
            if (poleNum > 0) {
              poleMap[poleNum] = marker;
              console.log(`Mapped pole ${poleNum} to post ${postId}`);
            }
          }
        }

        console.log(`Pole map has ${Object.keys(poleMap).length} poles`);

        let drawnCount = 0;
        let skippedCount = 0;

        // Draw each connection
        connections.forEach((conn, idx) => {
          const fromBus = conn.from_bus;
          const toBus = conn.to_bus;
          const connType = conn.connection_type || '';

          // Extract first numeric value from bus ID
          const fromMatch = fromBus.match(/\d+/);
          const toMatch = toBus.match(/\d+/);

          if (!fromMatch || !toMatch) {
            skippedCount++;
            return;
          }

          const fromNum = parseInt(fromMatch[0]);
          const toNum = parseInt(toMatch[0]);

          const fromMarker = poleMap[fromNum];
          const toMarker = poleMap[toNum];

          if (!fromMarker || !toMarker) {
            skippedCount++;
            return;
          }

          const fromLatLng = fromMarker.getLatLng();
          const toLatLng = toMarker.getLatLng();

          if (!fromLatLng || !toLatLng) {
            skippedCount++;
            const toBus = conn.to_bus_id || conn.to_bus;
            return;
          }

          // Determine line color
          const lineColor = getLineColor(conn.circuit, conn.phasing);
          let lineWeight = 2;
          let dashArray = null;

          // Adjust weight and dash based on connection type
          if (connType.includes('Primary')) {
            lineWeight = 3;
          } else if (connType.includes('Transformer')) {
            lineWeight = 2.5;
          } else if (connType.includes('Secondary')) {
            lineWeight = 2;
            dashArray = '5, 5'; // Dashed for secondary-to-secondary
          }

          // Create polyline
          const polyline = L.polyline([fromLatLng, toLatLng], {
            color: lineColor,
            weight: lineWeight,
            opacity: 0.7,
            dashArray: dashArray
          });

          // Store circuit type for dynamic styling
          polyline.circuitType = conn.circuit;
          polyline.phasingType = conn.phasing; // Store phasing for color updates

          // Add popup
          const popupText = `
            <strong>${connType.replace(/_/g, ' → ')}</strong><br>
            From Bus: ${fromBus}<br>
            To Bus: ${toBus}<br>
            Feeder: ${conn.feeder || 'N/A'}<br>
            Circuit: ${conn.circuit || 'N/A'}<br>
            Phasing: ${conn.phasing || 'N/A'}
          `;
          polyline.bindPopup(popupText);

          polyline.addTo(connectionsLayer);
          drawnCount++;
        });

        // Add layer to map
        connectionsLayer.addTo(map);

        console.log(`Line connections: ${drawnCount} drawn, ${skippedCount} skipped`);
      })
      .catch(err => {
        console.error('Failed to load line connections:', err);
      });
  }

  // Chain segments that share an endpoint into continuous paths (so network looks like connected lines, not many separate segments)
  function chainSegmentsIntoPaths(lines) {
    var tol = 1e-6;
    function eq(a, b) { return Math.abs(parseFloat(a) - parseFloat(b)) < tol; }
    function samePoint(lat1, lng1, lat2, lng2) { return eq(lat1, lat2) && eq(lng1, lng2); }
    var used = {};
    var paths = [];
    for (var i = 0; i < lines.length; i++) {
      if (used[i]) continue;
      var line = lines[i];
      var lat1 = parseFloat(line.lat1);
      var lng1 = parseFloat(line.lng1);
      var lat2 = parseFloat(line.lat2);
      var lng2 = parseFloat(line.lng2);
      if (Number.isNaN(lat1) || Number.isNaN(lng1) || Number.isNaN(lat2) || Number.isNaN(lng2)) continue;
      var points = [[lat1, lng1], [lat2, lng2]];
      var pathMeta = { connection_type: line.connection_type || '', circuit: line.circuit, feeder: line.feeder, phasing: line.phasing, from_bus: line.from_bus, to_bus: line.to_bus, length_meters: line.length_meters, segments: 1 };
      used[i] = true;
      var changed = true;
      while (changed) {
        changed = false;
        var head = points[points.length - 1];
        var tail = points[0];
        for (var j = 0; j < lines.length; j++) {
          if (used[j]) continue;
          var s = lines[j];

          // CRITICAL: Only chain if metadata matches (prevent "consumption" of different line types)
          if (s.connection_type !== pathMeta.connection_type ||
            s.phasing !== pathMeta.phasing ||
            s.circuit !== pathMeta.circuit ||
            s.feeder !== pathMeta.feeder) {
            continue;
          }

          var s1 = [parseFloat(s.lat1), parseFloat(s.lng1)];
          var s2 = [parseFloat(s.lat2), parseFloat(s.lng2)];
          if (samePoint(head[0], head[1], s1[0], s1[1])) { points.push(s2); pathMeta.segments++; pathMeta.to_bus = s.to_bus; if (s.length_meters != null && !Number.isNaN(s.length_meters)) pathMeta.length_meters = (pathMeta.length_meters || 0) + s.length_meters; used[j] = true; changed = true; break; }
          if (samePoint(head[0], head[1], s2[0], s2[1])) { points.push(s1); pathMeta.segments++; pathMeta.to_bus = s.from_bus; if (s.length_meters != null && !Number.isNaN(s.length_meters)) pathMeta.length_meters = (pathMeta.length_meters || 0) + s.length_meters; used[j] = true; changed = true; break; }
          if (samePoint(tail[0], tail[1], s2[0], s2[1])) { points.unshift(s1); pathMeta.segments++; pathMeta.from_bus = s.from_bus; if (s.length_meters != null && !Number.isNaN(s.length_meters)) pathMeta.length_meters = (pathMeta.length_meters || 0) + s.length_meters; used[j] = true; changed = true; break; }
          if (samePoint(tail[0], tail[1], s1[0], s1[1])) { points.unshift(s2); pathMeta.segments++; pathMeta.from_bus = s.to_bus; if (s.length_meters != null && !Number.isNaN(s.length_meters)) pathMeta.length_meters = (pathMeta.length_meters || 0) + s.length_meters; used[j] = true; changed = true; break; }
        }
      }
      paths.push({ points: points, meta: pathMeta });
    }
    return paths;
  }

  // Load network line geometry from DB (coordinates from DB only; no client-side resolution)
  function loadNetworkGeometry() {
    fetch('/api/network-geometry')
      .then(function (r) { return r.ok ? r.json() : Promise.reject(new Error(r.statusText)); })
      .then(function (data) {
        networkLinesLayer.clearLayers();
        var lines = data.lines || [];
        var stats = data.stats || {};
        var hintEl = document.getElementById('network-geometry-hint');
        if (data.error) {
          console.warn('Network geometry (server message):', data.error);
          if (hintEl) {
            hintEl.textContent = 'Network lines: ' + data.error + ' (check migrations or database).';
            hintEl.style.display = 'block';
          }
        } else if (lines.length === 0) {
          console.log('Network geometry: no lines yet. Import posts with coordinates from the Resources page.');
          if (hintEl) {
            hintEl.innerHTML = 'No network lines yet. Upload posts with <strong>Pole Number, Latitude, Longitude</strong> from the <a href="/resources">Resources</a> page to see lines on the map.';
            hintEl.style.display = 'block';
          }
        } else {
          if (hintEl) { hintEl.style.display = 'none'; }
        }
        // Instead of chaining segments (which merges metadata), 
        // we render each segment individually to match the CSV records exactly.
        lines.forEach(function (line) {
          var points = [[line.lat1, line.lng1], [line.lat2, line.lng2]];
          var meta = line;
          if (points.length < 2) return;
          var connType = meta.connection_type || '';
          var color = getLineColor(meta.circuit, meta.phasing);
          var weight = 2;
          var dash = null;
          var lineCat = 'unknown'; // specific category for the UI filters

          // prioritized categorization based on user technical terminology (P = Primary/Distribution, DT = Transformer, S = Secondary)
          var fromB = String(meta.from_bus || '').toUpperCase();
          var toB = String(meta.to_bus || '').toUpperCase();

          // Priority categorization: check explicit connection type first
          if (connType.indexOf('Transformer') !== -1 || connType === 'Primary_to_Transformer') {
            weight = 3;
            lineCat = 'transformer';
            color = '#f59e0b'; // Bold Transformer Gold
          }
          else if (connType.indexOf('Secondary') !== -1 || (connType.indexOf('Line') !== -1 && connType.indexOf('Secondary') !== -1)) {
            weight = 2;
            lineCat = 'secondary';
          }
          else if (connType.indexOf('Customer') !== -1 || connType.indexOf('Service_Drop') !== -1 || connType === 'Secondary_to_Customer') {
            weight = 2;
            lineCat = 'service_drop';
            dash = '3, 4';
          }
          else if (connType.indexOf('Primary') !== -1 || connType === 'Distribution_Line') {
            weight = 3;
            lineCat = 'primary';
          }
          // Fallback to ID prefixes if type is ambiguous
          else if (fromB.startsWith('DT') || toB.startsWith('DT') || connType.indexOf('transformer') !== -1) {
            weight = 3;
            lineCat = 'transformer';
            color = '#f59e0b';
          }
          else if (fromB.startsWith('S') || toB.startsWith('S')) {
            weight = 2;
            lineCat = 'secondary';
          }
          else if (fromB.startsWith('P') || toB.startsWith('P')) {
            weight = 3;
            lineCat = 'primary';
          }
          else {
            lineCat = 'primary'; // Fallback
          }

          var poly = L.polyline(points, { color: color, weight: weight, opacity: 0.8, dashArray: dash, lineJoin: 'round', lineCap: 'round' });

          // Store tags for dynamic styling and filtering
          poly.circuitType = meta.circuit;
          poly.phasingType = meta.phasing;
          poly.lineCategory = lineCat;
          poly._feederName = String(meta.feeder || '').trim();
          poly._fromBus = meta.from_bus;
          poly._toBus = meta.to_bus;
          poly._defaultStyle = { color: color, weight: weight, opacity: 0.8, dashArray: dash };
          if (meta.feeder) knownFeeders.add(String(meta.feeder).trim());

          var lenStr = (meta.length_meters != null && !Number.isNaN(meta.length_meters))
            ? '<br>Length: ' + Number(meta.length_meters).toFixed(2) + ' m'
            : '';
          var segStr = meta.segments > 1 ? ' (' + meta.segments + ' segments)' : '';

          // Use friendly label for the popup title based on category
          var friendlyTitle = 'Network';
          if (lineCat === 'primary') friendlyTitle = 'Primary / Distribution Line';
          else if (lineCat === 'secondary') friendlyTitle = 'Secondary Line';
          else if (lineCat === 'service_drop') friendlyTitle = 'Service Drop';
          else if (lineCat === 'transformer') friendlyTitle = 'Distribution Transformer';
          else friendlyTitle = connType.replace(/_/g, ' \u2192 ') || 'Network';

          var popup = '<strong>' + friendlyTitle + segStr + '</strong><br>From: ' + (meta.from_bus || '') + ' \u2192 To: ' + (meta.to_bus || '') + '<br>Feeder: ' + (meta.feeder || '') + ' | Circuit: ' + (meta.circuit || '') + ' | Phasing: ' + (meta.phasing || 'N/A') + lenStr;
          poly.bindPopup(popup);
          poly.addTo(networkLinesLayer);
        });
        networkLinesLayer.addTo(map);

        // --- Render Virtual Nodes & Customers ---
        var nodesForMap = data.nodes || [];
        var nodesDrawn = 0;
        nodesForMap.forEach(function (n) {
          if (n.feature_type === 'virtual_node' || n.feature_type === 'customer') {
            var lat = parseFloat(n.lat);
            var lng = parseFloat(n.lng);
            if (Number.isNaN(lat) || Number.isNaN(lng)) return;

            var iconToUse = (n.feature_type === 'customer') ? customerIcon : virtualNodeIcon;
            var labelType = (n.feature_type === 'customer') ? 'Customer' : 'Virtual Node';
            var title = n.pole_number || (labelType + ' at ' + lat.toFixed(4) + ',' + lng.toFixed(4));

            var marker = L.marker([lat, lng], { title: title, icon: iconToUse });
            marker._feederName = String(n.feeder || '').trim();
            if (n.feeder) knownFeeders.add(String(n.feeder).trim());

            var popupContent = '<strong>' + labelType + '</strong><br>ID: ' + (n.pole_number || 'N/A') + '<br>Feeder: ' + (n.feeder || 'N/A');
            if (n.feature_type === 'customer' && n.customer_name) {
              popupContent += '<br>Name: ' + n.customer_name;
            }
            marker.bindPopup(popupContent);
            marker.bindTooltip(title, { permanent: false, direction: 'top' });

            marker.addTo(networkLinesLayer);
            nodesDrawn++;
          }
        });
        if (nodesDrawn > 0) {
          console.log('Network geometry: Rendered ' + nodesDrawn + ' virtual/customer nodes.');
        }
        // -----------------------------------------

        // Refresh the feeder filter UI after network lines are loaded FIRST
        if (typeof window._refreshFeederList === 'function') window._refreshFeederList();

        // Final pass to apply all active filters (feeders, phases, and Post visibility logic for technical markers)
        applyFeederFilter();
        var totalM = stats.total_length_meters != null ? stats.total_length_meters : 0;
        console.log('Network geometry: Rendered ' + lines.length + ' segments (nodes: ' + (stats.nodes || 0) + ', total length: ' + (typeof totalM === 'number' ? totalM.toFixed(2) : totalM) + ' m)');
      })
      .catch(function (err) { console.warn('Network geometry load failed:', err); });
  }


  // Load connections after posts are loaded
  setTimeout(function () {
    console.log('Calling loadLineConnections after posts...');
    // loadLineConnections(); // DEPRECATED: redundant with network-geometry
    loadNetworkGeometry();
  }, 1000);

  // ---------- Bulk CSV/Excel import is now the primary method (removed single-post input) ----------
  // Users should use the resources page to upload CSV/Excel files for bulk post import

  // ---------- Connection editing controls and logic ----------
  // Add a layer for saved connections
  connectionsLayer.addTo(map);

  // On-map hint when in connection mode (show/hide)
  function showConnectionHint(text) {
    let el = document.getElementById('conn-hint');
    if (!el) {
      const parent = document.querySelector('.connection-control');
      if (parent) {
        el = document.createElement('div');
        el.id = 'conn-hint';
        el.className = 'conn-hint';
        parent.appendChild(el);
      } else return;
    }
    el.textContent = text;
    el.style.display = 'block';
  }
  function hideConnectionHint() {
    const el = document.getElementById('conn-hint');
    if (el) el.style.display = 'none';
  }

  // Connection mode management (internal, no UI toolbar)
  function startConnection() {
    connectionMode = true;
    connectionPoints = [];
    if (connectionPolyline) { map.removeLayer(connectionPolyline); connectionPolyline = null; }
    connectionPolyline = L.polyline([], { color: '#ff6600', weight: 4, dashArray: '6 4' }).addTo(map);
    updateConnectionUI();
  }

  function stopConnection() {
    connectionMode = false;
    hideConnectionHint();
    updateConnectionUI();
  }

  function clearConnection() {
    connectionPoints = [];
    if (connectionPolyline) { connectionPolyline.setLatLngs([]); map.removeLayer(connectionPolyline); connectionPolyline = null; }
    clearLiveEndpoints();
    document.getElementById('conn-distance').textContent = '0 m';
    connectionMode = false;
    hideConnectionHint();
    updateConnectionControlsVisibility();
  }

  function addPointToConnection(pt) {
    connectionPoints.push(pt);
    if (!connectionPolyline) {
      connectionPolyline = L.polyline([], { color: '#ff6600', weight: 4, dashArray: '6 4', lineCap: 'round' }).addTo(map);
    }
    connectionPolyline.addLatLng([pt.lat, pt.lng]);
    // Add a small visible endpoint marker exactly at coordinates
    addLiveEndpoint(pt.lat, pt.lng);
    updateConnectionControlsVisibility();
    updateConnectionUI();
  }

  function updateConnectionUI() {
    // compute total
    let total = 0;
    for (let i = 1; i < connectionPoints.length; i++) {
      total += haversine(connectionPoints[i - 1].lat, connectionPoints[i - 1].lng, connectionPoints[i].lat, connectionPoints[i].lng);
    }
  }

  // Temporarily highlight a polyline for visual feedback when clicked
  function highlightPoly(poly) {
    try {
      const origColor = poly.options.color || '#0066ff';
      const origWeight = poly.options.weight || 3;
      poly.setStyle({ color: '#ff9900', weight: Math.max(origWeight + 2, 5) });
      setTimeout(() => {
        try { poly.setStyle({ color: origColor, weight: origWeight }); } catch (e) { /* ignore */ }
      }, 1000);
    } catch (e) { /* ignore */ }
  }



  // Success/result modal (replaces alert after connecting)
  let _resultModal = null;
  function createResultModal() {
    if (_resultModal) return _resultModal;
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay result-modal-overlay';
    overlay.setAttribute('aria-label', 'Connection result');
    overlay.innerHTML = `
      <div class="modal result-modal">
        <div class="modal-header result-modal-header">
          <h3 class="result-modal-title">Connection saved</h3>
          <button class="modal-close result-modal-close" aria-label="Close">✕</button>
        </div>
        <div class="modal-body result-modal-body">
          <p class="result-modal-message"></p>
          <div class="result-modal-details"></div>
        </div>
        <div class="modal-footer">
          <button class="btn result-modal-ok">OK</button>
        </div>
      </div>
    `;
    document.body.appendChild(overlay);
    overlay.querySelector('.result-modal-close').addEventListener('click', closeResultModal);
    overlay.querySelector('.result-modal-ok').addEventListener('click', closeResultModal);
    overlay.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeResultModal(); });
    overlay.addEventListener('click', (e) => { if (e.target === overlay) closeResultModal(); });
    _resultModal = overlay;
    return _resultModal;
  }
  function showResultModal(options) {
    const m = createResultModal();
    const titleEl = m.querySelector('.result-modal-title');
    const messageEl = m.querySelector('.result-modal-message');
    const detailsEl = m.querySelector('.result-modal-details');
    const header = m.querySelector('.result-modal-header');
    if (options.error) {
      titleEl.textContent = 'Connection failed';
      header.className = 'modal-header result-modal-header result-modal-header-error';
      messageEl.textContent = options.message || options.error;
      detailsEl.innerHTML = '';
    } else if (options.customTitle) {
      // allow arbitrary title for reuse (eg. deletion notices)
      titleEl.textContent = options.customTitle;
      header.className = 'modal-header result-modal-header';
      messageEl.textContent = options.message || '';
      detailsEl.innerHTML = '';
    } else {
      titleEl.textContent = options.count === 0 && options.id != null ? 'Post added' : (options.count > 1 ? 'Connections saved' : 'Connection saved');
      header.className = 'modal-header result-modal-header';
      messageEl.textContent = options.message || (options.name ? `"${options.name}" has been saved.` : 'Connection has been saved.');
      const length = options.length != null ? options.length : 0;
      const count = options.count != null ? options.count : (options.id != null ? 1 : 0);

      let gridHtml = '';
      if (count > 1) {
        gridHtml += `<div class="kv-item"><div class="kv-label">Segments saved</div><div class="kv-value">${count} post-to-post</div></div>`;
        gridHtml += `<div class="kv-item"><div class="kv-label">Total length</div><div class="kv-value">${formatMeters(length)}</div></div>`;
      } else if (count === 0 && options.id != null) {
        gridHtml += `<div class="kv-item"><div class="kv-label">Post ID</div><div class="kv-value">${options.id}</div></div>`;
      } else {
        gridHtml += `<div class="kv-item"><div class="kv-label">Connection ID</div><div class="kv-value">${options.id != null ? options.id : '—'}</div></div>`;
        gridHtml += `<div class="kv-item"><div class="kv-label">Length</div><div class="kv-value">${formatMeters(length)}</div></div>`;
      }

      detailsEl.innerHTML = `
        <div class="info-card">
          <div class="kv-grid">
            ${gridHtml}
          </div>
        </div>
      `;
    }
    m.style.display = 'flex';
    m.tabIndex = -1;
    m.focus();
  }
  function closeResultModal() {
    if (_resultModal) _resultModal.style.display = 'none';
  }

  // --- Primary line-overhead modal (post technical data) ---
  var _primaryLineOverheadModal = null;
  var PRIMARY_LINE_OVERHEAD_FIELDS = [
    { key: 'segment_id', label: 'Segment ID' },
    { key: 'from_bus_id', label: 'From Pole ID' },
    { key: 'to_bus_id', label: 'To Pole ID' },
    { key: 'length_meters', label: 'Length (m)' },
    { key: 'conductor_unit', label: 'Conductor unit' },
    { key: 'system_grounding_type', label: 'System grounding type' },
    { key: 'conductor_strands', label: 'Conductor strands' },
    { key: 'neutral_wire_type', label: 'Neutral wire type' },
    { key: 'neutral_wire_size', label: 'Neutral wire size' },
    { key: 'neutral_wire_unit', label: 'Neutral wire unit' },
    { key: 'neutral_wire_strands', label: 'Neutral wire strands' },
    { key: 'spacing_d12', label: 'Spacing D12' },
    { key: 'spacing_d23', label: 'Spacing D23' },
    { key: 'spacing_d13', label: 'Spacing D13' },
    { key: 'spacing_d1n', label: 'Spacing D1n' },
    { key: 'spacing_d2n', label: 'Spacing D2n' },
    { key: 'spacing_d3n', label: 'Spacing D3n' },
    { key: 'spacing_dc1_c2', label: 'Spacing DC1-C2' },
    { key: 'height_h1', label: 'Height H1' },
    { key: 'height_h2', label: 'Height H2' },
    { key: 'height_h3', label: 'Height H3' },
    { key: 'height_hn', label: 'Height Hn' },
    { key: 'earth_resistivity', label: 'Earth resistivity' }
  ];
  function createPrimaryLineOverheadModal() {
    if (_primaryLineOverheadModal) return _primaryLineOverheadModal;
    var overlay = document.createElement('div');
    overlay.className = 'modal-overlay primary-line-overhead-modal-overlay';
    overlay.setAttribute('aria-label', 'Primary line-overhead');
    overlay.innerHTML = [
      '<div class="modal result-modal" style="max-width: 500px; width: 90vw;">',
      '  <div class="modal-header result-modal-header">',
      '    <h3 class="result-modal-title">Primary line-overhead</h3>',
      '    <button class="modal-close primary-line-overhead-close" aria-label="Close">✕</button>',
      '  </div>',
      '  <div class="modal-body result-modal-body primary-line-overhead-body enhanced-body" style="max-height: 70vh; overflow-y: auto;">',
      '    <div class="primary-line-overhead-content"></div>',
      '  </div>',
      '  <div class="modal-footer"><button class="btn result-modal-ok primary-line-overhead-ok">OK</button></div>',
      '</div>'
    ].join('');
    document.body.appendChild(overlay);
    overlay.querySelector('.primary-line-overhead-close').addEventListener('click', closePrimaryLineOverheadModal);
    overlay.querySelector('.primary-line-overhead-ok').addEventListener('click', closePrimaryLineOverheadModal);
    overlay.addEventListener('click', function (e) { if (e.target === overlay) closePrimaryLineOverheadModal(); });
    overlay.addEventListener('keydown', function (e) { if (e.key === 'Escape') closePrimaryLineOverheadModal(); });
    _primaryLineOverheadModal = overlay;
    return _primaryLineOverheadModal;
  }
  function showPrimaryLineOverheadModal(data) {
    var m = createPrimaryLineOverheadModal();
    var contentDiv = m.querySelector('.primary-line-overhead-content');
    var title = m.querySelector('.result-modal-title');
    title.textContent = 'Primary line-overhead' + (data && data.name ? ' — ' + data.name : '');

    contentDiv.innerHTML = '';

    const card = document.createElement('div');
    card.className = 'info-card';

    // Optional: Add a header to the card if needed, but for now just the grid
    // card.innerHTML = `<div class="info-card-header"><h4 class="info-card-title">Attributes</h4></div>`; 

    const grid = document.createElement('div');
    grid.className = 'kv-grid';

    PRIMARY_LINE_OVERHEAD_FIELDS.forEach(function (f) {
      var val = data && data[f.key];
      if (val === undefined || val === null || val === '') val = '—';
      else if (typeof val === 'number') val = Number(val);

      const item = document.createElement('div');
      item.className = 'kv-item';
      item.innerHTML = `<div class="kv-label">${f.label}</div><div class="kv-value">${val}</div>`;
      grid.appendChild(item);
    });

    card.appendChild(grid);
    contentDiv.appendChild(card);

    m.style.display = 'flex';
    m.tabIndex = -1;
    m.focus();
  }
  function closePrimaryLineOverheadModal() {
    if (_primaryLineOverheadModal) _primaryLineOverheadModal.style.display = 'none';
  }

  // --- Distribution Transformer modal ---
  var _distributionTransformerModal = null;
  var DISTRIBUTION_TRANSFORMER_FIELDS = [
    { key: 'id', label: 'ID' },
    { key: 'transformer_id', label: 'Transformer ID' },
    { key: 'from_primary_bus_id', label: 'From Primary Bus ID' },
    { key: 'to_secondary_bus_id', label: 'To Secondary Bus ID' },
    { key: 'primary_phasing', label: 'Primary Phasing' },
    { key: 'secondary_phasing', label: 'Secondary Phasing' },
    { key: 'installation_type', label: 'Installation Type' },
    { key: 'no_dts_in_bank', label: 'No. DTs in Bank' },
    { key: 'connection', label: 'Connection' },
    { key: 'kva_rating', label: 'kVA Rating' },
    { key: 'primary_voltage_kv', label: 'Primary Voltage (kV)' },
    { key: 'secondary_voltage_kv', label: 'Secondary Voltage (kV)' },
    { key: 'primary_tap_kv', label: 'Primary Tap (kV)' },
    { key: 'secondary_tap_kv', label: 'Secondary Tap (kV)' },
    { key: 'pct_z', label: '%Z' },
    { key: 'xr_ratio', label: 'X/R Ratio' },
    { key: 'no_load_loss_kw', label: 'No-Load Loss (kW)' },
    { key: 'exciting_current_pct', label: 'Exciting Current (%)' },
    { key: 'created_at', label: 'Created At' }
  ];
  function createDistributionTransformerModal() {
    if (_distributionTransformerModal) return _distributionTransformerModal;
    var overlay = document.createElement('div');
    overlay.className = 'modal-overlay distribution-transformer-modal-overlay';
    overlay.setAttribute('aria-label', 'Distribution Transformer');
    overlay.innerHTML = [
      '<div class="modal result-modal" style="max-width: 520px; width: 90vw;">',
      '  <div class="modal-header result-modal-header">',
      '    <h3 class="result-modal-title">Distribution Transformer</h3>',
      '    <button class="modal-close distribution-transformer-close" aria-label="Close">✕</button>',
      '  </div>',
      '  <div class="modal-body result-modal-body distribution-transformer-body enhanced-body" style="max-height: 70vh; overflow-y: auto;">',
      '    <div class="distribution-transformer-content"></div>',
      '  </div>',
      '  <div class="modal-footer"><button class="btn result-modal-ok distribution-transformer-ok">OK</button></div>',
      '</div>'
    ].join('');
    document.body.appendChild(overlay);
    overlay.querySelector('.distribution-transformer-close').addEventListener('click', closeDistributionTransformerModal);
    overlay.querySelector('.distribution-transformer-ok').addEventListener('click', closeDistributionTransformerModal);
    overlay.addEventListener('click', function (e) { if (e.target === overlay) closeDistributionTransformerModal(); });
    overlay.addEventListener('keydown', function (e) { if (e.key === 'Escape') closeDistributionTransformerModal(); });
    _distributionTransformerModal = overlay;
    return _distributionTransformerModal;
  }
  function showDistributionTransformerModal(data) {
    var m = createDistributionTransformerModal();
    var contentDiv = m.querySelector('.distribution-transformer-content');
    var title = m.querySelector('.result-modal-title');
    title.textContent = 'Distribution Transformer' + (data && data.transformer_id ? ' — ' + data.transformer_id : '');

    contentDiv.innerHTML = '';

    const card = document.createElement('div');
    card.className = 'info-card';
    // card.innerHTML = `<div class="info-card-header"><h4 class="info-card-title">Equipment Details</h4></div>`;

    const grid = document.createElement('div');
    grid.className = 'kv-grid';

    DISTRIBUTION_TRANSFORMER_FIELDS.forEach(function (f) {
      var val = data && data[f.key];
      if (val === undefined || val === null || val === '') val = '—';
      else if (f.key === 'created_at' && val) {
        try {
          var d = new Date(val);
          val = d.toLocaleString();
        } catch (e) {
          val = String(val);
        }
      } else if (typeof val === 'number') {
        val = Number(val);
      }

      const item = document.createElement('div');
      item.className = 'kv-item';
      item.innerHTML = `<div class="kv-label">${f.label}</div><div class="kv-value">${val}</div>`;
      grid.appendChild(item);
    });

    card.appendChild(grid);
    contentDiv.appendChild(card);

    m.style.display = 'flex';
    m.tabIndex = -1;
    m.focus();
  }
  function closeDistributionTransformerModal() {
    if (_distributionTransformerModal) _distributionTransformerModal.style.display = 'none';
  }

  // --- Secondary Line modal ---
  var _secondaryLineModal = null;
  var SECONDARY_LINE_FIELDS = [
    { key: 'secondary_line_id', label: 'Secondary Line ID' },
    { key: 'from_bus_id', label: 'From Bus ID' },
    { key: 'to_bus_id', label: 'To Bus ID' },
    { key: 'phasing', label: 'Phasing' },
    { key: 'conductor_type', label: 'Conductor Type' },
    { key: 'conductor_size', label: 'Conductor Size' },
    { key: 'conductor_unit', label: 'Unit' },
    { key: 'length_meters', label: 'Length (m)' },
    { key: 'system_grounding_type', label: 'System Grounding' },
    { key: 'neutral_wire_type', label: 'Neutral Wire Type' },
    { key: 'neutral_wire_size', label: 'Neutral Wire Size' }
  ];

  function createSecondaryLineModal() {
    if (_secondaryLineModal) return _secondaryLineModal;
    var overlay = document.createElement('div');
    overlay.className = 'modal-overlay secondary-line-modal-overlay';
    overlay.setAttribute('aria-label', 'Secondary Lines');
    overlay.innerHTML = [
      '<div class="modal result-modal" style="max-width: 600px; width: 90vw;">',
      '  <div class="modal-header result-modal-header">',
      '    <h3 class="result-modal-title">Secondary Lines</h3>',
      '    <button class="modal-close secondary-line-close" aria-label="Close">✕</button>',
      '  </div>',
      '  <div class="modal-body result-modal-body secondary-line-body enhanced-body" style="max-height: 70vh; overflow-y: auto;">',
      '    <div class="secondary-line-content"></div>',
      '  </div>',
      '  <div class="modal-footer"><button class="btn result-modal-ok secondary-line-ok">OK</button></div>',
      '</div>'
    ].join('');
    document.body.appendChild(overlay);
    overlay.querySelector('.secondary-line-close').addEventListener('click', closeSecondaryLineModal);
    overlay.querySelector('.secondary-line-ok').addEventListener('click', closeSecondaryLineModal);
    overlay.addEventListener('click', function (e) { if (e.target === overlay) closeSecondaryLineModal(); });
    overlay.addEventListener('keydown', function (e) { if (e.key === 'Escape') closeSecondaryLineModal(); });
    _secondaryLineModal = overlay;
    return _secondaryLineModal;
  }

  function showSecondaryLineModal(data) {
    var m = createSecondaryLineModal();
    var contentDiv = m.querySelector('.secondary-line-content');
    var title = m.querySelector('.result-modal-title');

    title.textContent = 'Secondary Lines (' + (data.count || 0) + ')';
    contentDiv.innerHTML = '';

    if (!data.secondary_lines || data.secondary_lines.length === 0) {
      contentDiv.innerHTML = '<div class="info-card"><div class="kv-value" style="text-align:center; color:var(--text-secondary);">No secondary lines found for this bus.</div></div>';
    } else {
      // Create a list or series of DLs for multiple lines
      data.secondary_lines.forEach(function (line, idx) {

        var card = document.createElement('div');
        card.className = 'info-card';

        var lineId = line.secondary_line_id ? line.secondary_line_id : `Line #${idx + 1}`;
        card.innerHTML = `<div class="info-card-header"><h4 class="info-card-title">${lineId}</h4></div>`;

        var grid = document.createElement('div');
        grid.className = 'kv-grid';

        SECONDARY_LINE_FIELDS.forEach(function (f) {
          var val = line[f.key];
          if (val === undefined || val === null || val === '') return; // Skip empty
          if (typeof val === 'number') val = Number(val);

          var item = document.createElement('div');
          item.className = 'kv-item';
          item.innerHTML = `<div class="kv-label">${f.label}</div><div class="kv-value">${val}</div>`;
          grid.appendChild(item);
        });

        card.appendChild(grid);
        contentDiv.appendChild(card);
      });
    }

    m.style.display = 'flex';
    m.tabIndex = -1;
    m.focus();
  }

  function closeSecondaryLineModal() {
    if (_secondaryLineModal) _secondaryLineModal.style.display = 'none';
  }

  // --- Secondary Service Drop modal ---
  var _serviceDropModal = null;
  var SERVICE_DROP_FIELDS = [
    { key: 'service_drop_id', label: 'Service Drop ID' },
    { key: 'to_customer_id', label: 'Customer ID' },
    { key: 'phasing', label: 'Phasing' },
    { key: 'installation_type', label: 'Installation Type' },
    { key: 'conductor_type', label: 'Conductor Type' },
    { key: 'conductor_size', label: 'Conductor Size' },
    { key: 'conductor_unit', label: 'Unit' },
    { key: 'length_meters_1', label: 'Length-1 (m)' },
    { key: 'length_meters_2', label: 'Length-2 (m)' }
  ];

  function createServiceDropModal() {
    if (_serviceDropModal) return _serviceDropModal;
    var overlay = document.createElement('div');
    overlay.className = 'modal-overlay service-drop-modal-overlay';
    overlay.setAttribute('aria-label', 'Service Drops');
    overlay.innerHTML = [
      '<div class="modal result-modal" style="max-width: 600px; width: 90vw;">',
      '  <div class="modal-header result-modal-header">',
      '    <h3 class="result-modal-title">Secondary Service Drops</h3>',
      '    <button class="modal-close service-drop-close" aria-label="Close">✕</button>',
      '  </div>',
      '  <div class="modal-search-container" style="padding: 12px 16px; border-bottom: 1px solid var(--border);">',
      '    <input type="text" class="service-drop-search" placeholder="Search by Customer ID, Drop ID, or Phase..." style="width: 100%; padding: 8px 12px; border: 1px solid var(--border); border-radius: 4px; font-size: 0.9rem;">',
      '  </div>',
      '  <div class="modal-body result-modal-body service-drop-body enhanced-body" style="max-height: 60vh; overflow-y: auto; padding: 12px 16px;">',
      '    <div class="service-drop-content"></div>',
      '  </div>',
      '  <div class="modal-footer"><button class="btn result-modal-ok service-drop-ok">OK</button></div>',
      '</div>'
    ].join('');
    document.body.appendChild(overlay);
    overlay.querySelector('.service-drop-close').addEventListener('click', closeServiceDropModal);
    overlay.querySelector('.service-drop-ok').addEventListener('click', closeServiceDropModal);
    overlay.addEventListener('click', function (e) { if (e.target === overlay) closeServiceDropModal(); });
    overlay.addEventListener('keydown', function (e) { if (e.key === 'Escape') closeServiceDropModal(); });
    _serviceDropModal = overlay;
    return _serviceDropModal;
  }

  function showServiceDropModal(data) {
    var m = createServiceDropModal();
    var contentDiv = m.querySelector('.service-drop-content');
    var title = m.querySelector('.result-modal-title');
    var searchInput = m.querySelector('.service-drop-search');

    title.textContent = 'Service Drops (' + (data.count || 0) + ')';
    searchInput.value = ''; // Reset search on open

    const renderDrops = (filteredDrops) => {
      contentDiv.innerHTML = '';
      if (!filteredDrops || filteredDrops.length === 0) {
        contentDiv.innerHTML = '<div class="info-card" style="text-align:center; color:var(--text-secondary); padding: 20px;">No matching service drops found.</div>';
        return;
      }

      filteredDrops.forEach(function (drop, idx) {
        var card = document.createElement('div');
        card.className = 'info-card';

        // Header
        var header = document.createElement('div');
        header.className = 'info-card-header';

        var cardTitle = document.createElement('div');
        cardTitle.className = 'info-card-title';
        cardTitle.textContent = 'Drop #' + (idx + 1) + (drop.service_drop_id ? ' (' + drop.service_drop_id + ')' : '');
        header.appendChild(cardTitle);

        if (drop.to_customer_id) {
          var cBtn = document.createElement('button');
          cBtn.className = 'btn btn-sm';
          cBtn.style.fontSize = '0.8rem';
          cBtn.style.padding = '4px 12px';
          cBtn.textContent = 'View Customer Info';
          cBtn.onclick = function () { showCustomerInfoModal(drop.to_customer_id); };
          header.appendChild(cBtn);
        }
        card.appendChild(header);

        // Grid
        var grid = document.createElement('div');
        grid.className = 'kv-grid';

        SERVICE_DROP_FIELDS.forEach(function (f) {
          var val = drop[f.key];
          if (val === undefined || val === null || val === '') return;

          var item = document.createElement('div');
          item.className = 'kv-item';

          var label = document.createElement('div');
          label.className = 'kv-label';
          label.textContent = f.label;

          var value = document.createElement('div');
          value.className = 'kv-value';
          value.textContent = val;

          item.appendChild(label);
          item.appendChild(value);
          grid.appendChild(item);
        });
        card.appendChild(grid);
        contentDiv.appendChild(card);
      });
    };

    renderDrops(data.service_drops);

    searchInput.oninput = function () {
      var query = searchInput.value.toLowerCase().trim();
      var filtered = data.service_drops.filter(function (d) {
        return (d.to_customer_id && d.to_customer_id.toLowerCase().includes(query)) ||
          (d.service_drop_id && d.service_drop_id.toLowerCase().includes(query)) ||
          (d.phasing && d.phasing.toLowerCase().includes(query));
      });
      renderDrops(filtered);
    };

    m.style.display = 'flex';
    m.tabIndex = -1;
    m.focus();
  }

  function closeServiceDropModal() {
    if (_serviceDropModal) _serviceDropModal.style.display = 'none';
  }

  // --- Confirmation modal (replaces window.confirm) ---
  let _confirmModal = null;
  function createConfirmModal() {
    if (_confirmModal) return _confirmModal;
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay confirm-modal-overlay';
    overlay.setAttribute('aria-label', 'Confirm');
    overlay.innerHTML = `
      <div class="modal">
        <div class="modal-header">
          <h3 class="confirm-title">Confirm</h3>
          <button class="modal-close confirm-close" aria-label="Close">✕</button>
        </div>
        <div class="modal-body confirm-body">
          <p class="confirm-message"></p>
        </div>
        <div class="modal-footer">
          <button class="btn confirm-cancel">Cancel</button>
          <button class="btn btn-danger confirm-ok">Delete</button>
        </div>
      </div>
    `;
    document.body.appendChild(overlay);
    overlay.querySelector('.confirm-close').addEventListener('click', () => { overlay.style.display = 'none'; });
    overlay.querySelector('.confirm-cancel').addEventListener('click', () => { overlay.style.display = 'none'; });
    overlay.addEventListener('click', (e) => { if (e.target === overlay) overlay.style.display = 'none'; });
    overlay.addEventListener('keydown', (e) => { if (e.key === 'Escape') overlay.style.display = 'none'; });
    _confirmModal = overlay;
    return _confirmModal;
  }
  function showConfirmModal(message, opts) {
    opts = opts || {};
    const m = createConfirmModal();
    m.querySelector('.confirm-title').textContent = opts.title || 'Confirm';
    m.querySelector('.confirm-message').textContent = message || '';
    const ok = m.querySelector('.confirm-ok');
    ok.textContent = opts.okText || 'Delete';
    const cancel = m.querySelector('.confirm-cancel');
    cancel.textContent = opts.cancelText || 'Cancel';
    m.style.display = 'flex';
    m.tabIndex = -1;
    m.focus();
    return new Promise((resolve) => {
      function cleanup() {
        ok.removeEventListener('click', onOk);
        cancel.removeEventListener('click', onCancel);
        m.style.display = 'none';
      }
      function onOk() { cleanup(); resolve(true); }
      function onCancel() { cleanup(); resolve(false); }
      ok.addEventListener('click', onOk);
      cancel.addEventListener('click', onCancel);
    });
  }

  // --- Notice modal (replaces alert) ---
  let _noticeModal = null;
  function createNoticeModal() {
    if (_noticeModal) return _noticeModal;
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay notice-modal-overlay';
    overlay.setAttribute('aria-label', 'Notice');
    overlay.innerHTML = `
      <div class="modal">
        <div class="modal-header">
          <h3 class="notice-title">Notice</h3>
          <button class="modal-close notice-close" aria-label="Close">✕</button>
        </div>
        <div class="modal-body notice-body">
          <p class="notice-message"></p>
        </div>
        <div class="modal-footer">
          <button class="btn notice-ok">OK</button>
        </div>
      </div>
    `;
    document.body.appendChild(overlay);
    overlay.querySelector('.notice-close').addEventListener('click', () => { overlay.style.display = 'none'; });
    overlay.querySelector('.notice-ok').addEventListener('click', () => { overlay.style.display = 'none'; });
    overlay.addEventListener('click', (e) => { if (e.target === overlay) overlay.style.display = 'none'; });
    overlay.addEventListener('keydown', (e) => { if (e.key === 'Escape') overlay.style.display = 'none'; });
    _noticeModal = overlay;
    return _noticeModal;
  }
  function showNoticeModal(title, message) {
    const m = createNoticeModal();
    m.querySelector('.notice-title').textContent = title || 'Notice';
    m.querySelector('.notice-message').innerHTML = message || '';
    m.style.display = 'flex';
    m.tabIndex = -1;
    m.focus();
  }

  // Save a connection from the current points
  function saveConnection(nameArg) {
    if (connectionPoints.length < 2) { showNoticeModal('Info', 'Add at least two points to save a connection.'); return; }
    let name = nameArg;
    if (!name) name = prompt('Name this connection', `Connection ${new Date().toISOString().slice(0, 19)}`) || 'Connection';
    hideConnectionHint();
    // Send a plain array of { post_id, lat, lng } so backend never receives a dict or non-numeric values
    var pointsPayload = connectionPoints.map(function (pt) {
      var lat = parseFloat(pt.lat);
      var lng = parseFloat(pt.lng);
      return {
        post_id: pt.post_id != null ? parseInt(pt.post_id, 10) : null,
        lat: Number.isFinite(lat) ? lat : 0,
        lng: Number.isFinite(lng) ? lng : 0
      };
    });
    fetch('/api/connections', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: name, points: pointsPayload })
    }).then(r => r.json())
      .then(j => {
        if (j && j.created && j.created.length > 0) {
          var totalLen = j.created.reduce(function (sum, c) { return sum + (c.total_length || 0); }, 0);
          showResultModal({
            id: j.created.length === 1 ? j.created[0].id : null,
            name: name,
            length: totalLen,
            count: j.count || j.created.length,
            message: (j.count || j.created.length) > 1
              ? (j.count + ' post-to-post connection(s) saved. Total length: ' + (totalLen >= 1000 ? (totalLen / 1000).toFixed(2) + ' km' : Math.round(totalLen) + ' m'))
              : null
          });
          clearConnection();
          loadConnections();
        } else if (j && j.error) {
          showResultModal({ error: true, message: j.error });
        }
      }).catch(err => {
        showResultModal({ error: true, message: 'Save failed: ' + (err && err.message ? err.message : String(err)) });
      });
  }

  function loadConnections() {
    fetch('/api/connections')
      .then(r => r.json())
      .then(arr => {
        connectionsLayer.clearLayers();
        endpointsLayer.clearLayers();
        arr.forEach(c => {
          const latlngs = c.points.map(p => [p.lat, p.lng]);
          const postList = c.points.map(p => p.post_id ? `#${p.post_id}` : `${p.lat.toFixed(6)},${p.lng.toFixed(6)}`).join(', ');
          const popupHtml = `
            <div>
              <strong>${c.name}</strong><br/>
              Length: ${formatMeters(c.total_length || 0)}<br/>
              Points: ${c.points.length}<br/>
              Connected IDs: ${postList}
            </div>
            <div style="margin-top:8px;">
              <button class="btn disconnect-conn" data-conn-id="${c.id}">Disconnect</button>
            </div>
          `;
          const poly = L.polyline(latlngs, { color: '#0066ff', weight: 3, lineCap: 'round' }).addTo(connectionsLayer);
          poly.bindPopup(popupHtml);

          // Invisible, wider polyline to make clicking the connection easier
          const buffer = L.polyline(latlngs, { color: 'transparent', weight: 20, opacity: 0, className: 'click-buffer' }).addTo(connectionsLayer);
          buffer.on('click', function () { poly.openPopup(); highlightPoly(poly); });
          poly.on('click', function () { poly.openPopup(); highlightPoly(poly); });

          // Add non-interactive endpoint markers for each point to ensure visual match
          c.points.forEach(pt => {
            L.circleMarker([pt.lat, pt.lng], { radius: 5, color: '#0066ff', fillColor: '#fff', weight: 2, interactive: false }).addTo(endpointsLayer);
          });

          // Attach handler when popup opens
          poly.on('popupopen', function () {
            const el = poly.getPopup().getElement();
            if (!el) return;
            const btn = el.querySelector('.disconnect-conn');
            if (!btn) return;
            btn.addEventListener('click', function (ev) {
              ev.preventDefault();
              const id = btn.getAttribute('data-conn-id');
              showConfirmModal('Disconnect and delete this connection?', { title: 'Delete connection', okText: 'Delete', cancelText: 'Cancel' })
                .then(function (confirmed) {
                  if (!confirmed) return;
                  fetch('/api/connections/' + id, { method: 'DELETE' })
                    .then(r => r.json())
                    .then(j => {
                      if (j && j.result === 'deleted') {
                        showNoticeModal('Deleted', 'Connection deleted');
                        loadConnections();
                      } else {
                        showNoticeModal('Delete failed', 'Delete failed: ' + JSON.stringify(j));
                      }
                    }).catch(err => showNoticeModal('Delete failed', 'Delete failed: ' + err));
                });
            });
          });
        });
      }).catch(err => console.error('Failed to load connections', err));
  }

  // Load existing connections on start
  // Note: /api/connections endpoint not implemented - skipping
  // loadConnections();

  // --- Bulk selection / connect UI ---
  window._selectionMode = false;
  const selectedOrder = []; // preserve order of selection
  function toggleSelect(postId, lat, lng, marker) {
    const idx = selectedOrder.indexOf(postId);
    if (idx === -1) {
      selectedOrder.push(postId);
      try { marker.setOpacity(0.6); } catch (e) { }
    } else {
      selectedOrder.splice(idx, 1);
      try { marker.setOpacity(1); } catch (e) { }
    }
    updateSelectionBadge();
  }

  function clearSelection() {
    selectedOrder.slice().forEach(id => {
      const m = postMarkers[id]; if (m) try { m.setOpacity(1); } catch (e) { }
    });
    selectedOrder.length = 0;
    updateSelectionBadge();
  }

  function updateSelectionBadge() {
    const el = document.querySelector('.map-selection-badge');
    if (!el) return;
    el.textContent = selectedOrder.length ? String(selectedOrder.length) : '';
  }

  function connectSelected() {
    if (selectedOrder.length < 2) { showNoticeModal('Info', 'Select at least two posts to connect.'); return; }
    const points = selectedOrder.map(id => {
      const m = postMarkers[id];
      if (!m) return null;
      const latlng = m.getLatLng();
      return { post_id: id, lat: latlng.lat, lng: latlng.lng };
    }).filter(Boolean);
    if (points.length < 2) { showNoticeModal('Info', 'Selected posts do not have valid coordinates.'); return; }
    const name = 'Bulk connect';
    fetch('/api/connections', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name: name, points: points }) })
      .then(r => r.json()).then(j => {
        if (j && j.created) {
          showResultModal({ name: name, length: j.created.reduce((s, c) => s + (c.total_length || 0), 0), count: j.count || j.created.length });
          clearSelection();
          loadConnections();
        } else if (j && j.error) {
          showResultModal({ error: true, message: j.error });
        }
      }).catch(err => showResultModal({ error: true, message: 'Save failed: ' + err }));
  }

  // --- New Asset Modals ---

  // Voltage Regulator
  let _vrModal = null;
  const VR_FIELDS = [
    { key: 'regulator_id', label: 'ID' },
    { key: 'from_bus_id', label: 'From Bus' },
    { key: 'to_bus_id', label: 'To Bus' },
    { key: 'regulated_bus_id', label: 'Regulated Bus' },
    { key: 'phase_type', label: 'Phase Type' },
    { key: 'phasing', label: 'Phasing' },
    { key: 'kva_rating', label: 'KVA' },
    { key: 'kv_rating', label: 'KV' },
    { key: 'target_voltage', label: 'Target V' },
    { key: 'bandwidth', label: 'Bandwidth' },
    { key: 'pt_ratio', label: 'PT Ratio' },
    { key: 'primary_current_rating', label: 'Pri. Current (A)' }
  ];

  function createVRModal() {
    if (_vrModal) return _vrModal;
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.innerHTML = `
      <div class="modal result-modal">
        <div class="modal-header">
          <h3 class="result-modal-title">Voltage Regulators</h3>
          <button class="modal-close vr-close">✕</button>
        </div>
        <div class="modal-body result-modal-body vr-content enhanced-body" style="max-height: 70vh; overflow-y: auto;"></div>
        <div class="modal-footer">
          <button class="btn btn-primary vr-ok">Close</button>
        </div>
      </div>
    `;
    document.body.appendChild(overlay);
    overlay.querySelector('.vr-close').addEventListener('click', () => overlay.style.display = 'none');
    overlay.querySelector('.vr-ok').addEventListener('click', () => overlay.style.display = 'none');
    overlay.addEventListener('click', (e) => { if (e.target === overlay) overlay.style.display = 'none'; });
    _vrModal = overlay;
    return _vrModal;
  }

  function showVoltageRegulatorModal(data) {
    const m = createVRModal();
    const content = m.querySelector('.vr-content');
    const title = m.querySelector('.result-modal-title');
    title.textContent = 'Voltage Regulators (' + (data.count || 0) + ')';
    content.innerHTML = '';

    if (!data.items || data.items.length === 0) {
      content.innerHTML = '<div class="info-card"><div class="kv-value" style="text-align:center;">No items found.</div></div>';
    } else {
      data.items.forEach((item, idx) => {
        const card = document.createElement('div');
        card.className = 'info-card';
        card.innerHTML = `<div class="info-card-header"><h4 class="info-card-title">Item #${idx + 1} (${item.regulator_id || ''})</h4></div>`;

        const grid = document.createElement('div');
        grid.className = 'kv-grid';

        VR_FIELDS.forEach(f => {
          let val = item[f.key];
          if (val !== undefined && val !== null && val !== '') {
            const itemEl = document.createElement('div');
            itemEl.className = 'kv-item';
            itemEl.innerHTML = `<div class="kv-label">${f.label}</div><div class="kv-value">${val}</div>`;
            grid.appendChild(itemEl);
          }
        });
        card.appendChild(grid);
        content.appendChild(card);
      });
    }
    m.style.display = 'flex';
  }

  // Shunt Capacitor
  let _scModal = null;
  const SC_FIELDS = [
    { key: 'capacitor_id', label: 'ID' },
    { key: 'bus_connected_id', label: 'Bus' },
    { key: 'phase_type', label: 'Phase Type' },
    { key: 'phasing', label: 'Phasing' },
    { key: 'voltage_rating_kv', label: 'Voltage (kV)' },
    { key: 'kvar_rating_a', label: 'KVAR (A)' },
    { key: 'kvar_rating_b', label: 'KVAR (B)' },
    { key: 'kvar_rating_c', label: 'KVAR (C)' },
    { key: 'power_loss_watts', label: 'Power Loss (W)' }
  ];

  function createSCModal() {
    if (_scModal) return _scModal;
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.innerHTML = `
      <div class="modal result-modal">
        <div class="modal-header">
          <h3 class="result-modal-title">Shunt Capacitors</h3>
          <button class="modal-close sc-close">✕</button>
        </div>
        <div class="modal-body result-modal-body sc-content enhanced-body" style="max-height: 70vh; overflow-y: auto;"></div>
        <div class="modal-footer">
          <button class="btn btn-primary sc-ok">Close</button>
        </div>
      </div>
    `;
    document.body.appendChild(overlay);
    overlay.querySelector('.sc-close').addEventListener('click', () => overlay.style.display = 'none');
    overlay.querySelector('.sc-ok').addEventListener('click', () => overlay.style.display = 'none');
    overlay.addEventListener('click', (e) => { if (e.target === overlay) overlay.style.display = 'none'; });
    _scModal = overlay;
    return _scModal;
  }

  function showShuntCapacitorModal(data) {
    const m = createSCModal();
    const content = m.querySelector('.sc-content');
    const title = m.querySelector('.result-modal-title');
    title.textContent = 'Shunt Capacitors (' + (data.count || 0) + ')';
    content.innerHTML = '';

    if (!data.items || data.items.length === 0) {
      content.innerHTML = '<div class="info-card"><div class="kv-value" style="text-align:center;">No items found.</div></div>';
    } else {
      data.items.forEach((item, idx) => {
        const card = document.createElement('div');
        card.className = 'info-card';
        card.innerHTML = `<div class="info-card-header"><h4 class="info-card-title">Item #${idx + 1} (${item.capacitor_id || ''})</h4></div>`;

        const grid = document.createElement('div');
        grid.className = 'kv-grid';

        SC_FIELDS.forEach(f => {
          let val = item[f.key];
          if (val !== undefined && val !== null && val !== '') {
            const itemEl = document.createElement('div');
            itemEl.className = 'kv-item';
            itemEl.innerHTML = `<div class="kv-label">${f.label}</div><div class="kv-value">${val}</div>`;
            grid.appendChild(itemEl);
          }
        });
        card.appendChild(grid);
        content.appendChild(card);
      });
    }
    m.style.display = 'flex';
  }

  // Shunt Inductor
  let _siModal = null;
  const SI_FIELDS = [
    { key: 'inductor_id', label: 'ID' },
    { key: 'bus_connected_id', label: 'Bus' },
    { key: 'phase_type', label: 'Phase Type' },
    { key: 'phasing', label: 'Phasing' },
    { key: 'voltage_rating_kv', label: 'Voltage (kV)' },
    { key: 'resistance_a', label: 'R (A)' },
    { key: 'reactance_a', label: 'X (A)' }
  ];

  function createSIModal() {
    if (_siModal) return _siModal;
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.innerHTML = `
      <div class="modal result-modal">
        <div class="modal-header">
          <h3 class="result-modal-title">Shunt Inductors</h3>
          <button class="modal-close si-close">✕</button>
        </div>
        <div class="modal-body result-modal-body si-content enhanced-body" style="max-height: 70vh; overflow-y: auto;"></div>
        <div class="modal-footer">
          <button class="btn btn-primary si-ok">Close</button>
        </div>
      </div>
    `;
    document.body.appendChild(overlay);
    overlay.querySelector('.si-close').addEventListener('click', () => overlay.style.display = 'none');
    overlay.querySelector('.si-ok').addEventListener('click', () => overlay.style.display = 'none');
    overlay.addEventListener('click', (e) => { if (e.target === overlay) overlay.style.display = 'none'; });
    _siModal = overlay;
    return _siModal;
  }

  function showShuntInductorModal(data) {
    const m = createSIModal();
    const content = m.querySelector('.si-content');
    const title = m.querySelector('.result-modal-title');
    title.textContent = 'Shunt Inductors (' + (data.count || 0) + ')';
    content.innerHTML = '';

    if (!data.items || data.items.length === 0) {
      content.innerHTML = '<div class="info-card"><div class="kv-value" style="text-align:center;">No items found.</div></div>';
    } else {
      data.items.forEach((item, idx) => {
        const card = document.createElement('div');
        card.className = 'info-card';
        card.innerHTML = `<div class="info-card-header"><h4 class="info-card-title">Item #${idx + 1} (${item.inductor_id || ''})</h4></div>`;

        const grid = document.createElement('div');
        grid.className = 'kv-grid';

        SI_FIELDS.forEach(f => {
          let val = item[f.key];
          if (val !== undefined && val !== null && val !== '') {
            const itemEl = document.createElement('div');
            itemEl.className = 'kv-item';
            itemEl.innerHTML = `<div class="kv-label">${f.label}</div><div class="kv-value">${val}</div>`;
            grid.appendChild(itemEl);
          }
        });
        card.appendChild(grid);
        content.appendChild(card);
      });
    }
    m.style.display = 'flex';
  }

  // Series Inductor
  let _eriModal = null;
  const ERI_FIELDS = [
    { key: 'inductor_id', label: 'ID' },
    { key: 'from_bus_id', label: 'From Bus' },
    { key: 'to_bus_id', label: 'To Bus' },
    { key: 'phase_type', label: 'Phase Type' },
    { key: 'phasing', label: 'Phasing' },
    { key: 'voltage_rating_kv', label: 'Voltage (kV)' },
    { key: 'resistance_a', label: 'R (A)' },
    { key: 'reactance_a', label: 'X (A)' }
  ];

  function createERIModal() {
    if (_eriModal) return _eriModal;
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.innerHTML = `
      <div class="modal result-modal">
        <div class="modal-header">
          <h3 class="result-modal-title">Series Inductors</h3>
          <button class="modal-close eri-close">✕</button>
        </div>
        <div class="modal-body result-modal-body eri-content enhanced-body" style="max-height: 70vh; overflow-y: auto;"></div>
        <div class="modal-footer">
          <button class="btn btn-primary eri-ok">Close</button>
        </div>
      </div>
    `;
    document.body.appendChild(overlay);
    overlay.querySelector('.eri-close').addEventListener('click', () => overlay.style.display = 'none');
    overlay.querySelector('.eri-ok').addEventListener('click', () => overlay.style.display = 'none');
    overlay.addEventListener('click', (e) => { if (e.target === overlay) overlay.style.display = 'none'; });
    _eriModal = overlay;
    return _eriModal;
  }

  function showSeriesInductorModal(data) {
    const m = createERIModal();
    const content = m.querySelector('.eri-content');
    const title = m.querySelector('.result-modal-title');
    title.textContent = 'Series Inductors (' + (data.count || 0) + ')';
    content.innerHTML = '';

    if (!data.items || data.items.length === 0) {
      content.innerHTML = '<div class="info-card"><div class="kv-value" style="text-align:center;">No items found.</div></div>';
    } else {
      data.items.forEach((item, idx) => {
        const card = document.createElement('div');
        card.className = 'info-card';
        card.innerHTML = `<div class="info-card-header"><h4 class="info-card-title">Item #${idx + 1} (${item.inductor_id || ''})</h4></div>`;

        const grid = document.createElement('div');
        grid.className = 'kv-grid';

        ERI_FIELDS.forEach(f => {
          let val = item[f.key];
          if (val !== undefined && val !== null && val !== '') {
            const itemEl = document.createElement('div');
            itemEl.className = 'kv-item';
            itemEl.innerHTML = `<div class="kv-label">${f.label}</div><div class="kv-value">${val}</div>`;
            grid.appendChild(itemEl);
          }
        });
        card.appendChild(grid);
        content.appendChild(card);
      });
    }
    m.style.display = 'flex';
  }

  // --- Customer Info Modal ---
  var _customerInfoModal = null;
  function createCustomerInfoModal() {
    if (_customerInfoModal) return _customerInfoModal;
    var overlay = document.createElement('div');
    overlay.className = 'modal-overlay customer-info-modal-overlay';
    overlay.setAttribute('aria-label', 'Customer Info');
    overlay.innerHTML = [
      '<div class="modal result-modal" style="max-width: 600px; width: 90vw;">',
      '  <div class="modal-header result-modal-header">',
      '    <h3 class="result-modal-title">Customer Info</h3>',
      '    <button class="modal-close customer-info-close" aria-label="Close">✕</button>',
      '  </div>',
      '  <div class="modal-body result-modal-body customer-info-body enhanced-body" style="max-height: 70vh; overflow-y: auto; padding: 16px;">',
      '    <div class="customer-details" style="margin-bottom: 20px;"></div>',
      '    <h4 style="margin-bottom: 10px; border-bottom: 2px solid #eee; padding-bottom: 5px;">Energy Consumption</h4>',
      '    <div class="customer-consumption"></div>',
      '  </div>',
      '  <div class="modal-footer"><button class="btn result-modal-ok customer-info-ok">Close</button></div>',
      '</div>'
    ].join('');
    document.body.appendChild(overlay);
    overlay.querySelector('.customer-info-close').addEventListener('click', closeCustomerInfoModal);
    overlay.querySelector('.customer-info-ok').addEventListener('click', closeCustomerInfoModal);
    overlay.addEventListener('click', function (e) { if (e.target === overlay) closeCustomerInfoModal(); });
    overlay.addEventListener('keydown', function (e) { if (e.key === 'Escape') closeCustomerInfoModal(); });
    _customerInfoModal = overlay;
    return _customerInfoModal;
  }

  function closeCustomerInfoModal() {
    if (_customerInfoModal) _customerInfoModal.style.display = 'none';
  }

  // --- Connections Modal ---
  let connectionsModalStub = null;
  function showConnectionsModal(connections, postId) {
    if (connectionsModalStub) {
      if (connectionsModalStub.parentNode) document.body.removeChild(connectionsModalStub);
      connectionsModalStub = null;
    }

    // Create modal elements
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay connections-modal-overlay';
    overlay.innerHTML = `
        <div class="modal connections-modal" style="max-width: 500px; width: 90%;">
            <div class="modal-header">
                <h3>Connected Lines for Post #${postId}</h3>
                <button class="modal-close" aria-label="Close">✕</button>
            </div>
            <div class="modal-body">
                <div class="connections-list" style="max-height: 400px; overflow-y: auto; padding-right: 4px;">
                    ${connections.map(conn => `
                        <div class="connection-item" style="display: flex; justify-content: space-between; align-items: center; padding: 12px; border-bottom: 1px solid #eee; gap: 12px;">
                            <div class="connection-info">
                                <div style="font-weight: 600; color: var(--text-primary); margin-bottom: 2px;">
                                    ${conn.name || 'Unknown Segment'}
                                </div>
                                <div style="font-size: 0.85rem; color: var(--text-secondary);">
                                    ${conn.type} • ID: ${conn.id}
                                </div>
                                <div style="font-size: 0.8rem; color: #666; margin-top: 2px;">
                                    ${conn.from_bus} → ${conn.to_bus}
                                </div>
                            </div>
                        </div>
                    `).join('')}
                </div>
            </div>
            <div class="modal-footer">
                <button class="btn btn-secondary modal-close-btn">Close</button>
            </div>
        </div>
    `;

    document.body.appendChild(overlay);
    connectionsModalStub = overlay;
    overlay.style.display = 'flex'; // Ensure flex display

    // Handlers
    const close = () => {
      overlay.style.display = 'none';
      if (overlay.parentNode) document.body.removeChild(overlay);
      connectionsModalStub = null;
    };

    overlay.querySelector('.modal-close').onclick = close;
    overlay.querySelector('.modal-close-btn').onclick = close;
    overlay.onclick = (e) => { if (e.target === overlay) close(); };

    // Disconnect handlers
    overlay.querySelectorAll('.btn-disconnect').forEach(btn => {
      btn.onclick = function () {
        const id = this.getAttribute('data-id');
        showConfirmModal(`Are you sure you want to disconnect ${id}? (This is a simulation)`, { title: 'Disconnect', okText: 'Disconnect', cancelText: 'Cancel' })
          .then(confirmed => {
            if (confirmed) {
              showNoticeModal('Info', `Disconnected ${id} (Mock Action)`);
              // logical removal from UI could happen here
              this.closest('.connection-item').style.opacity = '0.5';
              this.disabled = true;
              this.textContent = 'Disconnected';
            }
          });
      };
    });
  }

  window.showCustomerInfoModal = function (customerId) {
    if (!customerId) return;
    var m = createCustomerInfoModal();
    var detailsDiv = m.querySelector('.customer-details');
    var consDiv = m.querySelector('.customer-consumption');

    detailsDiv.innerHTML = '<div class="spinner"></div> Loading details...';
    consDiv.innerHTML = '';
    m.style.display = 'flex';

    // Fetch Customer Data
    fetch('/api/customers/' + encodeURIComponent(customerId))
      .then(function (r) { return r.json(); })
      .then(function (cData) {
        if (cData.error) {
          detailsDiv.innerHTML = '<p style="color:red">Error: ' + cData.error + '</p>';
          return;
        }

        var html = '<div class="info-card">';
        html += '<div class="info-card-header"><h4 class="info-card-title">Account Details</h4></div>';
        html += '<div class="kv-grid">';
        html += '<div class="kv-item"><div class="kv-label">Customer Name</div><div class="kv-value">' + (cData.name || '—') + '</div></div>';
        html += '<div class="kv-item"><div class="kv-label">Customer ID</div><div class="kv-value">' + (cData.customer_id || '—') + '</div></div>';
        html += '<div class="kv-item"><div class="kv-label">Type</div><div class="kv-value">' + (cData.customer_type || '—') + '</div></div>';
        html += '<div class="kv-item"><div class="kv-label">Service Voltage</div><div class="kv-value">' + (cData.service_voltage || '—') + '</div></div>';
        html += '<div class="kv-item"><div class="kv-label">Phase</div><div class="kv-value">' + (cData.phase || '—') + '</div></div>';
        html += '</div></div>';
        detailsDiv.innerHTML = html;

        // Fetch Consumption Data
        fetch('/api/customers/' + encodeURIComponent(customerId) + '/consumption')
          .then(function (r) { return r.json(); })
          .then(function (consData) {
            if (consData.error) {
              consDiv.innerHTML = '<div class="info-card" style="color:#b91c1c;">Error loading consumption.</div>';
              return;
            }
            if (!consData.items || consData.items.length === 0) {
              consDiv.innerHTML = '<div class="info-card" style="color:var(--text-secondary); text-align:center;">No consumption records found.</div>';
              return;
            }

            var table = '<div class="table-scroll" style="border:1px solid var(--border); border-radius:var(--radius-md); overflow:hidden;"><table class="modern-table">';
            table += '<thead><tr>';
            table += '<th>Billing Period</th>';
            table += '<th>Energy (kWh)</th>';
            table += '<th>Power Factor</th>';
            table += '</tr></thead><tbody>';

            consData.items.forEach(function (item) {
              table += '<tr>';
              table += '<td>' + (item.billing_period || '—') + '</td>';
              table += '<td>' + (item.kwh_consumed || '—') + '</td>';
              table += '<td>' + (item.power_factor || '—') + '</td>';
              table += '</tr>';
            });
            table += '</tbody></table></div>';
            consDiv.innerHTML = table;
          })
          .catch(function (e) {
            consDiv.innerHTML = '<div class="info-card" style="color:#b91c1c;">Failed to load consumption.</div>';
          });
      })
      .catch(function (e) {
        detailsDiv.innerHTML = '<p style="color:red">Failed to load customer details.</p>';
      });
  };


  // ═══════════════════════════════════════════════════════
  // CUSTOMER SEARCH BAR (Top-Right Corner)
  // ═══════════════════════════════════════════════════════

  // ── 1. Build expandable search icon HTML ──
  var searchIconHTML = `
    <div class="expandable-search-wrapper">
      <button id="search-icon-btn" class="search-icon-btn" title="Search Customer">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 -960 960 960" fill="currentColor">
          <path d="M784-120 532-372q-30 24-69 38t-83 14q-109 0-184.5-75.5T120-580q0-109 75.5-184.5T380-840q109 0 184.5 75.5T640-580q0 44-14 83t-38 69l252 252-56 56ZM380-400q75 0 127.5-52.5T560-580q0-75-52.5-127.5T380-760q-75 0-127.5 52.5T200-580q0 75 52.5 127.5T380-400Z"/>
        </svg>
      </button>
    </div>
  `;

  var expandedBarHTML = `
    <div id="search-bar-expanded" class="search-bar-expanded">
      <div style="position:relative;width:100%;">
        <input id="customer-search-input" class="top-search-input"
          type="text" placeholder="Customer ID…"
          autocomplete="off" spellcheck="false" />
        <button id="search-clear-btn" class="search-clear-btn" title="Clear Search">✕</button>
        <div id="customer-search-suggestions" class="customer-search-suggestions"></div>
      </div>
    </div>
  `;

  // Append search tools to the map-actions container
  var mapActions = document.getElementById('map-actions');
  if (!mapActions) {
    // Fallback if index.html hasn't been updated or in other pages
    var mapHeader = document.querySelector('.map-header');
    if (mapHeader) {
      mapActions = document.createElement('div');
      mapActions.className = 'map-actions';
      mapActions.id = 'map-actions';
      mapHeader.appendChild(mapActions);
    }
  }

  if (mapActions) {
    // Clear any existing content (like ghost elements or old buttons)
    mapActions.innerHTML = '';

    var searchContainer = document.createElement('div');
    searchContainer.className = 'expandable-search-container';
    searchContainer.innerHTML = searchIconHTML + expandedBarHTML;
    mapActions.appendChild(searchContainer);
  }

  // Append route result to body
  var routeResultWrapper = document.createElement('div');
  routeResultWrapper.innerHTML = '<div id="route-result" class="route-result" style="display:none;"></div>';
  document.body.appendChild(routeResultWrapper);

  // ── 1.5. Toggle search bar expansion ──
  var searchIconBtn = document.getElementById('search-icon-btn');
  var searchBarExpanded = document.getElementById('search-bar-expanded');
  var customerSearchInput = document.getElementById('customer-search-input');
  var customerSearchSuggestions = document.getElementById('customer-search-suggestions');
  var searchClearBtn = document.getElementById('search-clear-btn');

  function toggleSearchBar(show) {
    if (show === undefined) {
      show = !searchBarExpanded.classList.contains('active');
    }

    if (show) {
      searchBarExpanded.classList.add('active');
    } else {
      searchBarExpanded.classList.remove('active');
    }

    searchIconBtn.setAttribute('aria-expanded', show);

    if (show) {
      customerSearchInput.focus();
      customerSearchInput.select();
    } else {
      customerSearchInput.blur();
      customerSearchSuggestions.classList.remove('active');
    }
  }

  searchIconBtn.addEventListener('click', function (e) {
    e.stopPropagation();
    toggleSearchBar();
  });

  // Keyboard support
  customerSearchInput.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      toggleSearchBar(false);
      e.preventDefault();
    }
  });

  // Clear search when closing
  searchBarExpanded.addEventListener('focusout', function (e) {
    // Only close if focus moved outside the search bar
    if (!searchBarExpanded.contains(e.relatedTarget)) {
      // Don't automatically close, let user interact
    }
  });

  // ── 1.6. Customer Search functionality ──
  var customerSearchTimeout = null;
  var selectedCustomerData = null;
  var customerSearchHighlight = null;

  // Search customers as user types with loading state
  customerSearchInput.addEventListener('input', function (e) {
    clearTimeout(customerSearchTimeout);
    var query = e.target.value.trim();

    // Toggle clear button
    if (query.length > 0) {
      searchClearBtn.classList.add('active');
    } else {
      searchClearBtn.classList.remove('active');
    }

    if (!query || query.length < 1) {
      customerSearchSuggestions.classList.remove('active');
      return;
    }

    // Show loading state
    customerSearchSuggestions.innerHTML = '<div class="customer-search-item customer-search-loading">🔍 Searching...</div>';
    customerSearchSuggestions.classList.add('active');

    customerSearchTimeout = setTimeout(function () {
      fetch('/api/customers?q=' + encodeURIComponent(query) + '&per_page=5&skip_trace=true')
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (!data.data || data.data.length === 0) {
            customerSearchSuggestions.innerHTML = '<div class="customer-search-item customer-search-empty">No customers found</div>';
            customerSearchSuggestions.classList.add('active');
            return;
          }

          var html = data.data.map(function (cust, idx) {
            var name = cust.name || 'N/A';
            return '<div class="customer-search-item" data-customer-id="' + cust.customer_id + '" tabindex="' + idx + '">' +
              '<div class="customer-search-item-id">🏢 ' + cust.customer_id + '</div>' +
              '<div class="customer-search-item-name">' + name + '</div>' +
              '</div>';
          }).join('');

          customerSearchSuggestions.innerHTML = html;
          customerSearchSuggestions.classList.add('active');

          // Add click handlers to suggestions
          var items = customerSearchSuggestions.querySelectorAll('.customer-search-item');
          items.forEach(function (item) {
            item.addEventListener('click', function (e) {
              e.stopPropagation();
              var customerId = item.getAttribute('data-customer-id');
              selectCustomer(customerId);
            });
            item.addEventListener('keydown', function (e) {
              if (e.key === 'Enter') {
                var customerId = item.getAttribute('data-customer-id');
                selectCustomer(customerId);
              }
            });
          });
        })
        .catch(function (err) {
          console.error('Customer search error:', err);
          customerSearchSuggestions.innerHTML = '<div class="customer-search-item customer-search-error">⚠️ Error loading customers</div>';
          customerSearchSuggestions.classList.add('active');
        });
    }, 300);
  });

  // Clear button logic
  searchClearBtn.addEventListener('click', function (e) {
    e.stopPropagation();
    customerSearchInput.value = '';
    searchClearBtn.classList.remove('active');
    customerSearchSuggestions.classList.remove('active');
    customerSearchInput.focus();

    // Clear highlights and routes
    if (customerSearchHighlight) {
      map.removeLayer(customerSearchHighlight);
      customerSearchHighlight = null;
    }
    clearRoute();
  });

  // Hide suggestions and close search when clicking elsewhere
  document.addEventListener('click', function (e) {
    if (!searchBarExpanded.contains(e.target) && e.target !== searchIconBtn && !searchIconBtn.contains(e.target)) {
      customerSearchSuggestions.classList.remove('active');
    }
  });

  function selectCustomer(customerId) {
    // Show loading state
    customerSearchInput.value = customerId;
    customerSearchSuggestions.innerHTML = '<div class="customer-search-item customer-search-loading" style="padding: 12px; text-align: center; color: var(--text-secondary);">⏳ Locating and calculating route...</div>';
    customerSearchSuggestions.classList.add('active');

    // Fetch customer location and details
    fetch('/api/customers/' + encodeURIComponent(customerId) + '/location')
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (!data.found || !data.customer) {
          customerSearchSuggestions.innerHTML = '<div class="customer-search-item customer-search-error" style="padding: 12px; text-align: center; color: #dc2626;">⚠️ Customer not found</div>';
          setTimeout(function () { customerSearchSuggestions.classList.remove('active'); }, 2000);
          return;
        }

        selectedCustomerData = data;

        // Highlight customer location on map if post location exists
        if (data.connected_post) {
          // Clear previous highlight
          if (customerSearchHighlight) {
            map.removeLayer(customerSearchHighlight);
          }

          // Add highlight marker
          var lat = data.connected_post.lat;
          var lng = data.connected_post.lng;

          customerSearchHighlight = L.circleMarker([lat, lng], {
            radius: 20,
            fillColor: '#fbbf24',
            color: '#f59e0b',
            weight: 3,
            opacity: 0.8,
            fillOpacity: 0.6
          }).addTo(map);

          // Zoom to customer location
          map.setView([lat, lng], 17);

          // AUTO-TRIGGER ROUTE FINDING
          findRouteToCustomer(customerId).finally(function () {
            customerSearchSuggestions.classList.remove('active');
            searchClearBtn.classList.add('active'); // Show clear button
          });
        } else {
          // Customer found but no post linked
          customerSearchSuggestions.innerHTML = '<div class="customer-search-item customer-search-error" style="padding: 12px; text-align: center; color: #f59e0b;">⚠️ Customer found but no connected pole on map</div>';
          setTimeout(function () {
            customerSearchSuggestions.classList.remove('active');
            searchClearBtn.classList.add('active');
          }, 3000);
        }
      })
      .catch(function (err) {
        console.error('Error fetching customer location:', err);
        customerSearchSuggestions.innerHTML = '<div class="customer-search-item customer-search-error" style="padding: 12px; text-align: center; color: #dc2626;">⚠️ Error loading customer location</div>';
        setTimeout(function () { customerSearchSuggestions.classList.remove('active'); }, 2000);
      });
  }

  // ── 2. Route layer ──
  var routeLayer = L.layerGroup().addTo(map);
  var _routePolyline = null;
  var _routeMarkers = [];

  function clearRoute() {
    routeLayer.clearLayers();
    _routePolyline = null;
    _routeMarkers = [];
    document.getElementById('route-result').style.display = 'none';
  }

  // ── 3. Auto-trigger route finding when customer selected ──
  function findRouteToCustomer(custId) {
    return new Promise(function (resolve, reject) {
      if (!custId) {
        console.error('No customer ID provided');
        resolve();
        return;
      }

      if (!navigator.geolocation) {
        console.error('Geolocation is not supported by your browser.');
        resolve();
        return;
      }

      // Show specific geolocation status
      showRouteStatus('info', '⏳ Waiting for GPS permission...');

      navigator.geolocation.getCurrentPosition(
        function (pos) {
          showRouteStatus('info', '✅ GPS location acquired. Calculating route...');
          var lat = pos.coords.latitude;
          var lng = pos.coords.longitude;

          var url = '/api/path?customer_id=' + encodeURIComponent(custId)
            + '&user_lat=' + lat + '&user_lng=' + lng;

          fetch(url)
            .then(function (r) { return r.json(); })
            .then(function (data) {
              if (!data.found) {
                console.warn('No path found for customer ' + custId);
              } else {
                drawRoute(data, lat, lng);
              }
              resolve();
            })
            .catch(function (err) {
              console.error('Route finding error:', err);
              resolve();
            });
        },
        function (err) {
          console.error('Geolocation error:', err);
          resolve();
        },
        { enableHighAccuracy: true, timeout: 15000 }
      );
    });
  }

  // ── 4. Status helper ──
  function showRouteStatus(type, msg) {
    var el = document.getElementById('route-status');
    if (!el) return;
    el.style.display = 'block';
    el.className = 'route-status route-status--' + type;
    el.innerHTML = msg;
  }

  // ── 5. Draw the route on the map ──
  function drawRoute(data, userLat, userLng) {
    clearRoute();

    var path = data.path || [];
    if (path.length < 1) {
      showRouteStatus('error', 'Path returned no coordinates.');
      return;
    }

    var latlngs = path.map(function (n) { return [n.lat, n.lng]; });

    // Add user location as first point
    var userIcon = L.divIcon({
      className: '',
      html: '<div class="route-user-dot"></div>',
      iconSize: [16, 16],
      iconAnchor: [8, 8]
    });
    var userMarker = L.marker([userLat, userLng], { icon: userIcon })
      .bindPopup('<strong>📍 Your Location</strong>');
    routeLayer.addLayer(userMarker);
    _routeMarkers.push(userMarker);

    // Destination marker
    var destPost = data.destination_post;
    var destIcon = L.divIcon({
      className: '',
      html: '<div class="route-dest-flag">🏁</div>',
      iconSize: [28, 28],
      iconAnchor: [10, 24]
    });
    var destMarker = L.marker([destPost.lat, destPost.lng], { icon: destIcon })
      .bindPopup('<strong>🏁 ' + (destPost.name || 'Destination Post') + '</strong><br>Customer: <code>' + data.customer_id + '</code><br>' + (data.customer_name || ''));
    routeLayer.addLayer(destMarker);
    _routeMarkers.push(destMarker);

    // Animated polyline — user location + all path posts
    var fullLine = [[userLat, userLng]].concat(latlngs);
    var polyline = L.polyline(fullLine, {
      color: '#06b6d4',
      weight: 4,
      opacity: 0.9,
      dashArray: '10 8',
      lineJoin: 'round'
    }).addTo(routeLayer);
    _routePolyline = polyline;

    // Fit map to route
    var bounds = L.latLngBounds([[userLat, userLng]].concat(latlngs));
    map.fitBounds(bounds, { padding: [50, 50] });

    // Show result card
    renderRouteResult(data, path);
  }

  // ── 6. Result card ──
  function renderRouteResult(data, path) {
    var el = document.getElementById('route-result');
    el.classList.add('route-result-visible');
    el.style.display = 'block';

    var distKm = (data.total_distance_m / 1000).toFixed(2);
    var distText = data.total_distance_m < 1000
      ? Math.round(data.total_distance_m) + ' m'
      : distKm + ' km';

    // Format duration
    var durationText = '';
    if (data.duration_sec) {
      var mins = Math.floor(data.duration_sec / 60);
      var hrs = Math.floor(mins / 60);
      if (hrs > 0) {
        durationText = hrs + ' hr ' + (mins % 60) + ' min';
      } else {
        durationText = (mins || 1) + ' min';
      }
    }

    el.innerHTML =
      '<div class="route-summary">' +
      '<div class="route-summary-item"><span class="route-summary-num">' + durationText + '</span><span class="route-summary-label">Est. Time</span></div>' +
      '<div class="route-summary-sep">|</div>' +
      '<div class="route-summary-item"><span class="route-summary-num">' + distText + '</span><span class="route-summary-label">Road Distance</span></div>' +
      '</div>' +
      '<div class="route-customer-info">' +
      '<div style="font-size:0.75rem; color:var(--text-secondary); margin-bottom:2px;">Destination</div>' +
      '<strong>' + (data.customer_name || data.customer_id) + '</strong>' +
      '<div style="font-size:0.75rem;color:var(--text-secondary); margin-top:1px;">' + (data.destination_post.name || 'Post #' + data.destination_post.id) + '</div>' +
      '</div>' +
      '<button class="route-cancel-btn">✕ Cancel Route</button>';
  }

  /**
   * Clears an active feeder trace, restoring all map elements to default visibility.
   */
  function clearFeederTrace() {
    console.log('🧹 Clearing active feeder trace...');

    // Restore markers
    _allPostMarkers.forEach(m => {
      const el = m.getElement();
      if (el) {
        L.DomUtil.removeClass(el, 'active');
        el.style.opacity = '1';
        el.style.filter = 'none';
      }
    });

    // Restore Network Lines to their original styles
    if (typeof networkLinesLayer !== 'undefined') {
      networkLinesLayer.eachLayer(layer => {
        if (layer._defaultStyle) {
          layer.setStyle(layer._defaultStyle);
        }
      });
    }

    // Hide the Clear Trace button
    const clearBtn = document.getElementById('clear-trace-btn');
    if (clearBtn) clearBtn.style.display = 'none';
  }

  // Helper to inject the Clear Trace button
  function injectClearTraceButton() {
    const mapContainer = document.getElementById('map');
    if (mapContainer && !document.getElementById('clear-trace-btn')) {
      const btn = document.createElement('button');
      btn.id = 'clear-trace-btn';
      btn.className = 'btn btn-danger';
      btn.innerHTML = '✕ Clear Trace';
      btn.style.position = 'absolute';
      btn.style.bottom = '20px';
      btn.style.left = '50%';
      btn.style.transform = 'translateX(-50%)';
      btn.style.zIndex = '1000';
      btn.style.display = 'none';
      btn.style.boxShadow = '0 4px 6px rgba(0,0,0,0.3)';
      mapContainer.appendChild(btn);

      btn.addEventListener('click', clearFeederTrace);
    }
  }

  // Inject immediately if DOM is ready, otherwise wait for DOMContentLoaded
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', injectClearTraceButton);
  } else {
    injectClearTraceButton();
  }

  // Handle dinamically added Cancel Route button
  document.addEventListener('click', function (e) {
    if (e.target && e.target.classList.contains('route-cancel-btn')) {
      clearRoute();
      // Also clear search state
      customerSearchInput.value = '';
      searchClearBtn.classList.remove('active');
      if (customerSearchHighlight) {
        map.removeLayer(customerSearchHighlight);
        customerSearchHighlight = null;
      }
    }
  });

  /**
   * Highlights a set of buses found during a feeder trace.
   * Applies the 'active' class to markers, styles polylines, and dims unrelated elements.
   */
  function highlightFeederTrace(busIds) {
    if (!busIds || !Array.isArray(busIds)) return;

    console.log('🌟 Highlighting feeder trace:', busIds.length, 'nodes');
    const busSet = new Set(busIds);

    // Dim ALL markers first, and remove active class
    _allPostMarkers.forEach(m => {
      const el = m.getElement();
      if (el) {
        L.DomUtil.removeClass(el, 'active');
        el.style.opacity = '0.3';
        el.style.filter = 'grayscale(100%)';
      }
    });

    // Highlight only the traced markers
    let highlightedCount = 0;
    busIds.forEach(bid => {
      // Try various bus ID formats to find the post
      const post = busToPostMap[bid] || poleToPostMap[bid];
      if (post && postMarkers[post.id]) {
        const marker = postMarkers[post.id];
        const el = marker.getElement();
        if (el) {
          L.DomUtil.addClass(el, 'active');
          el.style.opacity = '1';
          el.style.filter = 'none';
          highlightedCount++;
        }
      }
    });

    // Handle Network Lines
    let highlightedLines = 0;
    if (typeof networkLinesLayer !== 'undefined') {
      networkLinesLayer.eachLayer(layer => {
        // We highlight the line if BOTH ends are in the trace (for full connectivity)
        // Or if one end is in the trace (e.g. for dangling service drops)
        if (layer._fromBus || layer._toBus) {
          const fromInTrace = busSet.has(layer._fromBus);
          const toInTrace = busSet.has(layer._toBus);

          if (fromInTrace || toInTrace) {
            layer.setStyle({ color: '#ffeb3b', weight: 5, opacity: 1, dashArray: null });
            if (layer.bringToFront) layer.bringToFront();
            highlightedLines++;
          } else {
            // Dim network lines not in trace
            layer.setStyle({ opacity: 0.15, weight: 1 });
            if (layer.bringToBack) layer.bringToBack();
          }
        }
      });
    }

    console.log(`✅ Successfully highlighted ${highlightedCount} markers and ${highlightedLines} lines on map.`);

    // Show the Clear Trace button
    const clearBtn = document.getElementById('clear-trace-btn');
    if (clearBtn) clearBtn.style.display = 'block';
  }

  /**
   * Updates the global grid analytics stats in the sidebar.
   */
  function updateGridAnalytics() {
    const el = document.getElementById('sidebar-grid-analytics');
    if (!el) return;

    const mlRisks = Object.values(window._mlRiskMap || {});
    const loadStresses = Object.values(window._loadStressMap || {});

    const criticalCount = mlRisks.filter(r => r.risk_level === 'Critical').length;
    const highRiskCount = mlRisks.filter(r => r.risk_level === 'High').length;
    const overloadedCount = loadStresses.filter(s => s.status === 'Overloaded').length;
    const highLoadCount = loadStresses.filter(s => s.status === 'High Load').length;

    let html = '';

    // ML Stats
    html += `<div style="margin-bottom:8px;">
                <div style="font-size:0.75rem; color:var(--text-secondary); margin-bottom:4px;">ML Predicted Risks:</div>
                <div style="display:flex; justify-content:space-between; font-size:0.8rem;">
                    <span style="color:var(--danger); font-weight:600;">Critical: ${criticalCount}</span>
                    <span style="color:var(--warning); font-weight:600;">High: ${highRiskCount}</span>
                </div>
             </div>`;

    // Load Stats
    html += `<div>
                <div style="font-size:0.75rem; color:var(--text-secondary); margin-bottom:4px;">Load Flow Stress:</div>
                <div style="display:flex; justify-content:space-between; font-size:0.8rem;">
                    <span style="color:var(--danger); font-weight:600;">Overloaded: ${overloadedCount}</span>
                    <span style="color:var(--warning); font-weight:600;">High Load: ${highLoadCount}</span>
                </div>
             </div>`;

    if (criticalCount + highRiskCount + overloadedCount + highLoadCount === 0) {
      html = '<div style="padding:10px; font-size:0.8rem; color:var(--text-muted); text-align:center;">Network 100% Healthy</div>';
    }

    el.innerHTML = html;
  }

  /**
   * Displays a detailed modal with Outage Simulation results.
   */
  function showOutageImpactModal(data, startBus) {
    let html = `
        <div class="outage-summary" style="margin-bottom:16px; padding:12px; background:var(--danger-light); border-radius:8px; border-left:4px solid var(--danger);">
            <div style="font-size:1.1rem; font-weight:700; color:var(--danger-dark);">Potential Outage Detected</div>
            <div style="font-size:0.9rem; color:var(--text-secondary);">Root Point: ${startBus}</div>
        </div>
        
        <div class="stats-row" style="display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-bottom:16px;">
            <div class="stat-card" style="padding:12px; flex-direction:column; align-items:flex-start; gap:4px;">
                <div class="stat-value" style="font-size:1.5rem;">${Number(data.total_customers).toLocaleString()}</div>
                <div class="stat-label">Affected Customers</div>
            </div>
            <div class="stat-card" style="padding:12px; flex-direction:column; align-items:flex-start; gap:4px;">
                <div class="stat-value" style="font-size:1.5rem;">${Number(data.total_load_kwh).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</div>
                <div class="stat-label">Est. Load Loss (kWh)</div>
            </div>
        </div>

        <div style="margin-bottom:8px;"><strong>Downstream Topology Data:</strong></div>
        <ul style="font-size:0.85rem; color:var(--text-secondary); margin-bottom:16px;">
            <li>Nodes in outage zone: ${Number(data.downstream_bus_count).toLocaleString()}</li>
            <li>Transformers offline: ${data.affected_transformer_ids.length}</li>
        </ul>

    `;

    if (data.customer_details && data.customer_details.length > 0) {
      html += `<div style="margin-bottom:8px;"><strong>Impacted Customers List:</strong></div>
                <div style="max-height:200px; overflow-y:auto; border:1px solid var(--border); border-radius:6px;">
                    <table style="width:100%; font-size:0.8rem; border-collapse:collapse;">
                        <thead style="background:var(--surface-secondary); position:sticky; top:0;">
                            <tr>
                                <th style="padding:4px 8px; text-align:left; border-bottom:1px solid var(--border);">Name</th>
                                <th style="padding:4px 8px; text-align:right; border-bottom:1px solid var(--border);">Load (kWh)</th>
                            </tr>
                        </thead>
                        <tbody>`;

      data.customer_details.sort((a, b) => b.load_kwh - a.load_kwh).forEach(c => {
        html += `<tr>
                        <td style="padding:4px 8px; border-bottom:1px solid var(--divider);">${c.name || c.customer_id}</td>
                        <td style="padding:4px 8px; border-bottom:1px solid var(--divider); text-align:right;">${c.load_kwh.toFixed(2)}</td>
                    </tr>`;
      });

      html += `</tbody></table></div>`;
    } else {
      html += `<div style="padding:12px; text-align:center; color:var(--text-muted); border:1px dashed var(--border); border-radius:6px;">
                    No customer impact detected for this point.
                </div>`;
    }

    showNoticeModal('Outage Impact Analysis', html);
  }

});
