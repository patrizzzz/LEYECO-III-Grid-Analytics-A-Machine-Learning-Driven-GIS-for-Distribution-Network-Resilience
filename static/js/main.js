document.addEventListener('DOMContentLoaded', function() {
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
    setTimeout(function() { try { window._mapInstance.invalidateSize(); } catch (e) {} }, 100);
    return;
  }

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

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '© OpenStreetMap contributors',
    }).addTo(map);

    try { map._container.style.borderRadius = '8px'; } catch (e) {}
    try { map._container.style.boxShadow = '0 4px 6px -1px rgba(0,0,0,0.1)'; } catch (e) {}
  } catch (err) {
    showMapError('Map could not start: ' + (err.message || err));
    return;
  }

  const postsLayer = L.layerGroup();
  const latlongLayer = L.layerGroup();
  const connectionsLayer = L.layerGroup();
  const networkLinesLayer = L.layerGroup();
  const postMarkers = {}; // map post_id -> marker
  const busToPostMap = {}; // map bus_id -> post data
  const poleToPostMap = {}; // map pole_number -> post data
  const bounds = L.latLngBounds();

  const overlays = {
    'Posts (canonical)': postsLayer,
    'LatLongData (raw)': latlongLayer,
    'Connections': connectionsLayer,
    'Network lines (DB)': networkLinesLayer
  };
  L.control.layers(null, overlays, { collapsed: false }).addTo(map);

  // Force Leaflet to measure container and load tiles (fixes blank map)
  function refreshMapSize() {
    try { map.invalidateSize(); } catch (e) {}
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
        connBtns.forEach(b => { try { b.disabled = true; } catch (e) {} });
      }
    }
  }).catch(() => {});

  // Custom electrical-post icon
  const poleIcon = L.icon({
    iconUrl: '/static/img/pole.svg',
    iconSize: [55, 70],
    iconAnchor: [28, 61],
    popupAnchor: [0, -68],
    tooltipAnchor: [0, -44],
    className: 'pole-icon'
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
    setTimeout(function() {
      loadPosts();
    }, 100);
    
    setTimeout(function() {
      loadLineConnections();
      loadNetworkGeometry();
    }, 1500);
  }

  // Make it globally accessible for resources page
  window.reloadMapData = reloadMapData;

  // Delete all data from backend (posts, connections, network lines, raw data) and reset IDs
  function deleteAllData() {
    if (!confirm('⚠️ DELETE ALL DATA?\n\nThis will permanently delete:\n- All posts/poles\n- All connections\n- All network lines\n- All raw coordinates\n\nIDs will reset to 1. This cannot be undone!\n\nType OK to confirm.')) {
      return Promise.resolve({ success: false, message: 'Cancelled by user' });
    }

    console.log('Starting deleteAllData request...');
    
    return fetch('/api/data/delete-all', { 
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    })
      .then(r => {
        console.log('Delete API response status:', r.status);
        if (!r.ok) {
          console.error('Delete API returned status:', r.status);
          return r.json().then(data => {
            throw new Error(`Server error (${r.status}): ${data.message || data.error || 'Unknown error'}`);
          });
        }
        return r.json();
      })
      .then(data => {
        console.log('Delete response:', data);
        if (data.result === 'success') {
          console.log('✓ Backend: All data deleted, IDs reset');
          console.log('Reset status:', data.id_reset_status);
          clearAllMapLayers();
          return { success: true, message: data.message };
        } else if (data.error) {
          console.error('❌ Delete failed:', data.message);
          return { success: false, message: data.message };
        } else {
          console.error('Unexpected response:', data);
          return { success: false, message: 'Unexpected response from server' };
        }
      })
      .catch(err => {
        console.error('❌ Delete API error:', err);
        return { success: false, message: err.message || 'API error: ' + String(err) };
      });
  }

  function formatMeters(m) {
    if (m >= 1000) return (m/1000).toFixed(2) + ' km';
    return Math.round(m) + ' m';
  }

  // Helper function to determine line color based on Circuit field
  function getLineColor(circuit) {
    if (!circuit) return '#999'; // Default gray for null/undefined
    const normalizedCircuit = String(circuit).trim().toLowerCase();
    if (normalizedCircuit === '3 phase') return '#228B22'; // Green
    if (normalizedCircuit === 'single phase') return '#d63031'; // Red
    if (normalizedCircuit === 'v phase') return '#0984e3'; // Blue
    return '#999'; // Default gray for unknown values
  }

  function haversine(lat1, lon1, lat2, lon2) {
    const R = 6371000; // meters
    const toRad = (deg) => deg * Math.PI / 180;
    const dLat = toRad(lat2 - lat1);
    const dLon = toRad(lon2 - lon1);
    const a = Math.sin(dLat/2) * Math.sin(dLat/2) + Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon/2) * Math.sin(dLon/2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
    return R * c;
  }

  // Helper to add markers to a layer
  function addPostMarker(layer, p) {
    const lat = parseFloat(p.lat);
    const lng = parseFloat(p.lng);
    if (Number.isNaN(lat) || Number.isNaN(lng)) return;

    const popupHtml = `
      <div class="popup-post-content">
        <div class="popup-post-details">
          <strong>${(p.name || 'Post ' + p.id).replace(/</g, '&lt;')}</strong><br>
          Status: ${(p.status || 'N/A').replace(/</g, '&lt;')}<br>
          Coordinates: ${lat.toFixed(6)}, ${lng.toFixed(6)}<br>
          ID: ${p.id}
        </div>
        <div class="popup-connect-actions">
          <button class="btn btn-outline primary-line-overhead-btn" data-post-id="${p.id}">Primary line-overhead</button>
          <button class="btn btn-outline distribution-transformer-btn" data-post-id="${p.id}">Distribution Transformer</button>
        </div>
        <div class="popup-connections-inner"></div>
      </div>
    `;

    const marker = L.marker([lat, lng], { title: p.name || `Post ${p.id}`, icon: poleIcon })
      .bindPopup(popupHtml);

    // Store post data on marker for later access (connections, etc.)
    marker._postData = p;

    // keep a reference for selection / bulk operations
    try { postMarkers[p.id] = marker; } catch (e) {}
    
    // Also store in lookup maps for connection drawing
    if (p.pole_number) {
      poleToPostMap[p.pole_number] = p;
      busToPostMap[p.pole_number] = p; // Primary bus is usually the pole number
    }
    if (p.feeder) {
      // Also create aliases for common bus naming patterns
      if (p.primary_bus_id) {
        busToPostMap[p.primary_bus_id] = p;
      }
    }

    // Bind tooltip but control open/close to avoid overlapping tooltips
    marker.bindTooltip(`ID: ${p.id}`, { permanent: false, direction: 'top' });
    marker.addTo(layer);

    // Ensure only one tooltip is visible at a time to prevent overlap
    marker.on('mouseover', function () {
      try {
        if (window._lastTooltipMarker && window._lastTooltipMarker !== marker) {
          window._lastTooltipMarker.closeTooltip();
        }
      } catch (e) {}
      try { marker.openTooltip(); } catch (e) {}
      window._lastTooltipMarker = marker;
    });

    // Small delay on mouseout to avoid flicker when moving between nearby markers
    marker.on('mouseout', function () {
      setTimeout(function () {
        try { marker.closeTooltip(); } catch (e) {}
        if (window._lastTooltipMarker === marker) window._lastTooltipMarker = null;
      }, 250);
    });
    bounds.extend([lat, lng]);

    // support connection mode: click marker to add to connection
    marker.on('click', function(e) {
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
    marker.on('popupopen', function() {
      const popupEl = marker.getPopup().getElement();
      if (!popupEl) return;

      // Primary line-overhead button: show modal with technical data
      const primaryLineBtn = popupEl.querySelector('.primary-line-overhead-btn');
      if (primaryLineBtn) {
        primaryLineBtn.onclick = function() {
          const postId = primaryLineBtn.getAttribute('data-post-id');
          if (!postId) return;
          fetch('/api/posts/' + postId)
            .then(function(r) { return r.json(); })
            .then(function(data) {
              if (data && data.error) return;
              showPrimaryLineOverheadModal(data);
            })
            .catch(function() {});
        };
      }

      // Distribution Transformer button: fetch transformer by bus_id
      const transformerBtn = popupEl.querySelector('.distribution-transformer-btn');
      if (transformerBtn) {
        transformerBtn.onclick = function() {
          const postId = transformerBtn.getAttribute('data-post-id');
          if (!postId) return;
          // First get post to find primary_bus_id
          fetch('/api/posts/' + postId)
            .then(function(r) { return r.json(); })
            .then(function(postData) {
              if (postData && postData.error) return;
              var busId = postData.primary_bus_id || postData.pole_number;
              if (!busId) {
                alert('No primary bus ID found for this post');
                return;
              }
              fetch('/api/transformers/by-bus/' + encodeURIComponent(busId))
                .then(function(r) { return r.json(); })
                .then(function(result) {
                  if (result && result.error) {
                    alert('Error: ' + result.error);
                    return;
                  }
                  if (!result.transformers || result.transformers.length === 0) {
                    alert('No transformer found for bus ID: ' + busId);
                    return;
                  }
                  // Show first transformer (or all if multiple)
                  showDistributionTransformerModal(result.transformers[0]);
                })
                .catch(function(err) {
                  alert('Failed to load transformer: ' + (err && err.message ? err.message : String(err)));
                });
            })
            .catch(function() {});
        };
      }

      // Load authoritative post details from the `post` table via API
      try {
        const detailsEl = popupEl.querySelector('.popup-post-details');
        fetch(`/api/posts/${p.id}`)
          .then(r => r.json())
          .then(data => {
            if (!data || data.error) return;
            const latText = (typeof data.lat === 'number') ? data.lat.toFixed(6) : (data.lat || '');
            const lngText = (typeof data.lng === 'number') ? data.lng.toFixed(6) : (data.lng || '');
            let infoHtml = `<strong>${(data.name || 'Post ' + data.id).replace(/</g, '&lt;')}</strong><br>`;
            infoHtml += `Pole Number: ${data.pole_number || '—'}<br>`;
            infoHtml += `Status: ${data.status || 'N/A'}<br>`;
            infoHtml += `Feeder: ${data.feeder || '—'}<br>`;
            infoHtml += `kVA Rating: ${data.kva_rating != null ? data.kva_rating : '—'}<br>`;
            infoHtml += `Meter: ${data.meter_brand ? (data.meter_brand + (data.meter_id ? ' / ' + data.meter_id : '')) : (data.meter_id || '—')}<br>`;
            infoHtml += `Coordinates: ${latText}, ${lngText}<br>`;
            if (detailsEl) detailsEl.innerHTML = infoHtml;
          }).catch(() => {});
      } catch (e) { console.error('Failed to fetch post details', e); }

      // Load connections that include this post — section is inside the popup (modal) content
      const connectionsContainer = popupEl.querySelector('.popup-connections-inner');
      if (!connectionsContainer) return;
      connectionsContainer.innerHTML = '';
      fetch(`/api/posts/${p.id}/connections`)
        .then(r => r.json())
        .then(function(conns) {
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
          conns.forEach(function(c) {
            const li = document.createElement('li');
            const name = (typeof c.name === 'string' && c.name && c.name.indexOf('{') !== 0) ? c.name : ('Connection #' + (c.id != null ? c.id : ''));
            const ids = (c.points || []).map(function(pt) { return pt.post_id ? '#' + pt.post_id : (pt.lat != null && pt.lng != null ? pt.lat.toFixed(6) + ',' + pt.lng.toFixed(6) : ''); }).join(', ');
            li.innerHTML = (name.replace(/</g, '&lt;')) + ' (id ' + (c.id != null ? c.id : '') + ') — ' + formatMeters(c.total_length || 0) + '<br/>IDs: ' + (ids || '—') + ' <button class="btn btn-danger disconnect-from-post" data-conn-id="' + (c.id != null ? c.id : '') + '">Disconnect</button>';
            list.appendChild(li);
          });
          section.appendChild(list);
          connectionsContainer.appendChild(section);

          // attach handlers scoped to the newly created section
          const btns = section.querySelectorAll('.disconnect-from-post');
          btns.forEach(b => {
            b.addEventListener('click', function(ev) {
              ev.preventDefault();
              const id = b.getAttribute('data-conn-id');
              showConfirmModal('Disconnect/delete this connection?', { title: 'Delete connection', okText: 'Delete', cancelText: 'Cancel' })
                .then(function(confirmed) {
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

  // Load canonical posts (filtered to PH)
  fetch('/api/posts?in_ph=1&per_page=1000')
    .then(r => {
      if (!r.ok) throw new Error(`API error: ${r.status}`);
      return r.json();
    })
    .then(response => {
      console.log('Posts API response:', response);
      
      // Handle both old array format and new paginated format
      const posts = Array.isArray(response) ? response : (response.data || []);
      console.log('Posts to render on map:', posts.length, posts);
      
      if (!posts || posts.length === 0) {
        console.warn('No posts found - map may appear empty');
      }
      
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
          setTimeout(function() {
            const marker = postMarkers[tid];
            if (marker && marker.getLatLng) {
              try { map.flyTo(marker.getLatLng(), 17); } catch (e) { map.setView(marker.getLatLng(), 17); }
              try { marker.openPopup(); } catch (e) {}
            } else {
              console.warn('Target marker not found:', tid);
            }
          }, 250);
        }
      } catch (e) { console.error('Error in target post handling:', e); }
    })
    .catch(err => console.error('Failed to load posts:', err));

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
            return;
          }

          // Determine line color based on Circuit field
          let lineColor = getLineColor(conn.circuit);
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

          // Add popup
          const popupText = `
            <strong>${connType.replace(/_/g, ' → ')}</strong><br>
            From Bus: ${fromBus}<br>
            To Bus: ${toBus}<br>
            Feeder: ${conn.feeder || 'N/A'}<br>
            Circuit: ${conn.circuit || 'N/A'}
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

  // Load network line geometry from DB (coordinates from DB only; no client-side resolution)
  function loadNetworkGeometry() {
    fetch('/api/network-geometry')
      .then(function(r) { return r.ok ? r.json() : Promise.reject(new Error(r.statusText)); })
      .then(function(data) {
        networkLinesLayer.clearLayers();
        var lines = data.lines || [];
        var stats = data.stats || {};
        lines.forEach(function(line) {
          var lat1 = parseFloat(line.lat1);
          var lng1 = parseFloat(line.lng1);
          var lat2 = parseFloat(line.lat2);
          var lng2 = parseFloat(line.lng2);
          if (Number.isNaN(lat1) || Number.isNaN(lng1) || Number.isNaN(lat2) || Number.isNaN(lng2)) return;
          var connType = line.connection_type || '';
          var color = getLineColor(line.circuit);
          var weight = 2;
          var dash = null;
          if (connType.indexOf('Primary_to_Primary') !== -1) { weight = 3; }
          else if (connType.indexOf('Primary_to_Transformer') !== -1) { weight = 2.5; }
          else if (connType.indexOf('Transformer_to_Secondary') !== -1) { weight = 2; }
          var poly = L.polyline([[lat1, lng1], [lat2, lng2]], { color: color, weight: weight, opacity: 0.8, dashArray: dash });
          var lenStr = (line.length_meters != null && !Number.isNaN(line.length_meters))
            ? '<br>Length: ' + Number(line.length_meters).toFixed(2) + ' m'
            : '';
          var popup = '<strong>' + (connType.replace(/_/g, ' \u2192 ')) + '</strong><br>From: ' + (line.from_bus || '') + ' \u2192 To: ' + (line.to_bus || '') + '<br>Feeder: ' + (line.feeder || '') + ' | Circuit: ' + (line.circuit || '') + lenStr;
          poly.bindPopup(popup);
          poly.addTo(networkLinesLayer);
        });
        networkLinesLayer.addTo(map);
        var totalM = stats.total_length_meters != null ? stats.total_length_meters : 0;
        console.log('Network geometry: ' + lines.length + ' lines (nodes: ' + (stats.nodes || 0) + ', total length: ' + (typeof totalM === 'number' ? totalM.toFixed(2) : totalM) + ' m)');
      })
      .catch(function(err) { console.warn('Network geometry load failed:', err); });
  }


  // Load connections after posts are loaded
  setTimeout(function() {
    console.log('Calling loadLineConnections after posts...');
    loadLineConnections();
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
      total += haversine(connectionPoints[i-1].lat, connectionPoints[i-1].lng, connectionPoints[i].lat, connectionPoints[i].lng);
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
          <dl class="result-modal-details"></dl>
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
      if (count > 1) {
        detailsEl.innerHTML = `<dt>Segments saved</dt><dd>${count} post-to-post</dd><dt>Total length</dt><dd>${formatMeters(length)}</dd>`;
      } else if (count === 0 && options.id != null) {
        detailsEl.innerHTML = `<dt>Post ID</dt><dd>${options.id}</dd>`;
      } else {
        detailsEl.innerHTML = `<dt>Connection ID</dt><dd>${options.id != null ? options.id : '—'}</dd><dt>Length</dt><dd>${formatMeters(length)}</dd>`;
      }
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
      '<div class="modal result-modal" style="max-width: 480px; width: 90vw;">',
      '  <div class="modal-header result-modal-header">',
      '    <h3 class="result-modal-title">Primary line-overhead</h3>',
      '    <button class="modal-close primary-line-overhead-close" aria-label="Close">✕</button>',
      '  </div>',
      '  <div class="modal-body result-modal-body primary-line-overhead-body" style="max-height: 60vh; overflow-y: auto; padding: 12px 16px;">',
      '    <dl class="result-modal-details primary-line-overhead-dl"></dl>',
      '  </div>',
      '  <div class="modal-footer"><button class="btn result-modal-ok primary-line-overhead-ok">OK</button></div>',
      '</div>'
    ].join('');
    document.body.appendChild(overlay);
    overlay.querySelector('.primary-line-overhead-close').addEventListener('click', closePrimaryLineOverheadModal);
    overlay.querySelector('.primary-line-overhead-ok').addEventListener('click', closePrimaryLineOverheadModal);
    overlay.addEventListener('click', function(e) { if (e.target === overlay) closePrimaryLineOverheadModal(); });
    overlay.addEventListener('keydown', function(e) { if (e.key === 'Escape') closePrimaryLineOverheadModal(); });
    _primaryLineOverheadModal = overlay;
    return _primaryLineOverheadModal;
  }
  function showPrimaryLineOverheadModal(data) {
    var m = createPrimaryLineOverheadModal();
    var dl = m.querySelector('.primary-line-overhead-dl');
    var title = m.querySelector('.result-modal-title');
    title.textContent = 'Primary line-overhead' + (data && data.name ? ' — ' + data.name : '');
    dl.innerHTML = '';
    PRIMARY_LINE_OVERHEAD_FIELDS.forEach(function(f) {
      var val = data && data[f.key];
      if (val === undefined || val === null || val === '') val = '—';
      else if (typeof val === 'number') val = Number(val);
      var dt = document.createElement('dt');
      dt.textContent = f.label;
      var dd = document.createElement('dd');
      dd.textContent = val;
      dl.appendChild(dt);
      dl.appendChild(dd);
    });
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
      '<div class="modal result-modal" style="max-width: 500px; width: 90vw;">',
      '  <div class="modal-header result-modal-header">',
      '    <h3 class="result-modal-title">Distribution Transformer</h3>',
      '    <button class="modal-close distribution-transformer-close" aria-label="Close">✕</button>',
      '  </div>',
      '  <div class="modal-body result-modal-body distribution-transformer-body" style="max-height: 60vh; overflow-y: auto; padding: 12px 16px;">',
      '    <dl class="result-modal-details distribution-transformer-dl"></dl>',
      '  </div>',
      '  <div class="modal-footer"><button class="btn result-modal-ok distribution-transformer-ok">OK</button></div>',
      '</div>'
    ].join('');
    document.body.appendChild(overlay);
    overlay.querySelector('.distribution-transformer-close').addEventListener('click', closeDistributionTransformerModal);
    overlay.querySelector('.distribution-transformer-ok').addEventListener('click', closeDistributionTransformerModal);
    overlay.addEventListener('click', function(e) { if (e.target === overlay) closeDistributionTransformerModal(); });
    overlay.addEventListener('keydown', function(e) { if (e.key === 'Escape') closeDistributionTransformerModal(); });
    _distributionTransformerModal = overlay;
    return _distributionTransformerModal;
  }
  function showDistributionTransformerModal(data) {
    var m = createDistributionTransformerModal();
    var dl = m.querySelector('.distribution-transformer-dl');
    var title = m.querySelector('.result-modal-title');
    title.textContent = 'Distribution Transformer' + (data && data.transformer_id ? ' — ' + data.transformer_id : '');
    dl.innerHTML = '';
    DISTRIBUTION_TRANSFORMER_FIELDS.forEach(function(f) {
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
      var dt = document.createElement('dt');
      dt.textContent = f.label;
      var dd = document.createElement('dd');
      dd.textContent = val;
      dl.appendChild(dt);
      dl.appendChild(dd);
    });
    m.style.display = 'flex';
    m.tabIndex = -1;
    m.focus();
  }
  function closeDistributionTransformerModal() {
    if (_distributionTransformerModal) _distributionTransformerModal.style.display = 'none';
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
    m.querySelector('.notice-message').textContent = message || '';
    m.style.display = 'flex';
    m.tabIndex = -1;
    m.focus();
  }

  // Save a connection from the current points
  function saveConnection(nameArg) {
    if (connectionPoints.length < 2) { alert('Add at least two points to save a connection.'); return; }
    let name = nameArg;
    if (!name) name = prompt('Name this connection', `Connection ${new Date().toISOString().slice(0,19)}`) || 'Connection';
    hideConnectionHint();
    // Send a plain array of { post_id, lat, lng } so backend never receives a dict or non-numeric values
    var pointsPayload = connectionPoints.map(function(pt) {
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
          buffer.on('click', function() { poly.openPopup(); highlightPoly(poly); });
          poly.on('click', function() { poly.openPopup(); highlightPoly(poly); });

          // Add non-interactive endpoint markers for each point to ensure visual match
          c.points.forEach(pt => {
            L.circleMarker([pt.lat, pt.lng], { radius: 5, color: '#0066ff', fillColor: '#fff', weight: 2, interactive: false }).addTo(endpointsLayer);
          });

          // Attach handler when popup opens
          poly.on('popupopen', function() {
            const el = poly.getPopup().getElement();
            if (!el) return;
            const btn = el.querySelector('.disconnect-conn');
            if (!btn) return;
            btn.addEventListener('click', function(ev) {
              ev.preventDefault();
              const id = btn.getAttribute('data-conn-id');
              showConfirmModal('Disconnect and delete this connection?', { title: 'Delete connection', okText: 'Delete', cancelText: 'Cancel' })
                .then(function(confirmed) {
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
      try { marker.setOpacity(0.6); } catch (e) {}
    } else {
      selectedOrder.splice(idx, 1);
      try { marker.setOpacity(1); } catch (e) {}
    }
    updateSelectionBadge();
  }

  function clearSelection() {
    selectedOrder.slice().forEach(id => {
      const m = postMarkers[id]; if (m) try { m.setOpacity(1); } catch (e) {}
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
    if (selectedOrder.length < 2) { alert('Select at least two posts to connect.'); return; }
    const points = selectedOrder.map(id => {
      const m = postMarkers[id];
      if (!m) return null;
      const latlng = m.getLatLng();
      return { post_id: id, lat: latlng.lat, lng: latlng.lng };
    }).filter(Boolean);
    if (points.length < 2) { alert('Selected posts do not have valid coordinates.'); return; }
    const name = 'Bulk connect';
    fetch('/api/connections', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name: name, points: points }) })
      .then(r => r.json()).then(j => {
        if (j && j.created) {
          showResultModal({ name: name, length: j.created.reduce((s,c)=>s+(c.total_length||0),0), count: j.count || j.created.length });
          clearSelection();
          loadConnections();
        } else if (j && j.error) {
          showResultModal({ error: true, message: j.error });
        }
      }).catch(err => showResultModal({ error: true, message: 'Save failed: ' + err }));
  }

});
