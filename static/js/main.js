document.addEventListener('DOMContentLoaded', function() {
  // Default map centered on Philippines
  const map = L.map('map').setView([12.8797, 121.7740], 6);

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '© OpenStreetMap contributors',
  }).addTo(map);

  // Rotation wrapper to allow visual rotation (tiles & overlays) without rotating controls
  const mapContainer = document.getElementById('map');
  const mapPane = map.getPane('mapPane');
  const rotateWrap = document.createElement('div');
  rotateWrap.className = 'rotate-wrapper';
  mapContainer.insertBefore(rotateWrap, mapPane);
  rotateWrap.appendChild(mapPane);
  let rotation = 0;
  function setMapRotation(deg) {
    rotation = ((deg % 360) + 360) % 360;
    rotateWrap.style.transform = `rotate(${rotation}deg)`;
  }
  function rotateBy(delta) { setMapRotation(rotation + delta); }

  // Rotate control: left/right/reset and slider
  const RotateControl = L.Control.extend({
    options: { position: 'topleft' },
    onAdd: function() {
      const container = L.DomUtil.create('div', 'leaflet-bar rotate-control');
      container.innerHTML = `
        <button id="rot-left" title="Rotate left 15°">◀</button>
        <input id="rot-range" type="range" min="0" max="360" step="1" value="0" style="width:80px; vertical-align:middle;">
        <button id="rot-right" title="Rotate right 15°">▶</button>
        <button id="rot-reset" title="Reset rotation">↺</button>
      `;
      L.DomEvent.disableClickPropagation(container);
      setTimeout(() => {
        const left = container.querySelector('#rot-left');
        const right = container.querySelector('#rot-right');
        const reset = container.querySelector('#rot-reset');
        const range = container.querySelector('#rot-range');
        left.addEventListener('click', () => { rotateBy(-15); range.value = rotation; });
        right.addEventListener('click', () => { rotateBy(15); range.value = rotation; });
        reset.addEventListener('click', () => { setMapRotation(0); range.value = rotation; });
        range.addEventListener('input', (e) => setMapRotation(parseInt(e.target.value, 10)));
      }, 0);
      return container;
    }
  });
  map.addControl(new RotateControl());

  const postsLayer = L.layerGroup();
  const latlongLayer = L.layerGroup();
  const bounds = L.latLngBounds();

  const overlays = {
    'Posts (canonical)': postsLayer,
    'LatLongData (raw)': latlongLayer
  };
  L.control.layers(null, overlays, { collapsed: false }).addTo(map);

  // Helper to add markers to a layer
  function addPostMarker(layer, p) {
    const lat = parseFloat(p.lat);
    const lng = parseFloat(p.lng);
    if (Number.isNaN(lat) || Number.isNaN(lng)) return;
    const marker = L.marker([lat, lng], { title: p.name || `Post ${p.id}` })
      .bindPopup(`<strong>${p.name || 'Post ' + p.id}</strong><br>Status: ${p.status || 'N/A'}<br>Coordinates: ${lat.toFixed(6)}, ${lng.toFixed(6)}<br>ID: ${p.id}`);
    marker.bindTooltip(`ID: ${p.id}`, { permanent: false, direction: 'top' });
    marker.addTo(layer);
    bounds.extend([lat, lng]);
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
  fetch('/api/posts?in_ph=1')
    .then(r => r.json())
    .then(posts => {
      posts.forEach(p => addPostMarker(postsLayer, p));
      // Add postsLayer to map by default
      postsLayer.addTo(map);
      // Fit map if we added markers
      if (!bounds.isEmpty()) {
        map.fitBounds(bounds.pad(0.12));
      }
    })
    .catch(err => console.error('Failed to load posts', err));

  // Load raw latlongdata layer
  fetch('/api/latlongdata')
    .then(r => r.json())
    .then(rows => {
      if (!rows || rows.length === 0) return;
      rows.forEach(r => addLatLongMarker(latlongLayer, r));
      // Do not add latlongLayer by default; user can toggle it on via control
    })
    .catch(err => console.error('Failed to load latlongdata', err));

});
