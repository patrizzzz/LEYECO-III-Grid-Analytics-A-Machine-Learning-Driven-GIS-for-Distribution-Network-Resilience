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

  // Global helper for opening posts from outside (e.g. search)
  function openPostInInspector(p) {
    const inspectorContent = document.getElementById('inspector-content');
    const layoutEl = document.querySelector('.premium-layout');
    if (!inspectorContent || !layoutEl) return;

    const lat = parseFloat(p.lat);
    const lng = parseFloat(p.lng);

    const popupHtml = `
      <div class="post-popup-container">
        <div class="post-popup-tabs">
            <button class="tab-link active" data-tab="General-${p.id}">General</button>
            <button class="tab-link" data-tab="Connections-${p.id}">Connections</button>
            <button class="tab-link" data-tab="Assets-${p.id}">Assets</button>
        </div>

        <div id="General-${p.id}" class="tab-content" style="display: block;">
            <div class="popup-post-details">
              <strong>${(p.name || 'Post ' + p.id).replace(/</g, '&lt;')}</strong><br>
              <div style="padding:10px;text-align:center;"><div class="spinner"></div> Loading details...</div>
            </div>
            <div class="popup-connect-actions" style="margin-bottom:4px;">
                <button class="btn btn-outline btn-street-view" data-lat="${lat}" data-lng="${lng}" data-post-id="${p.id}" title="Open Street View at this location">
                  <svg xmlns="http://www.w3.org/2000/svg" height="16" width="16" viewBox="0 -960 960 960" fill="currentColor" style="vertical-align:middle;margin-right:4px;"><path d="M480-80q-83 0-156-31.5T197-197q-54-54-85.5-127T80-480q0-83 31.5-156T197-763q54-54 127-85.5T480-880q83 0 156 31.5T763-763q54 54 85.5 127T880-480q0 83-31.5 156T763-197q-54 54-127 85.5T480-80Zm-40-82v-78q-33 0-56.5-23.5T360-320v-40L168-552q-3 18-5.5 36t-2.5 36q0 121 79.5 212T440-162Zm276-102q27-35 43.5-76t22.5-86H640v40q0 33 23.5 56.5T720-306v42Z"/></svg>
                  Street View
                </button>
            </div>
             <div class="popup-connect-actions">
                <button class="btn btn-outline primary-line-overhead-btn" data-post-id="${p.id}" data-bus-id="${p.primary_bus_id || p.transformer_bus_id || p.pole_number || ''}">Primary line-overhead</button>
                <button class="btn btn-outline distribution-transformer-btn" data-post-id="${p.id}">Distribution Transformer</button>
            </div>
        </div>

        <div id="Connections-${p.id}" class="tab-content" style="display: none;">
             <div class="popup-connect-actions">
                <button class="btn btn-outline secondary-lines-btn" data-post-id="${p.id}">Secondary Lines</button>
                <button class="btn btn-outline service-drop-btn" data-post-id="${p.id}">Secondary Service Drop</button>
                <button class="btn btn-outline full-width-btn btn-show-connections" data-post-id="${p.id}">View Connected Lines</button>
            </div>
            <div class="popup-connect-actions" style="margin-top:4px;">
                <button class="btn btn-outline btn-trace-downstream" data-post-id="${p.id}" data-pole="${p.pole_number || ''}" data-bus="${p.primary_bus_id || ''}" data-transformer-bus="${p.transformer_bus_id || ''}">⚡ Trace Downstream</button>
                <button class="btn btn-outline btn-outage-sim" data-post-id="${p.id}" data-pole="${p.pole_number || ''}" data-bus="${p.primary_bus_id || ''}" data-transformer-bus="${p.transformer_bus_id || ''}">🔴 Outage Simulation</button>
            </div>
            <div class="popup-connections-inner" style="margin-top:10px; font-size:0.85rem;"></div>
        </div>

        <div id="Assets-${p.id}" class="tab-content" style="display: none;">
            <div class="popup-connect-actions grid-actions">
              <button class="btn btn-outline voltage-regulator-btn" data-post-id="${p.id}">Voltage Regulator</button>
              <button class="btn btn-outline shunt-capacitor-btn" data-post-id="${p.id}">Shunt Capacitor</button>
              <button class="btn btn-outline shunt-inductor-btn" data-post-id="${p.id}">Shunt Inductor</button>
              <button class="btn btn-outline series-inductor-btn" data-post-id="${p.id}">Series Inductor</button>
            </div>
            <div style="margin-top: 12px; border-top: 1px solid var(--border); padding-top:12px;">
                <button class="btn btn-outline full-width-btn export-post-btn" data-post-id="${p.id}">📥 Export Post Data</button>
            </div>
        </div>
      </div>
    `;

    layoutEl.classList.add('inspector-open');

    // Manage active marker state
    if (window._selectionIndicatorMarker) {
      map.removeLayer(window._selectionIndicatorMarker);
    }
    window._selectionIndicatorMarker = L.marker([lat, lng], {
      icon: L.divIcon({
        className: 'custom-selection-indicator',
        html: '<div class="selection-tooltip">Selected</div>',
        iconSize: [80, 30],
        iconAnchor: [40, 85]
      }),
      interactive: false,
      zIndexOffset: 1000
    }).addTo(map);

    inspectorContent.innerHTML = `
      <div class="inspector-view-layer">
        <div class="inspector-header">
          <h3 style="margin:0; font-size:1.1rem; color:var(--text-primary);">Asset Inspector</h3>
          <button id="close-inspector-inner" class="btn-icon" style="background:var(--surface-secondary);border-radius:50%;">✕</button>
        </div>
        <div class="inspector-body">
          ${popupHtml}
        </div>
      </div>
    `;

    document.getElementById('close-inspector-inner').onclick = () => {
      layoutEl.classList.remove('inspector-open');
      if (window._selectionIndicatorMarker) {
        map.removeLayer(window._selectionIndicatorMarker);
        window._selectionIndicatorMarker = null;
      }
    };

    // Attach tab listeners
    const tabLinks = inspectorContent.querySelectorAll('.tab-link');
    const tabContents = inspectorContent.querySelectorAll('.tab-content');
    tabLinks.forEach(link => {
      link.addEventListener('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        tabContents.forEach(c => c.style.display = 'none');
        tabLinks.forEach(l => l.classList.remove('active'));
        const targetId = this.getAttribute('data-tab');
        const target = inspectorContent.querySelector('#' + targetId);
        if (target) target.style.display = 'block';
        this.classList.add('active');
      });
    });

    // ── Load authoritative details (Load Stress, technical data) ──
    const detailsEl = inspectorContent.querySelector('.popup-post-details');
    fetch(`/api/posts/${p.id}`)
      .then(r => r.json())
      .then(data => {
        if (!data || data.error) return;
        
        // Patch NETWORK attributes
        const trBtn = inspectorContent.querySelector('.btn-trace-downstream');
        const outBtn = inspectorContent.querySelector('.btn-outage-sim');
        if (trBtn) {
            trBtn.setAttribute('data-pole', data.pole_number || '');
            trBtn.setAttribute('data-bus', data.primary_bus_id || '');
            trBtn.setAttribute('data-transformer-bus', data.transformer_bus_id || '');
        }
        if (outBtn) {
            outBtn.setAttribute('data-pole', data.pole_number || '');
            outBtn.setAttribute('data-bus', data.primary_bus_id || '');
            outBtn.setAttribute('data-transformer-bus', data.transformer_bus_id || '');
        }

        const busId = data.primary_bus_id || data.pole_number;
        let vrPromise = (busId) ? fetch('/api/voltage-regulators/by-bus/' + encodeURIComponent(busId)).then(r => r.json()).catch(() => null) : Promise.resolve(null);

        vrPromise.then(vrRes => {
          const vrData = (vrRes && vrRes.items && vrRes.items.length > 0) ? vrRes.items[0] : null;
          let kvaDisplay = '—';
          if (vrData && vrData.kva_rating != null) kvaDisplay = vrData.kva_rating;
          else if (data.kva_rating != null) kvaDisplay = data.kva_rating;

          let infoHtml = `<strong>${(data.name || 'Post ' + data.id).replace(/</g, '&lt;')}</strong><br>`;
          infoHtml += `ID: ${data.id}<br>`;
          infoHtml += `Post Code: ${data.post_id || data.pole_number || '—'}<br>`;
          infoHtml += `Status: ${data.status || 'N/A'}<br>`;
          infoHtml += `Feeder: ${data.feeder || '—'}<br>`;
          infoHtml += `kVA Rating: ${kvaDisplay}<br>`;
          infoHtml += `Meter: ${data.meter_brand ? (data.meter_brand + (data.meter_id ? ' / ' + data.meter_id : '')) : (data.meter_id || '—')}<br>`;
          infoHtml += `Coordinates: ${lat.toFixed(6)}, ${lng.toFixed(6)}<br>`;

          if (data.utilization_percent !== undefined) {
              const util = data.utilization_percent;
              const status = data.load_status || 'Unknown';
              const statusClass = status.toLowerCase().replace(' ', '-');
              let barColorClass = 'normal';
              if (util >= 100) barColorClass = 'danger';
              else if (util >= 80) barColorClass = 'warning';

              infoHtml += `
                <div class="stress-section" style="margin-top:10px; padding:10px; background:var(--surface-secondary); border-radius:8px;">
                  <div class="stress-header" style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                    <span style="font-size:0.75rem; font-weight:700; color:var(--text-secondary);">LOAD STRESS</span>
                    <span class="status-badge ${statusClass}" style="padding:2px 6px; border-radius:4px; font-size:0.7rem; font-weight:700;">${status}</span>
                  </div>
                  <div class="utilization-track" style="height:6px; background:var(--border); border-radius:3px; overflow:hidden;">
                    <div class="utilization-fill ${barColorClass}" style="width: ${Math.min(util, 100)}%; height:100%;"></div>
                  </div>
                  <div class="stress-metrics" style="display:flex; justify-content:space-between; margin-top:6px; font-size:0.7rem; color:var(--text-secondary);">
                    <span>Utilization: ${util.toFixed(1)}%</span>
                    <span>Risk: ${data.ml_risk_level || 'Low'}</span>
                  </div>
                </div>
              `;
          }
          if (detailsEl) detailsEl.innerHTML = infoHtml;
        });
      });

    // ── Load connections section ──
    const connsContainer = inspectorContent.querySelector('.popup-connections-inner');
    fetch(`/api/posts/${p.id}/connections`)
      .then(r => r.json())
      .then(conns => {
        const list = Array.isArray(conns) ? conns : (conns && conns.connections ? conns.connections : []);
        if (list.length === 0) return;

        let html = '<strong>Connections involving this post:</strong>';
        html += '<ul class="post-connections-list" style="margin-top:8px; padding-left:1.2rem;">';
        list.forEach(c => {
            const name = (typeof c.name === 'string' && c.name && c.name.indexOf('{') !== 0) ? c.name : ('Connection #' + (c.id || ''));
            html += `<li style="margin-bottom:8px;">${name.replace(/</g, '&lt;')} (id ${c.id}) — ${formatMeters(c.total_length || 0)} <br/><button class="btn btn-danger disconnect-from-post" data-conn-id="${c.id}" style="padding:2px 8px; font-size:0.7rem; margin-top:4px;">Disconnect</button></li>`;
        });
        html += '</ul>';
        connsContainer.innerHTML = html;
        
        connsContainer.querySelectorAll('.disconnect-from-post').forEach(b => {
          b.onclick = () => {
            const id = b.dataset.connId;
            showConfirmModal('Permanently delete this connection?', { title: 'Delete Connection', okText: 'Delete' }).then(conf => {
              if (conf) {
                fetch('/api/connections/' + id, { method: 'DELETE' }).then(r => r.json()).then(j => {
                  if (j.result === 'deleted') {
                    b.closest('li').remove();
                    loadConnections();
                  } else {
                    showNoticeModal('Error', 'Failed to delete connection');
                  }
                });
              }
            });
          };
        });
      });

    bindInspectorButtons(inspectorContent);
  }

  function bindInspectorButtons(container) {
      // 1. Street View
      const svBtn = container.querySelector('.btn-street-view');
      if (svBtn) svBtn.onclick = (e) => {
          window.open(`https://www.google.com/maps/@${svBtn.dataset.lat},${svBtn.dataset.lng},3a,80y,0h,90t/data=!3m4!1e1!3m2!1s!2e0`, '_blank');
      };

      // 2. Primary Line Info
      const plBtn = container.querySelector('.primary-line-overhead-btn');
      if (plBtn) plBtn.onclick = () => {
          const id = plBtn.dataset.busId || plBtn.dataset.postId;
          fetch('/api/primary-lines/by-bus/' + encodeURIComponent(id))
            .then(r => r.json())
            .then(res => {
               if (res.primary_lines && res.primary_lines.length > 0) showPrimaryLineOverheadModal(res.primary_lines[0]);
               else fetch('/api/posts/' + plBtn.dataset.postId).then(r => r.json()).then(d => showPrimaryLineOverheadModal(d));
            });
      };

      // 3. Distribution Transformer
      const txBtn = container.querySelector('.distribution-transformer-btn');
      if (txBtn) txBtn.onclick = () => {
          fetch('/api/posts/' + txBtn.dataset.postId).then(r => r.json()).then(p => {
              const bus = p.transformer_bus_id || p.primary_bus_id || p.pole_number;
              fetch('/api/transformers/by-bus/' + encodeURIComponent(bus)).then(r => r.json()).then(t => {
                  if (t.transformers && t.transformers.length > 0) showDistributionTransformerModal(t.transformers[0]);
                  else showDistributionTransformerModal({ transformer_bus_id: bus });
              });
          });
      };

      // 4. Secondary Lines
      const slBtn = container.querySelector('.secondary-lines-btn');
      if (slBtn) slBtn.onclick = () => {
          fetch('/api/posts/' + slBtn.dataset.postId).then(r => r.json()).then(p => {
              const bus = p.transformer_bus_id || p.primary_bus_id || p.pole_number;
              fetch('/api/transformers/by-bus/' + encodeURIComponent(bus)).then(r => r.json()).then(trRes => {
                  if (trRes.transformers && trRes.transformers.length > 0) {
                      const secBus = trRes.transformers[0].to_secondary_bus_id;
                      if (!secBus) { showNoticeModal('Info', 'Transformer has no secondary bus defined.'); return; }
                      fetch('/api/secondary-lines/by-bus/' + encodeURIComponent(secBus)).then(r => r.json()).then(res => showSecondaryLineModal(res));
                  } else {
                      showNoticeModal('Info', 'No transformer found to resolve secondary lines.');
                  }
              });
          });
      };

      // 5. Service Drops
      const sdBtn = container.querySelector('.service-drop-btn');
      if (sdBtn) sdBtn.onclick = () => {
          sdBtn.textContent = '⏳ Loading...';
          fetch(`/api/posts/${sdBtn.dataset.postId}/service-drops`).then(r => r.json()).then(res => {
              sdBtn.textContent = '🏠 Service Drops';
              showServiceDropModal(res);
          });
      };

      // 6. Connected Lines Visualization
      const connBtn = container.querySelector('.btn-show-connections');
      if (connBtn) connBtn.onclick = () => {
          connBtn.textContent = '⏳ Loading...';
          fetch(`/api/posts/${connBtn.dataset.postId}/connections`).then(r => r.json()).then(res => {
              connBtn.textContent = 'View Connected Lines';
              showConnectionsModal(res, connBtn.dataset.postId);
          });
      };

      // 7. Network Analysis (Trace)
      const trBtn = container.querySelector('.btn-trace-downstream');
      if (trBtn) trBtn.onclick = () => {
          const busId = trBtn.dataset.pole || trBtn.dataset.bus || trBtn.dataset.transformerBus;
          if (!busId) { showNoticeModal('Info', 'No bus ID available'); return; }
          trBtn.textContent = '⏳ Tracing...';
          fetch('/api/network/trace-feeder?start_bus=' + encodeURIComponent(busId) + '&direction=downstream')
            .then(r => r.json())
            .then(result => {
                trBtn.textContent = '⚡ Trace Downstream';
                if (result.error) { showNoticeModal('Error', result.error); return; }
                
                const buses = result.visited_buses || [];
                let html = '<div class="trace-summary-header" style="display:flex; align-items:center; gap:12px; margin-bottom:16px;">';
                html += '<div style="width:40px; height:40px; border-radius:10px; background:#e0f2fe; color:#0ea5e9; display:flex; align-items:center; justify-content:center; font-size:20px;">⚡</div>';
                html += '<div><div style="font-weight:700; font-size:16px;">Trace Downstream</div><div style="font-size:12px; color:#64748b;">Starting Node: ' + busId + '</div></div></div>';
                
                html += '<div style="padding:16px; background:var(--surface-secondary); border-radius:8px; border:1px solid var(--border); margin-bottom:16px;">';
                html += '<div style="font-size:11px; color:#64748b; text-transform:uppercase; letter-spacing:0.5px; margin-bottom:4px;">Total Downstream Nodes</div>';
                html += '<div style="font-size:24px; font-weight:700; color:#0ea5e9;">' + buses.length + '</div>';
                html += '</div>';

                if (buses.length > 0) {
                    html += '<div style="font-weight:600; font-size:13px; margin-bottom:8px;">Buses in Trace</div>';
                    html += '<div style="max-height:180px; overflow-y:auto; font-size:12px; background:var(--surface-secondary); padding:10px; border-radius:8px; font-family:var(--font-mono); line-height:1.6;">';
                    buses.forEach(function (b, idx) { 
                        html += '<span style="color:#64748b;">' + (idx+1).toString().padStart(2, '0') + '. </span>' + b + '<br>'; 
                    });
                    html += '</div>';
                }
                
                showNoticeModal('Trace Result', html);
                visualizeNetworkAnalysis('trace', result, busId);
            })
            .catch(err => {
                trBtn.textContent = '⚡ Trace Downstream';
                showNoticeModal('Error', 'Trace failed: ' + (err.message || err));
            });
      };

      // 8. Network Analysis (Outage)
      const outBtn = container.querySelector('.btn-outage-sim');
      if (outBtn) outBtn.onclick = () => {
          const busId = outBtn.dataset.pole || outBtn.dataset.bus || outBtn.dataset.transformerBus;
          if (!busId) { showNoticeModal('Info', 'No bus ID available'); return; }
          outBtn.textContent = '⏳ Simulating...';
          fetch('/api/network/simulate-outage?start_bus=' + encodeURIComponent(busId))
            .then(r => r.json())
            .then(result => {
                outBtn.textContent = '🔴 Outage Simulation';
                if (result.error) { showNoticeModal('Error', result.error); return; }
                
                let html = '<div class="outage-summary-header" style="display:flex; align-items:center; gap:12px; margin-bottom:16px;">';
                html += '<div style="width:40px; height:40px; border-radius:10px; background:#fee2e2; color:#ef4444; display:flex; align-items:center; justify-content:center; font-size:20px;">⚠️</div>';
                html += '<div><div style="font-weight:700; font-size:16px;">Outage Impact Analysis</div><div style="font-size:12px; color:#64748b;">Source: ' + busId + '</div></div></div>';
                
                html += '<div style="display:grid; grid-template-columns: 1fr 1fr; gap:10px; margin-bottom:16px;">';
                html += '<div style="padding:12px; background:var(--surface-secondary); border-radius:8px; border:1px solid var(--border);"><div style="font-size:11px; color:#64748b; text-transform:uppercase; letter-spacing:0.5px; margin-bottom:4px;">Affected Customers</div><div style="font-size:20px; font-weight:700; color:#ef4444;">' + (result.total_customers || 0) + '</div></div>';
                html += '<div style="padding:12px; background:var(--surface-secondary); border-radius:8px; border:1px solid var(--border);"><div style="font-size:11px; color:#64748b; text-transform:uppercase; letter-spacing:0.5px; margin-bottom:4px;">Total Load Loss</div><div style="font-size:20px; font-weight:700; color:#ef4444;">' + (result.total_load_kwh || 0) + ' <span style="font-size:12px; font-weight:500;">kWh</span></div></div>';
                html += '<div style="padding:12px; background:var(--surface-secondary); border-radius:8px; border:1px solid var(--border);"><div style="font-size:11px; color:#64748b; text-transform:uppercase; letter-spacing:0.5px; margin-bottom:4px;">Transformers</div><div style="font-size:20px; font-weight:700; color:var(--text-primary);">' + (result.affected_transformer_ids ? result.affected_transformer_ids.length : 0) + '</div></div>';
                html += '<div style="padding:12px; background:var(--surface-secondary); border-radius:8px; border:1px solid var(--border);"><div style="font-size:11px; color:#64748b; text-transform:uppercase; letter-spacing:0.5px; margin-bottom:4px;">Downstream Nodes</div><div style="font-size:20px; font-weight:700; color:var(--text-primary);">' + (result.downstream_bus_count || 0) + '</div></div>';
                html += '</div>';

                const transIds = result.affected_transformer_ids || [];
                if (transIds.length > 0) {
                    html += '<div style="font-size:11px; padding:8px 12px; background:var(--surface-secondary); border-radius:6px; margin-bottom:16px; border:1px solid var(--border);"><strong>Transformers:</strong> ' + transIds.join(', ') + '</div>';
                }

                // Customer details
                const customers = result.customer_details || [];
                if (customers.length > 0) {
                    html += '<div style="font-weight:600; font-size:13px; margin-bottom:8px;">Affected Customers List</div>';
                    html += '<div class="table-scroll" style="max-height:220px; overflow-y:auto; border:1px solid var(--border); border-radius:8px; scrollbar-gutter: stable;">';
                    html += '<table style="width:100%; border-collapse:collapse; font-size:11px; table-layout: fixed;">';
                    html += '<thead style="background:var(--surface-secondary); position:sticky; top:0; z-index:10;"><tr style="border-bottom:1px solid var(--border);">';
                    html += '<th style="padding:10px 8px; text-align:left; color:#64748b; width: 55%;">Customer</th>';
                    html += '<th style="padding:10px 8px; text-align:left; color:#64748b; width: 22%;">Type</th>';
                    html += '<th style="padding:10px 12px; text-align:right; color:#64748b; width: 23%;">kWh</th></tr></thead><tbody>';
                    customers.forEach(function (c) {
                        const kwhFormatted = (c.load_kwh || 0).toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 });
                        html += '<tr style="border-bottom:1px solid var(--border); transition: background 0.2s;"><td style="padding:10px 8px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">';
                        html += '<div><strong title="' + (c.name || 'N/A') + '">' + (c.name || 'N/A') + '</strong></div><div style="font-size:9px; color:#94a3b8;">' + (c.customer_id || '') + '</div></td>';
                        html += '<td style="padding:10px 8px;"><span style="display:inline-block; padding:2px 6px; background:#e0f2fe; color:#0369a1; border-radius:4px; font-size:9px; font-weight:700;">' + (c.type || 'RES') + '</span></td>';
                        html += '<td style="padding:10px 12px; text-align:right; font-weight:600; color: var(--text-primary);">' + kwhFormatted + '</td></tr>';
                    });
                    html += '</tbody></table></div>';
                }
                
                showNoticeModal('Outage Impact Analysis', html);
                visualizeNetworkAnalysis('outage', result, busId);
            })
            .catch(err => {
                outBtn.textContent = '🔴 Outage Simulation';
                showNoticeModal('Error', 'Simulation failed: ' + (err.message || err));
            });
      };

      // 9. Asset Modals
      const bindAsset = (selector, apiPath, modalFn, label) => {
          const btn = container.querySelector(selector);
          if (btn) btn.onclick = () => {
              fetch('/api/posts/' + btn.dataset.postId).then(r => r.json()).then(p => {
                  const bus = p.transformer_bus_id || p.primary_bus_id || p.pole_number;
                  fetch(`${apiPath}${encodeURIComponent(bus)}`).then(r => r.json()).then(res => {
                      if (res.count > 0) modalFn(res);
                      else showNoticeModal('Info', `No ${label} found for bus: ${bus}`);
                  });
              });
          };
      };
      bindAsset('.voltage-regulator-btn', '/api/voltage-regulators/by-bus/', showVoltageRegulatorModal, 'Voltage Regulator');
      bindAsset('.shunt-capacitor-btn', '/api/shunt-capacitors/by-bus/', showShuntCapacitorModal, 'Shunt Capacitor');
      bindAsset('.shunt-inductor-btn', '/api/shunt-inductors/by-bus/', showShuntInductorModal, 'Shunt Inductor');
      bindAsset('.series-inductor-btn', '/api/series-inductors/by-bus/', showSeriesInductorModal, 'Series Inductor');

      // 10. Export
      const expBtn = container.querySelector('.export-post-btn');
      if (expBtn) expBtn.onclick = () => {
          window.location = '/api/export/post/' + expBtn.dataset.postId;
      };
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

  const mainCanvas = L.canvas();
  const postsLayer = L.markerClusterGroup({
    disableClusteringAtZoom: 16,
    spiderfyOnMaxZoom: true,
    maxClusterRadius: 40,
    showCoverageOnHover: false
  });
  const latlongLayer = L.layerGroup();
  const connectionsLayer = L.layerGroup();
  const primaryLinesLayer = L.layerGroup().addTo(map);
  const secondaryLinesLayer = L.layerGroup();
  const networkLinesLayer = L.layerGroup().addTo(map);
  const municipalityLayer = L.geoJSON(null, {
    style: function(feature) {
      const muniName = feature.properties.NAME_2 || feature.properties.name || 'Unknown';
      return {
        fillColor: getMunicipalityColor(muniName),
        fillOpacity: 0.4,
        color: '#fff',
        weight: 1,
        interactive: true
      };
    },
    onEachFeature: function(feature, layer) {
      const muniName = feature.properties.NAME_2 || feature.properties.name || 'Unknown';
      const brgyName = feature.properties.NAME_3 || '';
      
      // Store names on the layer for easy access in zoom-dependent labeling
      layer._muniName = muniName;
      layer._brgyName = brgyName;
      
      const displayName = brgyName ? brgyName + ', ' + muniName : muniName;
      
      if (displayName) {
        layer.bindPopup('<strong>' + displayName + '</strong>');
      }
    }
  });

  // Layer group for centered municipality labels (zoomed out)
  const muniLabelsLayer = L.layerGroup().addTo(map);

  function calculateMunicipalityCenters() {
    muniLabelsLayer.clearLayers();
    const muniBounds = {};

    municipalityLayer.eachLayer(function(layer) {
      const name = layer._muniName;
      if (!name) return;
      
      if (!muniBounds[name]) {
        muniBounds[name] = layer.getBounds();
      } else {
        muniBounds[name].extend(layer.getBounds());
      }
    });

    for (const name in muniBounds) {
      const center = muniBounds[name].getCenter();
      
      // Create a small invisible marker at the center to hold the tooltip
      const labelMarker = L.circleMarker(center, {
        radius: 0,
        opacity: 0,
        fillOpacity: 0,
        interactive: false
      });
      
      labelMarker.bindTooltip(name, {
        permanent: true,
        direction: 'center',
        className: 'municipality-label center-label',
        opacity: 1.0
      });
      
      muniLabelsLayer.addLayer(labelMarker);
    }
  }

  function updateMunicipalityLabels() {
    const zoom = map.getZoom();
    const threshold = 13;

    if (zoom < threshold) {
      // Zoomed Out: Show centered municipality labels
      if (!map.hasLayer(muniLabelsLayer)) map.addLayer(muniLabelsLayer);
      
      // Hide all individual barangay tooltips
      municipalityLayer.eachLayer(function(layer) {
        layer.unbindTooltip();
      });
    } else {
      // Zoomed In: Show ALL Barangay names, hide centered muni labels
      if (map.hasLayer(muniLabelsLayer)) map.removeLayer(muniLabelsLayer);

      municipalityLayer.eachLayer(function(layer) {
        const brgyName = layer._brgyName;
        layer.unbindTooltip();
        if (brgyName) {
          layer.bindTooltip(brgyName, {
            permanent: true,
            direction: 'center',
            className: 'municipality-label brgy-label',
            opacity: 0.8
          });
        }
      });
    }
  }

  // Ensure labels update whenever data is added or map is zoomed
  municipalityLayer.on('add', () => {
    calculateMunicipalityCenters();
    updateMunicipalityLabels();
  });

  // Ensure municipalityLayer is physically at the bottom of the map's panes if needed,
  // or just add it first.
  municipalityLayer.addTo(map);
  // Re-add other layers in order to keep Z-index correct
  primaryLinesLayer.addTo(map);
  secondaryLinesLayer.addTo(map);
  postsLayer.addTo(map);

  // Maps and Bounds - Must be defined here
  const postMarkers = {}; // map post_id -> marker
  const busToPostMap = {}; // map bus_id -> post data
  const poleToPostMap = {}; // map pole_number -> post data
  const bounds = L.latLngBounds();
  
  // --- Analysis Highlighting State ---
  let analysisHighlightLayers = L.featureGroup().addTo(map);
  const clearAnalysisBtn = document.createElement('button');
  clearAnalysisBtn.className = 'analysis-clear-btn';
  clearAnalysisBtn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6L6 18M6 6l12 12"/></svg> Clear Analysis';
  document.body.appendChild(clearAnalysisBtn);

  clearAnalysisBtn.onclick = function() {
    clearAnalysisHighlights();
  };

  function clearAnalysisHighlights() {
    analysisHighlightLayers.clearLayers();
    clearAnalysisBtn.style.display = 'none';
    
    // Reset any pulsing markers
    _allPostMarkers.forEach(m => {
        if (m.getElement()) {
            m.getElement().classList.remove('analysis-source-node');
        }
    });

    // Reset network lines if we modified them directly (though we'll use copies in the highlight layer)
  }

  const baseLayers = {
    'Standard': osmLayer,
    'Satellite': satelliteLayer,
    'Terrain': terrainLayer
  };

  const overlays = {
    'Municipalities': municipalityLayer,
    'Posts (canonical)': postsLayer,
    'LatLongData (raw)': latlongLayer,
    'Primary Lines': primaryLinesLayer,
    'Secondary Lines': secondaryLinesLayer,
    'Network Lines (DB)': networkLinesLayer
  };

  // Track whether each line layer overlay is enabled by the user (Layers section checkboxes)
  let primaryLayerOverlayOn = true;
  let secondaryLayerOverlayOn = true;

  // --- Global Line Color State ---
  let globalLineColor = localStorage.getItem('globalLineColor') || null;
  let usePhasingColor = localStorage.getItem('usePhasingColor') === 'true' || false;

  // --- Global Line Weight State (separate per line type) ---
  let primaryLineWeight = parseInt(localStorage.getItem('primaryLineWeight')) || 3;
  let secondaryLineWeight = parseInt(localStorage.getItem('secondaryLineWeight')) || 2;

  // Helper function to get weight per connection type
  function getLineWeight(connType) {
    if (!connType) return primaryLineWeight;
    const type = String(connType).toLowerCase();
    if (type.includes('secondary')) {
      return secondaryLineWeight;
    }
    // primary, transformer, distribution_line, default => use primaryLineWeight
    return primaryLineWeight;
  }

  // --- Feeder filter state ---
  let knownFeeders = new Set();
  let activeFeeders = new Set(); // feeders currently visible – starts with all enabled
  try {
    const savedFeedersRaw = localStorage.getItem('mapActiveFeeders');
    if (savedFeedersRaw) {
      const savedFeeders = JSON.parse(savedFeedersRaw);
      if (Array.isArray(savedFeeders)) {
        savedFeeders.forEach(function (f) {
          if (typeof f === 'string' && f) activeFeeders.add(f);
        });
      }
    }
  } catch (e) { /* ignore */ }

  // --- Phase filter state ---
  // Categories: '1' (Single Phase), '2' (Double Phase), '3' (Three Phase)
  let activePhaseCategories = new Set(['1', '2', '3']);
  try {
    const savedPhasesRaw = localStorage.getItem('mapActivePhases');
    if (savedPhasesRaw) {
      const savedPhases = JSON.parse(savedPhasesRaw);
      if (Array.isArray(savedPhases) && savedPhases.length > 0) {
        activePhaseCategories = new Set(savedPhases.filter(function (p) { return p === '1' || p === '2' || p === '3'; }));
      }
    }
  } catch (e) { /* ignore */ }

  const _allPostMarkers = []; // keeps references to ALL markers even when removed from layer
  let showPoles = true;
  let showTransformers = true;
  let showPrimaryLines = true;
  let showSecondaryLines = true;

  function persistActiveFeeders() {
    try {
      const arr = Array.from(activeFeeders);
      localStorage.setItem('mapActiveFeeders', JSON.stringify(arr));
    } catch (e) { /* ignore */ }
  }

  function applyMapFilters() {
    // Show all when: no feeders known, or all feeders are checked
    const showAllFeeds = knownFeeders.size === 0 || activeFeeders.size === knownFeeders.size;
    
    // Filter posts: remove/add from postsLayer
    _allPostMarkers.forEach(function (marker) {
      if (!marker._postData) return;
      const p = marker._postData;
      const f = p.feeder || '';
      const isFeederMatch = showAllFeeds || activeFeeders.has(f);
      
      const isTrans = p.has_transformer === true || (p.kva_rating != null && p.kva_rating > 0);
      let isTypeMatch = false;
      if (isTrans && showTransformers) isTypeMatch = true;
      if (!isTrans && showPoles) isTypeMatch = true;

      const shouldShow = isFeederMatch && isTypeMatch;

      if (shouldShow) {
        if (!postsLayer.hasLayer(marker)) postsLayer.addLayer(marker);
        // Swap icons based on toggle state
        if (isTrans) {
          marker.setIcon(showPoles ? transformerPoleIcon : transformerOnlyIcon);
        } else {
          marker.setIcon(poleIcon);
        }
      } else {
        if (postsLayer.hasLayer(marker)) postsLayer.removeLayer(marker);
      }
    });

    // Persist feeder selection whenever filter is applied
    persistActiveFeeders();

    // Filter network lines and connections: remove/add from their respective layers
    if (!window._hiddenNetworkLines) window._hiddenNetworkLines = [];
    if (!window._hiddenConnections) window._hiddenConnections = [];

    // Helper to filter a layer group
    function filterLineLayer(layerGroup, hiddenArray) {
      const currentLayers = [];
      layerGroup.eachLayer(function (layer) { currentLayers.push(layer); });
      
      const allLines = currentLayers.concat(hiddenArray);
      const newHidden = [];

      allLines.forEach(function (layer) {
        if (layer instanceof L.Polyline && !(layer.options && layer.options.className === 'click-buffer')) {
          // Feeder Check
          const f = layer._feederName || '';
          const isFeederVisible = showAllFeeds || activeFeeders.has(f);

          // Primary/Secondary Line Check
          let isTypeVisible = true;
          const cType = (layer._connType || '').toLowerCase();
          const isPrimary = cType.includes('primary') || cType.includes('distribution_line');
          const isSecondary = cType.includes('secondary');
          
          if (isPrimary && !showPrimaryLines) isTypeVisible = false;
          if (isSecondary && !showSecondaryLines) isTypeVisible = false;

          // Phase Check
          let isPhaseVisible = true;
          // Check if all phases are active (size 3), otherwise filter
          if (activePhaseCategories.size < 3) {
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

          if (isFeederVisible && isPhaseVisible && isTypeVisible) {
            if (!layerGroup.hasLayer(layer)) {
              layerGroup.addLayer(layer);
              // If there's a click-buffer associated, we might need a better way to track it,
              // but for now, we'll focus on the visible lines.
            }
          } else {
            if (layerGroup.hasLayer(layer)) layerGroup.removeLayer(layer);
            newHidden.push(layer);
          }
        }
      });
      return newHidden;
    }

    window._hiddenNetworkLines = filterLineLayer(networkLinesLayer, window._hiddenNetworkLines);
    window._hiddenConnections = filterLineLayer(connectionsLayer, window._hiddenConnections);
  }

  // Simple debounce helper for expensive filter operations
  function debounce(fn, delay) {
    let timer = null;
    return function () {
      const ctx = this;
      const args = arguments;
      if (timer) clearTimeout(timer);
      timer = setTimeout(function () { fn.apply(ctx, args); }, delay);
    };
  }

  let applyMapFiltersDebounced = null;

  // Expose function so it can be called after data loads
  window._refreshFeederList = function () { };

  // --- Unified Map Settings Control ---
  const mapSettingsControl = L.control({ position: 'topright' });
  mapSettingsControl.onAdd = function () {
    const container = L.DomUtil.create('div', 'leaflet-bar leaflet-control map-settings-panel');
    L.DomEvent.disableClickPropagation(container);
    L.DomEvent.disableScrollPropagation(container);

    // State for collapse
    let collapsed = false;

    // --- Header ---
    const header = document.createElement('div');
    header.className = 'msp-header';
    header.innerHTML = `
      <svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/>
        <circle cx="12" cy="12" r="3"/>
      </svg>
      <span style="font-size: 1.05rem;">Map Settings</span>
      <button class="msp-toggle" title="Collapse">▾</button>
    `;

    const body = document.createElement('div');
    body.className = 'msp-body';
    body.style.maxHeight = '400px';
    body.style.overflowY = 'auto';

    header.querySelector('.msp-toggle').addEventListener('click', function () {
      collapsed = !collapsed;
      body.style.display = collapsed ? 'none' : '';
      this.textContent = collapsed ? '▸' : '▾';
      container.classList.toggle('msp-collapsed', collapsed);
    });

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
        if (this.checked) {
          overlays[name].addTo(map);
          if (name === 'Primary Lines') primaryLayerOverlayOn = true;
          if (name === 'Secondary Lines') secondaryLayerOverlayOn = true;
        } else {
          map.removeLayer(overlays[name]);
          if (name === 'Primary Lines') primaryLayerOverlayOn = false;
          if (name === 'Secondary Lines') secondaryLayerOverlayOn = false;
        }
      });
      const span = document.createElement('span');
      span.textContent = name;
      row.appendChild(cb);
      row.appendChild(span);
      layerList.appendChild(row);
    });

    // window._applyPoleTransformerFilter = applyMapFilters;

    const separatorDiv = document.createElement('div');
    separatorDiv.style.borderTop = '1px solid rgba(0,0,0,0.08)';
    separatorDiv.style.margin = '6px 0 4px';
    separatorDiv.style.paddingTop = '4px';
    layerList.appendChild(separatorDiv);

    // Show Poles toggle
    const poleRow = document.createElement('label');
    poleRow.className = 'msp-option';
    const poleCb = document.createElement('input');
    poleCb.type = 'checkbox';
    poleCb.checked = true;
    poleCb.addEventListener('change', function () {
      showPoles = this.checked;
      applyMapFilters();
    });
    const poleSpan = document.createElement('span');
    poleSpan.textContent = 'Show Poles';
    poleRow.appendChild(poleCb);
    poleRow.appendChild(poleSpan);
    layerList.appendChild(poleRow);

    // Show Transformers toggle
    const transRow = document.createElement('label');
    transRow.className = 'msp-option';
    const transCb = document.createElement('input');
    transCb.type = 'checkbox';
    transCb.checked = true;
    transCb.addEventListener('change', function () {
      showTransformers = this.checked;
      applyMapFilters();
    });
    const transSpan = document.createElement('span');
    transSpan.textContent = 'Show Transformers';
    transRow.appendChild(transCb);
    transRow.appendChild(transSpan);
    layerList.appendChild(transRow);

    // Show Primary Lines toggle
    const priLineRow = document.createElement('label');
    priLineRow.className = 'msp-option';
    const priLineCb = document.createElement('input');
    priLineCb.type = 'checkbox';
    priLineCb.checked = true;
    priLineCb.addEventListener('change', function () {
      showPrimaryLines = this.checked;
      applyMapFilters();
    });
    const priLineSpan = document.createElement('span');
    priLineSpan.textContent = 'Show Primary Lines';
    priLineRow.appendChild(priLineCb);
    priLineRow.appendChild(priLineSpan);
    layerList.appendChild(priLineRow);

    // Show Secondary Lines toggle
    const secLineRow = document.createElement('label');
    secLineRow.className = 'msp-option';
    const secLineCb = document.createElement('input');
    secLineCb.type = 'checkbox';
    secLineCb.checked = true;
    secLineCb.addEventListener('change', function () {
      showSecondaryLines = this.checked;
      applyMapFilters();
    });
    const secLineSpan = document.createElement('span');
    secLineSpan.textContent = 'Show Secondary Lines';
    secLineRow.appendChild(secLineCb);
    secLineRow.appendChild(secLineSpan);
    layerList.appendChild(secLineRow);

    layerSection.appendChild(layerList);

    // === Section 3: Feeder Filter ===
    const feederSection = document.createElement('div');
    feederSection.className = 'msp-section';
    feederSection.innerHTML = '<div class="msp-section-title">Feeder Filter</div>';
    const feederList = document.createElement('div');
    feederList.className = 'msp-option-list msp-feeder-list';
    feederList.innerHTML = '<span class="msp-hint">Loading feeders…</span>';
    feederSection.appendChild(feederList);

    // Refresh feeder list after post data is loaded
    window._refreshFeederList = function () {
      feederList.innerHTML = '<span class="msp-hint">Loading feeders…</span>';

      // Build debounced filter on first use
      if (!applyMapFiltersDebounced) {
        applyMapFiltersDebounced = debounce(applyMapFilters, 120);
      }

      if (knownFeeders.size === 0) {
        feederList.innerHTML = '<span class="msp-hint">No feeders found</span>';
        return;
      }

      // If no saved state, ensure all currently known feeders are active
      const savedFeedersRaw = localStorage.getItem('mapActiveFeeders');
      if (!savedFeedersRaw) {
        knownFeeders.forEach(f => activeFeeders.add(f));
      }

      feederList.innerHTML = '';
      // "Show All" option
      const allRow = document.createElement('label');
      allRow.className = 'msp-option msp-feeder-all';
      const allCb = document.createElement('input');
      allCb.type = 'checkbox';
      // "Show All" is checked only if every feeder is active
      allCb.checked = activeFeeders.size === 0 || activeFeeders.size === knownFeeders.size;
      const allSpan = document.createElement('span');
      allSpan.textContent = 'Show All';
      allSpan.style.fontWeight = '600';
      allRow.appendChild(allCb);
      allRow.appendChild(allSpan);
      feederList.appendChild(allRow);

      const feederCbs = [];
      const sortedFeeders = Array.from(knownFeeders).sort();
      sortedFeeders.forEach(function (fname) {
        const hasSaved = savedFeedersRaw !== null;
        const row = document.createElement('label');
        row.className = 'msp-option';
        const cb = document.createElement('input');
        cb.type = 'checkbox';
        const shouldBeChecked = !hasSaved || activeFeeders.has(fname);
        cb.checked = shouldBeChecked;
        cb.dataset.feeder = fname;
        cb.addEventListener('change', function () {
          if (this.checked) { activeFeeders.add(fname); }
          else { activeFeeders.delete(fname); }
          // Sync "Show All"
          allCb.checked = activeFeeders.size === knownFeeders.size;
          if (applyMapFiltersDebounced) applyMapFiltersDebounced();
          else applyMapFilters();
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
        if (applyMapFiltersDebounced) applyMapFiltersDebounced();
        else applyMapFilters();
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
      { id: '3', label: 'Three Phase' }
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
        try {
          localStorage.setItem('mapActivePhases', JSON.stringify(Array.from(activePhaseCategories)));
        } catch (e) { /* ignore */ }
        if (applyMapFiltersDebounced) applyMapFiltersDebounced();
        else applyMapFilters(); // Re-run filter logic
      });
      const span = document.createElement('span');
      span.textContent = p.label;
      row.appendChild(cb);
      row.appendChild(span);
      phaseList.appendChild(row);
    });
    phaseSection.appendChild(phaseList);

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

    // Stroke weight slider — Primary Lines
    const priWeightRow = document.createElement('div');
    priWeightRow.className = 'msp-color-row';
    priWeightRow.style.marginTop = '8px';

    const priWeightLabel = document.createElement('span');
    priWeightLabel.textContent = 'Primary Thickness';
    priWeightLabel.className = 'msp-color-label';

    const priWeightContainer = document.createElement('div');
    priWeightContainer.style.display = 'flex';
    priWeightContainer.style.alignItems = 'center';
    priWeightContainer.style.flex = '1';
    priWeightContainer.style.gap = '8px';

    const priWeightInput = document.createElement('input');
    priWeightInput.type = 'range';
    priWeightInput.min = '1';
    priWeightInput.max = '10';
    priWeightInput.step = '1';
    priWeightInput.value = primaryLineWeight;
    priWeightInput.style.flex = '1';
    priWeightInput.style.cursor = 'pointer';

    const priWeightDisplay = document.createElement('span');
    priWeightDisplay.textContent = primaryLineWeight;
    priWeightDisplay.style.minWidth = '20px';
    priWeightDisplay.style.textAlign = 'right';
    priWeightDisplay.style.fontSize = '12px';
    priWeightDisplay.style.fontWeight = '500';

    priWeightContainer.appendChild(priWeightInput);
    priWeightContainer.appendChild(priWeightDisplay);
    priWeightRow.appendChild(priWeightLabel);
    priWeightRow.appendChild(priWeightContainer);

    // Stroke weight slider — Secondary Lines
    const secWeightRow = document.createElement('div');
    secWeightRow.className = 'msp-color-row';
    secWeightRow.style.marginTop = '6px';

    const secWeightLabel = document.createElement('span');
    secWeightLabel.textContent = 'Secondary Thickness';
    secWeightLabel.className = 'msp-color-label';

    const secWeightContainer = document.createElement('div');
    secWeightContainer.style.display = 'flex';
    secWeightContainer.style.alignItems = 'center';
    secWeightContainer.style.flex = '1';
    secWeightContainer.style.gap = '8px';

    const secWeightInput = document.createElement('input');
    secWeightInput.type = 'range';
    secWeightInput.min = '1';
    secWeightInput.max = '10';
    secWeightInput.step = '1';
    secWeightInput.value = secondaryLineWeight;
    secWeightInput.style.flex = '1';
    secWeightInput.style.cursor = 'pointer';

    const secWeightDisplay = document.createElement('span');
    secWeightDisplay.textContent = secondaryLineWeight;
    secWeightDisplay.style.minWidth = '20px';
    secWeightDisplay.style.textAlign = 'right';
    secWeightDisplay.style.fontSize = '12px';
    secWeightDisplay.style.fontWeight = '500';

    secWeightContainer.appendChild(secWeightInput);
    secWeightContainer.appendChild(secWeightDisplay);
    secWeightRow.appendChild(secWeightLabel);
    secWeightRow.appendChild(secWeightContainer);

    // Phasing toggle row
    const phasingRow = document.createElement('label');
    phasingRow.className = 'msp-option';
    phasingRow.style.marginTop = '8px';

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
    vizSection.appendChild(priWeightRow);
    vizSection.appendChild(secWeightRow);
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

    priWeightInput.addEventListener('input', function (e) {
      primaryLineWeight = parseInt(e.target.value);
      priWeightDisplay.textContent = primaryLineWeight;
      localStorage.setItem('primaryLineWeight', primaryLineWeight);
      updateNetworkLineWeights();
    });

    secWeightInput.addEventListener('input', function (e) {
      secondaryLineWeight = parseInt(e.target.value);
      secWeightDisplay.textContent = secondaryLineWeight;
      localStorage.setItem('secondaryLineWeight', secondaryLineWeight);
      updateNetworkLineWeights();
    });

    phasingCb.addEventListener('change', function () {
      usePhasingColor = this.checked;
      localStorage.setItem('usePhasingColor', usePhasingColor);
      updateNetworkLineColors();
    });

    // Assemble
    body.appendChild(baseSection);
    body.appendChild(layerSection);
    body.appendChild(feederSection);
    body.appendChild(phaseSection);
    body.appendChild(vizSection);
    container.appendChild(header);
    container.appendChild(body);

    return container;
  };

  const sidebarContainer = document.getElementById('sidebar-map-settings');
  if (sidebarContainer) {
    // Manually trigger onAdd to generate the settings UI
    const controlUI = mapSettingsControl.onAdd(map);
    // Ensure it's NOT added to the map's control layer
    // And append the body to our sidebar container
    const body = controlUI.querySelector('.msp-body');
    if (body) {
      body.style.display = 'block';
      body.style.maxHeight = 'none'; // Let sidebar handle scroll
      sidebarContainer.appendChild(body);
    }
  }

  // Handle Sidebar Toggle for Map Settings
  const mspToggle = document.getElementById('sidebar-map-settings-toggle');
  const mspWrapper = document.getElementById('sidebar-map-settings-wrapper');
  if (mspToggle && mspWrapper) {
    mspToggle.addEventListener('click', function(e) {
      e.preventDefault();
      // Check computed style or explicit style
      const currentDisplay = window.getComputedStyle(mspWrapper).display;
      const isHidden = currentDisplay === 'none';
      
      mspWrapper.style.display = isHidden ? 'block' : 'none';
      
      // Rotate arrow
      const arrow = mspToggle.querySelector('.sidebar-msp-arrow');
      if (arrow) arrow.textContent = isHidden ? '▾' : '▸';
      
      // Highlight link
      mspToggle.style.borderLeftColor = isHidden ? 'var(--primary)' : 'transparent';
      mspToggle.style.background = isHidden ? 'var(--primary-light)' : 'transparent';
    });
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
    iconSize: [55, 70],
    iconAnchor: [28, 61],
    popupAnchor: [0, -68],
    tooltipAnchor: [0, -44],
    className: 'pole-icon transformer-pole-icon'
  });

  // Standalone transformer icon (no pole) - used when "Show Poles" is off
  const transformerOnlyIcon = L.icon({
    iconUrl: '/static/img/transformer.svg',
    iconSize: [55, 70],
    iconAnchor: [28, 61],
    popupAnchor: [0, -68],
    tooltipAnchor: [0, -44],
    className: 'pole-icon transformer-only-icon'
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
    if (typeof networkLinesLayer !== 'undefined') networkLinesLayer.clearLayers();
    primaryLinesLayer.clearLayers();
    secondaryLinesLayer.clearLayers();
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
      loadLineConnections();
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

  // --- Municipality Boundary Logic ---
  const municipalityColors = {
    // Default palette - consistent per name
    'Pink': '#ff3399',
    'Purple': '#9933ff',
    'Green': '#33cc33',
    'Orange': '#ff9933',
    'Teal': '#33cccc',
    'Violet': '#6600ff'
  };

  function getMunicipalityColor(name) {
    if (!name) return '#d1d5db';
    const n = name.trim().toLowerCase();
    
    // Matched to LEYECO III System Map image
    if (n.includes('capoocan'))  return '#ff7675';   // Salmon / Soft Red
    if (n.includes('carigara'))  return '#fab1a0';   // Light Orange / Peach
    if (n.includes('barugo'))    return '#ff9ff3';   // Bright Pink
    if (n.includes('san miguel')) return '#badc58';  // Lime Green
    if (n.includes('tunga'))     return '#00d2d3';   // Light Blue / Cyan
    if (n.includes('alangalang')) return '#a29bfe';  // Lavender
    if (n.includes('jaro'))      return '#6c5ce7';   // Purple / Violet
    if (n.includes('santa fe'))   return '#feca57';  // Amber / Yellow-Orange
    if (n.includes('pastrana'))  return '#1dd1a1';   // Mint / Teal Green
    
    // Default color for non-highlighted municipalities
    return '#d1d5db'; // Light Gray
  }

  function loadMunicipalities() {
    // Fetching the pre-filtered Barangay boundaries (Level 3) for the 9 target municipalities
    fetch('/static/data/barangay-boundaries.json')
      .then(r => {
        if (!r.ok) {
            if (r.status === 404) {
                console.warn('Barangay GeoJSON not found at /static/data/barangay-boundaries.json. Skipping boundaries.');
            } else {
                throw new Error('Fetch failed: ' + r.status);
            }
            return null;
        }
        return r.json();
      })
      .then(data => {
        if (!data) return;
        municipalityLayer.addData(data);
        calculateMunicipalityCenters(); // Recalculate centers after data load
        updateMunicipalityLabels(); // Refresh labels after data load
        console.log('Barangay boundaries loaded.');
      })
      .catch(err => {
        console.warn('Graceful skip: Barangay boundary loading failed:', err.message);
      });
  }

  // --- Zoom Event Logic with Debounce ---
  let zoomTimeout;
  map.on('zoomend', function() {
    clearTimeout(zoomTimeout);
    zoomTimeout = setTimeout(function() {
        const zoom = map.getZoom();
        console.log('Map Zoom Level:', zoom);
        
        // Update Municipality/Barangay labels based on zoom
        updateMunicipalityLabels();
        
        if (zoom < 13) {
            if (map.hasLayer(postsLayer)) map.removeLayer(postsLayer);
            if (map.hasLayer(secondaryLinesLayer)) map.removeLayer(secondaryLinesLayer);
        } else {
            if (!map.hasLayer(postsLayer)) map.addLayer(postsLayer);
            // Only re-add layers if the user's overlay checkbox is ON
            if (secondaryLayerOverlayOn && !map.hasLayer(secondaryLinesLayer)) map.addLayer(secondaryLinesLayer);
        }
    }, 300);
  });

  function updateNetworkLineColors() {
    function updateLayer(layer) {
      if (layer instanceof L.Polyline) {
        const color = getLineColor(layer.circuitType, layer.phasingType);
        layer.setStyle({ color: color });
      }
    }
    connectionsLayer.eachLayer(updateLayer);
    primaryLinesLayer.eachLayer(updateLayer);
    secondaryLinesLayer.eachLayer(updateLayer);
  }

  function updateNetworkLineWeights() {
    function updateWeight(layer) {
      if (layer instanceof L.Polyline && layer._connType) {
        const weight = getLineWeight(layer._connType);
        layer.setStyle({ weight: weight });
      }
    }
    connectionsLayer.eachLayer(updateWeight);
    primaryLinesLayer.eachLayer(updateWeight);
    secondaryLinesLayer.eachLayer(updateWeight);
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

  function addPostMarker(layer, p) {
    const lat = parseFloat(p.lat);
    const lng = parseFloat(p.lng);
    if (Number.isNaN(lat) || Number.isNaN(lng)) return;

    const isTransformer = p.has_transformer === true || (p.kva_rating != null && p.kva_rating > 0);
    const iconToUse = isTransformer ? transformerPoleIcon : poleIcon;
    const titleText = (p.name || `Post ${p.id}`) + (isTransformer ? ' (Transformer)' : '');
    const marker = L.marker([lat, lng], { title: titleText, icon: iconToUse });

    // Store post data on marker
    marker._postData = p;

    // Keep references for selection / mapping
    try { postMarkers[p.id] = marker; } catch (e) { }
    if (p.pole_number) {
      poleToPostMap[p.pole_number] = p;
      busToPostMap[p.pole_number] = p;
    }
    if (p.primary_bus_id) {
      busToPostMap[p.primary_bus_id] = p;
    }

    // Tooltip handling
    const tooltipText = `ID: ${p.id}` + (isTransformer ? ' (Transformer)' : '');
    marker.bindTooltip(tooltipText, { permanent: false, direction: 'top' });
    marker.addTo(layer);
    _allPostMarkers.push(marker);

    marker.on('mouseover', function () {
      if (window._lastTooltipMarker && window._lastTooltipMarker !== marker) {
        window._lastTooltipMarker.closeTooltip();
      }
      marker.openTooltip();
      window._lastTooltipMarker = marker;
    });

    marker.on('mouseout', function () {
      setTimeout(function () {
        marker.closeTooltip();
        if (window._lastTooltipMarker === marker) window._lastTooltipMarker = null;
      }, 250);
    });

    // Fit map bounds
    bounds.extend([lat, lng]);

    // Simplified click handler
    marker.on('click', function (e) {
      if (window._selectionMode) {
        toggleSelect(p.id, lat, lng, marker);
        return;
      }
      if (connectionMode) {
        addPointToConnection({ post_id: p.id, lat: lat, lng: lng });
        return;
      }
      openPostInInspector(p);
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
  function loadPosts() {
    console.log('🔄 Loading posts...');
    return fetch('/api/posts?in_ph=1&per_page=1000')
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
            if (p.feeder) knownFeeders.add(p.feeder);
            addedCount++;
          } else {
            console.warn('Skipping post with missing coords:', p);
          }
        });

        console.log(`Added ${addedCount} markers to posts layer`);

        // Refresh the feeder list UI after posts are loaded
        if (typeof window._refreshFeederList === 'function') window._refreshFeederList();

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

        // If a target post id was provided via URL params, center/fly to it and open inspector
        try {
          const targetId = window._targetPostId;
          if (targetId) {
            const tid = parseInt(targetId, 10);
            console.log('Targeting post ID:', tid);
            setTimeout(function () {
              const marker = postMarkers[tid];
              if (marker && marker.getLatLng) {
                try { map.flyTo(marker.getLatLng(), 17); } catch (e) { map.setView(marker.getLatLng(), 17); }
                // Trigger click to open both popup AND the sidebar inspector
                marker.fire('click');
              } else {
                console.warn('Target marker not found:', tid);
              }
            }, 500); // Slightly longer delay to ensure layer is fully ready
          }
        } catch (e) { console.error('Error in target post handling:', e); }
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
          let lineWeight = getLineWeight(connType);
          let dashArray = null;

          // Adjust dash based on connection type
          if (connType.includes('Secondary')) {
            dashArray = null; // Changed from '5, 5' to null to ensure solid lines
          }

          // Create polyline
          const polyline = L.polyline([fromLatLng, toLatLng], {
            color: lineColor,
            weight: lineWeight,
            opacity: 0.7,
            dashArray: dashArray,
            renderer: mainCanvas // Enable Canvas Rendering
          });

          // Store circuit type for dynamic styling
          polyline.circuitType = conn.circuit;
          polyline.phasingType = conn.phasing; 
          polyline._connType = connType;

          // Add popup
          const popupText = `<div class="popup-card">
            <div class="popup-card-header">
              <h4 class="popup-card-title">⚡ ${connType.replace(/_/g, ' → ')}</h4>
            </div>
            <div class="popup-card-body">
              <div class="popup-kv-grid">
                <div class="popup-kv-label">From Bus:</div><div class="popup-kv-value">${fromBus}</div>
                <div class="popup-kv-label">To Bus:</div><div class="popup-kv-value">${toBus}</div>
                <div class="popup-kv-label">Feeder:</div><div class="popup-kv-value">${conn.feeder || 'N/A'}</div>
                <div class="popup-kv-label">Circuit:</div><div class="popup-kv-value">${conn.circuit || 'N/A'}</div>
                <div class="popup-kv-label">Phasing:</div><div class="popup-kv-value">${conn.phasing || 'N/A'}</div>
              </div>
            </div>
          </div>`;
          polyline.bindPopup(popupText);

          // Separate into primary or secondary layer
          const isSecondary = connType.toLowerCase().includes('secondary');
          if (isSecondary) {
            polyline.addTo(secondaryLinesLayer);
          } else {
            polyline.addTo(primaryLinesLayer);
          }
          drawnCount++;
        });

        // Refresh visibility based on current zoom and user overlay state
        const zoom = map.getZoom();
        if (zoom < 13) {
            if (map.hasLayer(secondaryLinesLayer)) map.removeLayer(secondaryLinesLayer);
        } else {
            if (secondaryLayerOverlayOn && !map.hasLayer(secondaryLinesLayer)) map.addLayer(secondaryLinesLayer);
        }

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
      var pathMeta = { 
        connection_type: line.connection_type || '', 
        circuit: line.circuit, 
        feeder: line.feeder, 
        phasing: line.phasing, 
        from_bus: line.from_bus, 
        to_bus: line.to_bus, 
        length_meters: line.length_meters, 
        segments: 1,
        all_buses: new Set()
      };
      if (line.from_bus) pathMeta.all_buses.add(line.from_bus);
      if (line.to_bus) pathMeta.all_buses.add(line.to_bus);
      used[i] = true;
      var changed = true;
      while (changed) {
        changed = false;
        var head = points[points.length - 1];
        var tail = points[0];
        for (var j = 0; j < lines.length; j++) {
          if (used[j]) continue;
          var s = lines[j];

          // NEW: Enforce metadata matching. Only merge if type, feeder, circuit, and phasing match.
          // This prevents primary lines from being merged into secondary lines (or vice versa),
          // which would corrupt the filter categorization on the resulting polyline.
          if ((s.connection_type || '') !== (pathMeta.connection_type || '') ||
              (s.feeder || '') !== (pathMeta.feeder || '') ||
              (s.circuit || '') !== (pathMeta.circuit || '') ||
              (s.phasing || '') !== (pathMeta.phasing || '')) {
            continue;
          }

          var s1 = [parseFloat(s.lat1), parseFloat(s.lng1)];
          var s2 = [parseFloat(s.lat2), parseFloat(s.lng2)];
          if (samePoint(head[0], head[1], s1[0], s1[1])) { points.push(s2); pathMeta.segments++; pathMeta.to_bus = s.to_bus; if (s.from_bus) pathMeta.all_buses.add(s.from_bus); if (s.to_bus) pathMeta.all_buses.add(s.to_bus); if (s.length_meters != null && !Number.isNaN(s.length_meters)) pathMeta.length_meters = (pathMeta.length_meters || 0) + s.length_meters; used[j] = true; changed = true; break; }
          if (samePoint(head[0], head[1], s2[0], s2[1])) { points.push(s1); pathMeta.segments++; pathMeta.to_bus = s.from_bus; if (s.from_bus) pathMeta.all_buses.add(s.from_bus); if (s.to_bus) pathMeta.all_buses.add(s.to_bus); if (s.length_meters != null && !Number.isNaN(s.length_meters)) pathMeta.length_meters = (pathMeta.length_meters || 0) + s.length_meters; used[j] = true; changed = true; break; }
          if (samePoint(tail[0], tail[1], s2[0], s2[1])) { points.unshift(s1); pathMeta.segments++; pathMeta.from_bus = s.from_bus; if (s.from_bus) pathMeta.all_buses.add(s.from_bus); if (s.to_bus) pathMeta.all_buses.add(s.to_bus); if (s.length_meters != null && !Number.isNaN(s.length_meters)) pathMeta.length_meters = (pathMeta.length_meters || 0) + s.length_meters; used[j] = true; changed = true; break; }
          if (samePoint(tail[0], tail[1], s1[0], s1[1])) { points.unshift(s2); pathMeta.segments++; pathMeta.from_bus = s.to_bus; if (s.from_bus) pathMeta.all_buses.add(s.from_bus); if (s.to_bus) pathMeta.all_buses.add(s.to_bus); if (s.length_meters != null && !Number.isNaN(s.length_meters)) pathMeta.length_meters = (pathMeta.length_meters || 0) + s.length_meters; used[j] = true; changed = true; break; }
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
        if (typeof networkLinesLayer !== 'undefined') networkLinesLayer.clearLayers();
        primaryLinesLayer.clearLayers();
        secondaryLinesLayer.clearLayers();
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
            hintEl.innerHTML = 'No network lines yet. Upload posts with <strong>Post ID, Latitude, Longitude</strong> from the <a href="/resources">Resources</a> page to see lines on the map.';
            hintEl.style.display = 'block';
          }
        } else {
          if (hintEl) { hintEl.style.display = 'none'; }
        }
        // Chain segments into continuous paths so the network draws as connected lines, not many separate straight segments
        var paths = chainSegmentsIntoPaths(lines);
        paths.forEach(function (pathObj) {
          var points = pathObj.points;
          var meta = pathObj.meta;
          if (points.length < 2) return;
          var connType = meta.connection_type || '';
          var color = getLineColor(meta.circuit, meta.phasing);
          var weight = getLineWeight(connType);
          var dash = null;
          
          var poly = L.polyline(points, { 
            color: color, 
            weight: weight, 
            opacity: 0.8, 
            dashArray: dash, 
            lineJoin: 'round', 
            lineCap: 'round',
            renderer: mainCanvas // Enable Canvas Rendering
          });

          // Store circuit type and phasing for dynamic styling on layer change
          poly.circuitType = meta.circuit;
          poly.phasingType = meta.phasing;
          poly._feederName = meta.feeder || '';
          poly._connType = connType;
          poly._allBuses = Array.from(meta.all_buses);
          if (meta.feeder) knownFeeders.add(meta.feeder);

          var segStr = meta.segments > 1 ? ' (' + meta.segments + ' segments)' : '';
          var popup = `<div class="popup-card">
            <div class="popup-card-header">
              <h4 class="popup-card-title">⚡ ${(connType.replace(/_/g, ' → ') || 'Network')}${segStr}</h4>
            </div>
            <div class="popup-card-body">
              <div class="popup-kv-grid">
                <div class="popup-kv-label">From:</div><div class="popup-kv-value">${meta.from_bus || '—'}</div>
                <div class="popup-kv-label">To:</div><div class="popup-kv-value">${meta.to_bus || '—'}</div>
                <div class="popup-kv-label">Feeder:</div><div class="popup-kv-value">${meta.feeder || '—'}</div>
                <div class="popup-kv-label">Circuit:</div><div class="popup-kv-value">${meta.circuit || '—'}</div>
                <div class="popup-kv-label">Phasing:</div><div class="popup-kv-value">${meta.phasing || 'N/A'}</div>
                ${meta.length_meters != null && !Number.isNaN(meta.length_meters) ? `<div class="popup-kv-label">Length:</div><div class="popup-kv-value">${Number(meta.length_meters).toFixed(2)} m</div>` : ''}
              </div>
            </div>
          </div>`;
          poly.bindPopup(popup);
          
          // Add to master network layer
          if (typeof networkLinesLayer !== 'undefined') poly.addTo(networkLinesLayer);

          // Separate into primary or secondary layer for legacy toggles (but don't add to map if networkLinesLayer is added)
          const isSecondary = connType.toLowerCase().includes('secondary');
          if (isSecondary) {
            poly.addTo(secondaryLinesLayer);
          } else {
            poly.addTo(primaryLinesLayer);
          }
        });

        // Trigger zoom visibility check immediately after loading, respecting overlay state
        const zoom = map.getZoom();
        if (zoom < 13) {
            if (map.hasLayer(secondaryLinesLayer)) map.removeLayer(secondaryLinesLayer);
        } else {
            if (secondaryLayerOverlayOn && !map.hasLayer(secondaryLinesLayer)) map.addLayer(secondaryLinesLayer);
        }

        // Refresh the feeder filter UI after network lines are loaded
        if (typeof window._refreshFeederList === 'function') window._refreshFeederList();
        var totalM = stats.total_length_meters != null ? stats.total_length_meters : 0;
        console.log('Network geometry: ' + lines.length + ' segments chained into ' + paths.length + ' paths (nodes: ' + (stats.nodes || 0) + ', total length: ' + (typeof totalM === 'number' ? totalM.toFixed(2) : totalM) + ' m)');
      })
      .catch(function (err) { console.warn('Network geometry load failed:', err); });
  }


  // Load connections after posts are loaded
  setTimeout(function () {
    console.log('Calling loadLineConnections after posts...');
    loadLineConnections();
    loadNetworkGeometry();
    loadMunicipalities(); // Call municipality load
  }, 500);

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



  function showResultModal(options) {
      let title = '';
      let msg = '';
      let isError = false;
      
      if (options.error) {
        title = 'Connection failed';
        msg = options.message || options.error;
        isError = true;
      } else if (options.customTitle) {
        title = options.customTitle;
        msg = options.message || '';
      } else {
        title = options.count === 0 && options.id != null ? 'Post added' : (options.count > 1 ? 'Connections saved' : 'Connection saved');
        msg = options.message || (options.name ? `"${options.name}" has been saved.` : 'Connection has been saved.');
      }
      
      let html = `<div class="info-card ${isError ? 'error-card' : ''}">`;
      html += `<p style="margin-bottom: 15px; ${isError ? 'color: var(--danger); font-weight: 500;' : ''}">${msg}</p>`;
      
      if (!isError && !options.customTitle) {
          const length = options.length != null ? options.length : 0;
          const count = options.count != null ? options.count : (options.id != null ? 1 : 0);
          
          html += '<div class="kv-grid">';
          if (count > 1) {
            html += `<div class="kv-item"><div class="kv-label">Segments saved</div><div class="kv-value">${count} post-to-post</div></div>`;
            html += `<div class="kv-item"><div class="kv-label">Total length</div><div class="kv-value">${formatMeters(length)}</div></div>`;
          } else if (count === 0 && options.id != null) {
            html += `<div class="kv-item"><div class="kv-label">Post ID</div><div class="kv-value">${options.id}</div></div>`;
          } else {
            html += `<div class="kv-item"><div class="kv-label">Connection ID</div><div class="kv-value">${options.id != null ? options.id : '—'}</div></div>`;
            html += `<div class="kv-item"><div class="kv-label">Length</div><div class="kv-value">${formatMeters(length)}</div></div>`;
          }
          html += '</div>';
      }
      html += '</div>';
      
      renderInInspector(title, html);
  }

  // --- Primary line-overhead modal (post technical data) ---
  var _primaryLineOverheadModal = null;
  var PRIMARY_LINE_OVERHEAD_FIELDS = [
    { key: 'length_meters', label: 'Length (m)' },
    { key: 'conductor_type', label: 'Conductor type' },
    { key: 'conductor_size', label: 'Conductor size' },
    { key: 'conductor_unit', label: 'Conductor unit' },
    { key: 'conductor_strands', label: 'Conductor strands' },
    { key: 'configuration', label: 'Configuration' },
    { key: 'system_grounding_type', label: 'System grounding type' },
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
  function showPrimaryLineOverheadModal(data) {
    let title = 'Primary line-overhead' + (data && data.name ? ' — ' + data.name : (data && data.segment_id ? ' — ' + data.segment_id : ''));
    let html = '<div class="info-card"><div class="kv-grid">';
    
    PRIMARY_LINE_OVERHEAD_FIELDS.forEach(function (f) {
      // Support both Post model keys (pri_conductor_size, neutral_wire) and DistributionLineSegment keys
      var val = data && (data[f.key] !== undefined ? data[f.key] : undefined);
      // Fallback aliases
      if ((val === undefined || val === null || val === '') && f.key === 'conductor_size') val = data && data['pri_conductor_size'];
      if ((val === undefined || val === null || val === '') && f.key === 'neutral_wire_type') val = data && (data['neutral_wire'] || data['neutral_wire_type']);
      if (val === undefined || val === null || val === '') val = '—';
      else if (typeof val === 'number') val = Number(val);
      
      html += `<div class="kv-item"><div class="kv-label">${f.label}</div><div class="kv-value">${val}</div></div>`;
    });
    
    html += '</div></div>';
    renderInInspector(title, html);
  }

  // --- Distribution Transformer modal ---
  var _distributionTransformerModal = null;
  var DISTRIBUTION_TRANSFORMER_FIELDS = [
    { key: 'id', label: 'ID' },
    { key: 'transformer_id', label: 'Transformer ID' },
    { key: 'from_primary_bus_id', label: 'From Bus' },
    { key: 'to_secondary_bus_id', label: 'To (Sec) Bus' },
    { key: 'kva_rating', label: 'kVA Rating' },
    { key: 'primary_phasing', label: 'Pri. Phasing' },
    { key: 'secondary_phasing', label: 'Sec. Phasing' },
    { key: 'installation_type', label: 'Installation' },
    { key: 'connection', label: 'Connection' },
    { key: 'primary_voltage_kv', label: 'Pri. Voltage (kV)' },
    { key: 'secondary_voltage_kv', label: 'Sec. Voltage (kV)' },
    { key: 'pct_z', label: '%Z' },
    { key: 'xr_ratio', label: 'X/R Ratio' },
    { key: 'no_load_loss_kw', label: 'No-Load Loss (kW)' },
    { key: 'exciting_current_pct', label: 'Exciting Current (%)' }
  ];
  function showDistributionTransformerModal(data) {
    let title = 'Distribution Transformer' + (data && data.transformer_id ? ' — ' + data.transformer_id : '');
    let html = '<div class="info-card"><div class="kv-grid">';

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

      html += `<div class="kv-item"><div class="kv-label">${f.label}</div><div class="kv-value">${val}</div></div>`;
    });

    html += '</div></div>';
    renderInInspector(title, html);
  }

  // --- Secondary Line modal ---
  var SECONDARY_LINE_FIELDS = [
    { key: 'segment_id', label: 'Line ID' },
    { key: 'from_bus_id', label: 'From Bus' },
    { key: 'to_bus_id', label: 'To Bus' },
    { key: 'phasing', label: 'Phasing' },
    { key: 'conductor_type', label: 'Conductor Type' },
    { key: 'conductor_size', label: 'Conductor Size' },
    { key: 'conductor_unit', label: 'Unit' },
    { key: 'length_meters', label: 'Length (m)' },
    { key: 'installation_type', label: 'Installation' }
  ];

  function showSecondaryLineModal(data) {
    let title = 'Secondary Lines (' + (data.count || 0) + ')';
    let html = '';

    if (!data.secondary_lines || data.secondary_lines.length === 0) {
      html = '<div class="info-card"><div class="kv-value" style="text-align:center; color:var(--text-secondary);">No secondary lines found for this bus.</div></div>';
    } else {
      data.secondary_lines.forEach(function (line, idx) {
        var lineId = line.secondary_line_id ? line.secondary_line_id : `Line #${idx + 1}`;
        html += `<div class="info-card"><div class="info-card-header"><h4 class="info-card-title">${lineId}</h4></div><div class="kv-grid">`;

        SECONDARY_LINE_FIELDS.forEach(function (f) {
          var val = line[f.key];
          if (val === undefined || val === null || val === '') return;
          if (typeof val === 'number') val = Number(val);

          html += `<div class="kv-item"><div class="kv-label">${f.label}</div><div class="kv-value">${val}</div></div>`;
        });
        html += '</div></div>';
      });
    }

    renderInInspector(title, html);
  }

  // --- Secondary Service Drop modal ---
  var SERVICE_DROP_FIELDS = [
    { key: 'service_drop_id', label: 'Drop ID' },
    { key: 'to_customer_id', label: 'Customer ID' },
    { key: 'phasing', label: 'Phasing' },
    { key: 'conductor_type', label: 'Conductor Type' },
    { key: 'conductor_size', label: 'Conductor Size' },
    { key: 'conductor_unit', label: 'Unit' },
    { key: 'length_meters_1', label: 'Length-1 (m)' },
    { key: 'length_meters_2', label: 'Length-2 (m)' },
    { key: 'installation_type', label: 'Installation' }
  ];

  function showServiceDropModal(data) {
    let title = 'Service Drops (' + (data.count || 0) + ')';
    let html = '';

    if (!data.service_drops || data.service_drops.length === 0) {
      html = '<div class="info-card" style="text-align:center; color:var(--text-secondary);">No service drops found for this bus.</div>';
    } else {
      data.service_drops.forEach(function (drop, idx) {
        let cardHtml = '<div class="info-card">';
        
        let dropTitle = 'Drop #' + (idx + 1) + (drop.service_drop_id ? ' (' + drop.service_drop_id + ')' : '');
        cardHtml += `<div class="info-card-header"><div class="info-card-title">${dropTitle}</div>`;
        
        if (drop.to_customer_id) {
          // Add a custom data attribute instead of an inline onclick handler to avoid evaluating JS directly here
          cardHtml += `<button class="btn btn-sm view-customer-btn" data-cust-id="${drop.to_customer_id}" style="font-size: 0.8rem; padding: 4px 12px;">View Customer Info</button>`;
        }
        cardHtml += '</div><div class="kv-grid">';

        SERVICE_DROP_FIELDS.forEach(function (f) {
          var val = drop[f.key];
          if (val === undefined || val === null || val === '') return;
          cardHtml += `<div class="kv-item"><div class="kv-label">${f.label}</div><div class="kv-value">${val}</div></div>`;
        });
        
        cardHtml += '</div></div>';
        html += cardHtml;
      });
    }

    renderInInspector(title, html);

    // Attach event listeners for customer view since we used custom HTML
    const inspectorContent = document.getElementById('inspector-content');
    if (inspectorContent) {
        const btns = inspectorContent.querySelectorAll('.view-customer-btn');
        btns.forEach(btn => {
            btn.onclick = () => showCustomerInfoModal(btn.getAttribute('data-cust-id'));
        });
    }
  }

  // --- Confirmation modal (replaces window.confirm) ---
  let _confirmModal = null;
  function showConfirmModal(message, opts) {
    opts = opts || {};
    return new Promise((resolve) => {
      let html = `
        <div class="info-card">
          <p style="margin-bottom: 20px; font-weight: 500; font-size: 1.05rem;">${message}</p>
          <div style="display: flex; gap: 10px; justify-content: flex-end; padding-top: 10px; border-top: 1px solid var(--border);">
            <button class="btn btn-secondary inspector-confirm-cancel">${opts.cancelText || 'Cancel'}</button>
            <button class="btn btn-danger inspector-confirm-ok">${opts.okText || 'Confirm'}</button>
          </div>
        </div>
      `;
      renderInInspector(opts.title || 'Confirm', html);

      const inspectorContent = document.getElementById('inspector-content');
      if (inspectorContent) {
        const okBtn = inspectorContent.querySelector('.inspector-confirm-ok');
        const cancelBtn = inspectorContent.querySelector('.inspector-confirm-cancel');
        
        function cleanup() {
            const layoutEl = document.querySelector('.premium-layout');
            if (layoutEl) layoutEl.classList.remove('inspector-open');
        }
        
        if (okBtn) okBtn.onclick = () => { cleanup(); resolve(true); };
        if (cancelBtn) cancelBtn.onclick = () => { cleanup(); resolve(false); };
      }
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

  // --- Global Inspector Renderer ---
  function renderInInspector(title, htmlString) {
    const inspectorContent = document.getElementById('inspector-content');
    const layoutEl = document.querySelector('.premium-layout');
    if (inspectorContent && layoutEl) {
        layoutEl.classList.add('inspector-open');
        
        // Hide existing children to create a history stack
        const children = Array.from(inspectorContent.children);
        let hasPrevious = false;
        
        children.forEach(child => {
            if (child.style.display !== 'none' && !child.classList.contains('inspector-hidden-for-subview')) {
                hasPrevious = true;
                child.dataset.oldDisplay = child.style.display || '';
                child.style.display = 'none';
                child.classList.add('inspector-hidden-for-subview');
            }
        });

        const newView = document.createElement('div');
        newView.className = 'inspector-view-layer';
        newView.style.display = 'flex';
        
        newView.innerHTML = `
          <div class="inspector-header">
            <div style="display:flex; align-items:center; gap:8px;">
              ${hasPrevious ? `<button class="btn-icon btn-inspector-back" style="background:transparent; padding:4px;" title="Go Back">←</button>` : ''}
              <h3 style="margin:0; font-size:1.1rem; color:var(--text-primary);">${title}</h3>
            </div>
            <button class="btn-icon close-inspector-layer" style="background:var(--surface-secondary);border-radius:50%;">✕</button>
          </div>
          <div class="inspector-body">${htmlString}</div>
          
          <div class="inspector-footer">
             ${hasPrevious ? `<button class="btn btn-secondary btn-inspector-footer-back">Back</button>` : ''}
             <button class="btn btn-primary btn-inspector-ok">OK</button>
          </div>
        `;
        
        inspectorContent.appendChild(newView);

        const closeHandler = () => {
            layoutEl.classList.remove('inspector-open');
            // Clean up all dynamically added subviews and restore original root
            const allLayers = inspectorContent.querySelectorAll('.inspector-view-layer');
            allLayers.forEach(layer => layer.remove());
            
            const rootLayer = inspectorContent.querySelector('.inspector-root-layer');
            if (rootLayer) {
                rootLayer.style.display = rootLayer.dataset.oldDisplay || 'block';
                rootLayer.classList.remove('inspector-hidden-for-subview');
            }

            if (window._selectionIndicatorMarker) {
                if (window._mapInstance) {
                   window._mapInstance.removeLayer(window._selectionIndicatorMarker);
                } else if (typeof map !== 'undefined') {
                   map.removeLayer(window._selectionIndicatorMarker);
                }
                window._selectionIndicatorMarker = null;
            }
        };

        const backHandler = () => {
            newView.remove(); // Remove this current layer
            
            // Find the most recently hidden layer and restore it
            const hiddenLayers = Array.from(inspectorContent.children).filter(c => c.classList.contains('inspector-hidden-for-subview'));
            if (hiddenLayers.length > 0) {
                const lastHidden = hiddenLayers[hiddenLayers.length - 1];
                lastHidden.style.display = lastHidden.dataset.oldDisplay || 'block';
                lastHidden.classList.remove('inspector-hidden-for-subview');
            }
        };

        const closeBtn = newView.querySelector('.close-inspector-layer');
        if (closeBtn) closeBtn.onclick = closeHandler;
        
        const okBtn = newView.querySelector('.btn-inspector-ok');
        // OK acts as "Back" if there's a history, otherwise it closes.
        if (okBtn) okBtn.onclick = hasPrevious ? backHandler : closeHandler;

        const backBtnTop = newView.querySelector('.btn-inspector-back');
        if (backBtnTop) backBtnTop.onclick = backHandler;

        const backBtnFooter = newView.querySelector('.btn-inspector-footer-back');
        if (backBtnFooter) backBtnFooter.onclick = backHandler;

    } else {
        // Fallback if inspector is not present in the DOM (e.g. some other page)
        const m = createNoticeModal();
        m.querySelector('.notice-title').textContent = title || 'Notice';
        m.querySelector('.notice-message').innerHTML = htmlString || '';
        m.style.display = 'flex';
        m.tabIndex = -1;
        m.focus();
    }
  }

  function showNoticeModal(title, message) {
    const existing = document.getElementById('custom-notice-modal');
    if (existing) existing.remove();

    const overlay = document.createElement('div');
    overlay.id = 'custom-notice-modal';
    Object.assign(overlay.style, {
      position: 'fixed', top: '0', left: '0',
      width: '100vw', height: '100vh',
      backgroundColor: 'rgba(15, 23, 42, 0.55)',
      backdropFilter: 'blur(6px)',
      zIndex: '999999',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      opacity: '0', transition: 'opacity 0.2s ease'
    });

    const card = document.createElement('div');
    Object.assign(card.style, {
      background: '#ffffff',
      borderRadius: '16px',
      padding: '28px 28px 22px',
      width: '90%', maxWidth: '480px',
      boxShadow: '0 25px 50px rgba(0,0,0,0.15), 0 0 0 1px rgba(0,0,0,0.04)',
      transform: 'scale(0.94) translateY(12px)',
      transition: 'all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275)',
      display: 'flex', flexDirection: 'column', gap: '0'
    });

    // Icon bar
    const iconMap = { 'Error': '❌', 'Info': 'ℹ️', 'Success': '✅', 'Outage Impact Analysis': '⚠️', 'Trace Downstream Result': '⚡', 'Analysis': '🔄', 'Outage Impact': '🔴' };
    const icon = iconMap[title] || '📋';

    const header = document.createElement('div');
    Object.assign(header.style, { display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '16px' });

    const iconEl = document.createElement('div');
    Object.assign(iconEl.style, {
      width: '42px', height: '42px', borderRadius: '10px',
      background: title === 'Error' ? '#fee2e2' : title.includes('Outage') ? '#fff1f2' : '#f0f9ff',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontSize: '20px', flexShrink: '0'
    });
    iconEl.textContent = icon;

    const titleEl = document.createElement('h3');
    titleEl.textContent = title || 'Notice';
    Object.assign(titleEl.style, { margin: '0', color: '#0f172a', fontSize: '1.15rem', fontWeight: '700', lineHeight: '1.2' });

    header.appendChild(iconEl);
    header.appendChild(titleEl);

    const body = document.createElement('div');
    body.innerHTML = message || '';
    Object.assign(body.style, {
      color: '#475569', fontSize: '0.9rem', lineHeight: '1.6',
      marginBottom: '22px', maxHeight: '55vh', overflowY: 'auto',
      paddingRight: '4px'
    });

    const footer = document.createElement('div');
    Object.assign(footer.style, { display: 'flex', justifyContent: 'flex-end' });

    const okBtn = document.createElement('button');
    okBtn.textContent = 'Acknowledge';
    Object.assign(okBtn.style, {
      padding: '9px 22px', backgroundColor: '#0ea5e9',
      color: 'white', border: 'none', borderRadius: '8px',
      fontWeight: '600', fontSize: '0.9rem', cursor: 'pointer',
      transition: 'background 0.2s ease'
    });
    okBtn.onmouseover = () => okBtn.style.backgroundColor = '#0284c7';
    okBtn.onmouseout = () => okBtn.style.backgroundColor = '#0ea5e9';

    const close = () => {
      overlay.style.opacity = '0';
      card.style.transform = 'scale(0.94) translateY(12px)';
      setTimeout(() => overlay.remove(), 220);
    };

    okBtn.onclick = close;
    overlay.onclick = (e) => { if (e.target === overlay) close(); };

    footer.appendChild(okBtn);
    card.appendChild(header);
    card.appendChild(body);
    card.appendChild(footer);
    overlay.appendChild(card);
    document.body.appendChild(overlay);

    requestAnimationFrame(() => {
      overlay.style.opacity = '1';
      card.style.transform = 'scale(1) translateY(0)';
    });
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
          const popupHtml = `<div class="popup-card">
            <div class="popup-card-header">
              <h4 class="popup-card-title">📍 ${c.name}</h4>
            </div>
            <div class="popup-card-body">
              <div class="popup-kv-grid">
                <div class="popup-kv-label">Length:</div><div class="popup-kv-value">${formatMeters(c.total_length || 0)}</div>
                <div class="popup-kv-label">Points:</div><div class="popup-kv-value">${c.points.length}</div>
                <div class="popup-kv-label">Connected IDs:</div><div class="popup-kv-value">${postList}</div>
              </div>
            </div>
            <div class="popup-footer">
              <button class="btn btn-danger disconnect-conn" data-conn-id="${c.id}">Disconnect</button>
            </div>
          </div>`;
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

  function showVoltageRegulatorModal(data) {
    let title = 'Voltage Regulators (' + (data.count || 0) + ')';
    let html = '';
    if (!data.items || data.items.length === 0) {
      html = '<div class="info-card"><div class="kv-value" style="text-align:center;">No items found.</div></div>';
    } else {
      data.items.forEach((item, idx) => {
        let card = '<div class="info-card">';
        card += `<div class="info-card-header"><h4 class="info-card-title">Item #${idx + 1} (${item.regulator_id || ''})</h4></div>`;
        card += '<div class="kv-grid">';
        VR_FIELDS.forEach(f => {
          let val = item[f.key];
          if (val !== undefined && val !== null && val !== '') {
            card += `<div class="kv-item"><div class="kv-label">${f.label}</div><div class="kv-value">${val}</div></div>`;
          }
        });
        card += '</div></div>';
        html += card;
      });
    }
    renderInInspector(title, html);
  }

  // Shunt Capacitor
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

  function showShuntCapacitorModal(data) {
    let title = 'Shunt Capacitors (' + (data.count || 0) + ')';
    let html = '';
    if (!data.items || data.items.length === 0) {
      html = '<div class="info-card"><div class="kv-value" style="text-align:center;">No items found.</div></div>';
    } else {
      data.items.forEach((item, idx) => {
        let card = '<div class="info-card">';
        card += `<div class="info-card-header"><h4 class="info-card-title">Item #${idx + 1} (${item.capacitor_id || ''})</h4></div>`;
        card += '<div class="kv-grid">';
        SC_FIELDS.forEach(f => {
          let val = item[f.key];
          if (val !== undefined && val !== null && val !== '') {
            card += `<div class="kv-item"><div class="kv-label">${f.label}</div><div class="kv-value">${val}</div></div>`;
          }
        });
        card += '</div></div>';
        html += card;
      });
    }
    renderInInspector(title, html);
  }

  // Shunt Inductor
  const SI_FIELDS = [
    { key: 'inductor_id', label: 'ID' },
    { key: 'bus_connected_id', label: 'Bus' },
    { key: 'phase_type', label: 'Phase Type' },
    { key: 'phasing', label: 'Phasing' },
    { key: 'voltage_rating_kv', label: 'Voltage (kV)' },
    { key: 'resistance_a', label: 'R (A)' },
    { key: 'reactance_a', label: 'X (A)' }
  ];

  function showShuntInductorModal(data) {
    let title = 'Shunt Inductors (' + (data.count || 0) + ')';
    let html = '';
    if (!data.items || data.items.length === 0) {
      html = '<div class="info-card"><div class="kv-value" style="text-align:center;">No items found.</div></div>';
    } else {
      data.items.forEach((item, idx) => {
        let card = '<div class="info-card">';
        card += `<div class="info-card-header"><h4 class="info-card-title">Item #${idx + 1} (${item.inductor_id || ''})</h4></div>`;
        card += '<div class="kv-grid">';
        SI_FIELDS.forEach(f => {
          let val = item[f.key];
          if (val !== undefined && val !== null && val !== '') {
            card += `<div class="kv-item"><div class="kv-label">${f.label}</div><div class="kv-value">${val}</div></div>`;
          }
        });
        card += '</div></div>';
        html += card;
      });
    }
    renderInInspector(title, html);
  }

  // Series Inductor
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

  function showSeriesInductorModal(data) {
    let title = 'Series Inductors (' + (data.count || 0) + ')';
    let html = '';
    if (!data.items || data.items.length === 0) {
      html = '<div class="info-card"><div class="kv-value" style="text-align:center;">No items found.</div></div>';
    } else {
      data.items.forEach((item, idx) => {
        let card = '<div class="info-card">';
        card += `<div class="info-card-header"><h4 class="info-card-title">Item #${idx + 1} (${item.inductor_id || ''})</h4></div>`;
        card += '<div class="kv-grid">';
        ERI_FIELDS.forEach(f => {
          let val = item[f.key];
          if (val !== undefined && val !== null && val !== '') {
            card += `<div class="kv-item"><div class="kv-label">${f.label}</div><div class="kv-value">${val}</div></div>`;
          }
        });
        card += '</div></div>';
        html += card;
      });
    }
    renderInInspector(title, html);
  }

  function showConnectionsModal(connections, postId) {
    let title = 'Connected Lines for Post #' + postId;
    let html = '<div class="connections-list" style="max-height: 400px; overflow-y: auto; padding-right: 4px;">';
    
    html += connections.map(conn => `
      <div class="connection-item info-card" style="display: flex; justify-content: space-between; align-items: center; padding: 12px; margin-bottom: 8px;">
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
          <button class="btn btn-sm btn-disconnect" data-id="${conn.id}">Disconnect</button>
      </div>
    `).join('');
    html += '</div>';

    renderInInspector(title, html);

    // Rebind handlers
    const inspectorContent = document.getElementById('inspector-content');
    if (inspectorContent) {
        inspectorContent.querySelectorAll('.btn-disconnect').forEach(btn => {
            btn.onclick = function () {
                const id = this.getAttribute('data-id');
                // showConfirmModal is still a popup dialog, which is appropriate for confirmations!
                showConfirmModal(`Are you sure you want to disconnect ${id}? (This is a simulation)`, { title: 'Disconnect', okText: 'Disconnect', cancelText: 'Cancel' })
                  .then(confirmed => {
                    if (confirmed) {
                      showNoticeModal('Info', `Disconnected ${id} (Mock Action)`);
                      this.closest('.connection-item').style.opacity = '0.5';
                      this.disabled = true;
                      this.textContent = 'Disconnected';
                    }
                  });
            };
        });
    }
  }

  // --- Customer Info Modal ---
  window.showCustomerInfoModal = function (customerId) {
    if (!customerId) return;
    renderInInspector('Customer Info', '<div class="spinner"></div> Loading details...');
    
    fetch('/api/customers/' + encodeURIComponent(customerId))
      .then(r => r.json())
      .then(cData => {
        if (cData.error) {
          renderInInspector('Customer Info', '<div class="info-card" style="color:var(--danger);">Error: ' + cData.error + '</div>');
          return;
        }

        let html = '<div class="info-card">';
        html += '<div class="info-card-header"><h4 class="info-card-title">Account Details</h4></div>';
        html += '<div class="kv-grid">';
        html += '<div class="kv-item"><div class="kv-label">Customer Name</div><div class="kv-value">' + (cData.name || '—') + '</div></div>';
        html += '<div class="kv-item"><div class="kv-label">Customer ID</div><div class="kv-value">' + (cData.customer_id || '—') + '</div></div>';
        html += '<div class="kv-item"><div class="kv-label">Type</div><div class="kv-value">' + (cData.customer_type || '—') + '</div></div>';
        html += '<div class="kv-item"><div class="kv-label">Service Voltage</div><div class="kv-value">' + (cData.service_voltage || '—') + '</div></div>';
        html += '<div class="kv-item"><div class="kv-label">Phase</div><div class="kv-value">' + (cData.phase || '—') + '</div></div>';
        html += '</div></div>';
        
        html += '<h4 style="margin-top: 16px; margin-bottom: 10px; border-bottom: 2px solid var(--border); padding-bottom: 5px; color: var(--text-primary);">Energy Consumption</h4>';
        html += '<div id="customer-consumption-container"><div class="spinner"></div> Loading consumption...</div>';

        renderInInspector('Customer: ' + (cData.name || customerId), html);

        fetch('/api/customers/' + encodeURIComponent(customerId) + '/consumption')
          .then(r => r.json())
          .then(consData => {
            const consContainer = document.getElementById('customer-consumption-container');
            if (!consContainer) return;

            if (consData.error) {
              consContainer.innerHTML = '<div class="info-card" style="color:var(--danger);">Error loading consumption.</div>';
              return;
            }
            if (!consData.items || consData.items.length === 0) {
              consContainer.innerHTML = '<div class="info-card" style="color:var(--text-secondary); text-align:center;">No consumption records found.</div>';
              return;
            }

            let table = '<div class="table-scroll" style="border:1px solid var(--border); border-radius:var(--radius-md); overflow:hidden;"><table class="modern-table">';
            table += '<thead><tr><th>Billing Period</th><th>Energy (kWh)</th><th>Power Factor</th></tr></thead><tbody>';

            const maxRows = 200;
            const limit = Math.min(consData.items.length, maxRows);
            for (let i = 0; i < limit; i++) {
              let item = consData.items[i];
              table += '<tr>';
              table += '<td>' + (item.billing_period || '—') + '</td>';
              table += '<td>' + (item.kwh_consumed || '—') + '</td>';
              table += '<td>' + (item.power_factor || '—') + '</td>';
              table += '</tr>';
            }
            table += '</tbody></table></div>';
            if (consData.items.length > maxRows) {
              table += '<div style="margin-top:4px;font-size:0.8rem;color:var(--text-secondary);">Showing first ' + maxRows + ' records for performance.</div>';
            }
            consContainer.innerHTML = table;
          })
          .catch(() => {
            const consContainer = document.getElementById('customer-consumption-container');
            if (consContainer) consContainer.innerHTML = '<div class="info-card" style="color:var(--danger);">Failed to load consumption.</div>';
          });
      })
      .catch(() => {
        renderInInspector('Customer Info', '<div class="info-card" style="color:var(--danger);">Failed to load customer details.</div>');
      });
  };


  // ═══════════════════════════════════════════════════════
  // CUSTOMER SEARCH BAR (Top-Right Corner)
  // ═══════════════════════════════════════════════════════

  // ── 1. Build combined expandable search HTML ──
  var combinedSearchHTML = `
    <div class="search-flex-container" style="display:flex; align-items:center; flex-direction:row-reverse; gap:8px;">
      <div class="expandable-search-wrapper">
        <button id="search-icon-btn" class="search-icon-btn" title="Search Map">
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 -960 960 960" fill="currentColor" width="20" height="20">
            <path d="M784-120 532-372q-30 24-69 38t-83 14q-109 0-184.5-75.5T120-580q0-109 75.5-184.5T380-840q109 0 184.5 75.5T640-580q0 44-14 83t-38 69l252 252-56 56ZM380-400q75 0 127.5-52.5T560-580q0-75-52.5-127.5T380-760q-75 0-127.5 52.5T200-580q0 75 52.5 127.5T380-400Z"/>
          </svg>
        </button>
      </div>
      
      <div id="search-bar-expanded" class="search-bar-expanded">
        <div style="display:flex; align-items:center; background: var(--surface); border: 1.5px solid var(--border); border-radius: 20px; padding: 2px 12px; box-shadow: var(--shadow-sm); width: 100%;">
          <!-- Mode Filter -->
          <div class="search-mode-selector" style="display:flex; align-items:center; border-right: 1px solid var(--border); padding-right: 8px; margin-right: 8px;">
            <select id="search-mode-select" style="background:transparent; border:none; font-size: 0.8rem; font-weight: 500; color: var(--text-secondary); cursor:pointer; outline:none; padding: 4px 0;">
              <option value="customer" selected>Customer</option>
              <option value="coord">Coordinates</option>
            </select>
          </div>
          
          <div style="position:relative; flex: 1;">
            <input id="customer-search-input" class="top-search-input"
              type="text" placeholder="Customer ID…"
              style="border:none !important; box-shadow:none !important; padding: 6px 0 !important; width: 100%;"
              autocomplete="off" spellcheck="false" />
            <div id="customer-search-suggestions" class="customer-search-suggestions" style="top: calc(100% + 10px);"></div>
          </div>
        </div>
      </div>
    </div>
  `;

  // Append search HTML to the map header
  var mapHeader = document.querySelector('.map-header');
  if (!mapHeader) {
    // Fallback: create header if it doesn't exist
    mapHeader = document.createElement('div');
    mapHeader.className = 'map-header';
    mapEl.parentElement.insertBefore(mapHeader, mapEl);
  }

  // Create wrapper container and append to header
  var searchWrapper = document.createElement('div');
  searchWrapper.style.cssText = 'display:flex; align-items:center; z-index:1001; margin-left: auto;';
  searchWrapper.innerHTML = combinedSearchHTML;
  mapHeader.appendChild(searchWrapper);

  // Append route result to body
  var routeResultWrapper = document.createElement('div');
  routeResultWrapper.innerHTML = '<div id="route-result" class="route-result" style="display:none;"></div>';
  document.body.appendChild(routeResultWrapper);

  // ── 1.5. Toggle search bar expansion ──
  var searchIconBtn = document.getElementById('search-icon-btn');
  var searchBarExpanded = document.getElementById('search-bar-expanded');
  var customerSearchInput = document.getElementById('customer-search-input');
  var customerSearchSuggestions = document.getElementById('customer-search-suggestions');

  function toggleSearchBar(show) {
    if (show === undefined) {
      show = !searchBarExpanded.classList.contains('active');
    }

    searchBarExpanded.classList.toggle('active', show);
    searchIconBtn.setAttribute('aria-expanded', show);

    if (show) {
      customerSearchInput.focus();
      customerSearchInput.select();
    } else {
      customerSearchInput.blur();
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

    // Manage search mode
    var modeSelect = document.getElementById('search-mode-select');
    modeSelect.addEventListener('change', function() {
        var mode = modeSelect.value;
        customerSearchInput.placeholder = mode === 'customer' ? 'Customer ID…' : 'Lat, Lng (e.g. 14.5, 120.9)';
        customerSearchInput.value = '';
        customerSearchSuggestions.classList.remove('active');
        customerSearchInput.focus();
    });

    // Search input handler
    customerSearchInput.addEventListener('input', function (e) {
    clearTimeout(customerSearchTimeout);
    var query = e.target.value.trim();
    var mode = modeSelect.value;

    if (!query || query.length < 1) {
      customerSearchSuggestions.classList.remove('active');
      return;
    }

    if (mode === 'coord') {
      // Check if input looks like coordinates: "lat, lng"
      var coordRegex = /^-?\d+(\.\d+)?[\s,]+-?\d+(\.\d+)?$/;
      if (coordRegex.test(query)) {
          customerSearchSuggestions.innerHTML = `<div class="customer-search-item" id="find-nearest-btn">
            <div class="customer-search-item-id">📍 Find Nearest Post</div>
            <div class="customer-search-item-name">${query}</div>
          </div>`;
          customerSearchSuggestions.classList.add('active');
          
          document.getElementById('find-nearest-btn').onclick = function() {
              var parts = query.split(/[\s,]+/).filter(Boolean);
              if (parts.length >= 2) {
                  findNearestPost(parts[0], parts[1]);
              }
          };
      } else {
          customerSearchSuggestions.innerHTML = '<div class="customer-search-item customer-search-empty">Format: Lat, Lng</div>';
          customerSearchSuggestions.classList.add('active');
      }
      return;
    }

    // Show loading state for customer search
    customerSearchSuggestions.innerHTML = '<div class="customer-search-item customer-search-loading">🔍 Searching...</div>';
    customerSearchSuggestions.classList.add('active');

    customerSearchTimeout = setTimeout(function () {
      fetch('/api/customers?q=' + encodeURIComponent(query) + '&per_page=5')
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

  // Hide suggestions and close search when clicking elsewhere
  document.addEventListener('click', function (e) {
    if (!searchBarExpanded.contains(e.target) && e.target !== searchIconBtn && !searchIconBtn.contains(e.target)) {
      customerSearchSuggestions.classList.remove('active');
    }
  });

  function selectCustomer(customerId) {
    // Fetch customer location and details
    fetch('/api/customers/' + encodeURIComponent(customerId) + '/location')
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (!data.found || !data.customer) {
          alert('Customer not found');
          return;
        }

        selectedCustomerData = data;
        customerSearchInput.value = data.customer.customer_id;
        customerSearchSuggestions.classList.remove('active');

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
        }

        // AUTO-TRIGGER ROUTE FINDING
        findRouteToCustomer(customerId);
      })
      .catch(function (err) {
        console.error('Error fetching customer location:', err);
        alert('Error loading customer location');
      });
  }

  function findNearestPost(lat, lng) {
      customerSearchSuggestions.classList.remove('active');
      customerSearchSuggestions.innerHTML = '<div class="customer-search-item customer-search-loading">📡 Locating nearest post...</div>';
      customerSearchSuggestions.classList.add('active');

      fetch(`/api/posts/nearest?lat=${lat}&lng=${lng}`)
        .then(r => r.json())
        .then(data => {
            customerSearchSuggestions.classList.remove('active');
            if (data.error) {
                showNoticeModal('Not Found', 'No posts found near these coordinates.');
                return;
            }

            // Highlight and zoom
            if (window._selectionIndicatorMarker) {
                map.removeLayer(window._selectionIndicatorMarker);
            }

            window._selectionIndicatorMarker = L.circleMarker([data.lat, data.lng], {
                radius: 25,
                fillColor: '#ef4444',
                color: '#b91c1c',
                weight: 3,
                opacity: 0.8,
                fillOpacity: 0.4,
                className: 'analysis-source-node' // Use existing animation
            }).addTo(map);

            map.setView([data.lat, data.lng], 19);
            
            // Re-fetch full post details to ensure all fields are present
            fetch(`/api/posts/${data.id}`)
              .then(r => r.json())
              .then(fullData => {
                  if (fullData && !fullData.error) {
                      openPostInInspector(fullData);
                  }
              });
        })
        .catch(err => {
            customerSearchSuggestions.classList.remove('active');
            console.error('Nearest post error:', err);
            showNoticeModal('Error', 'Failed to communicate with spatial server.');
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
    if (!custId) {
      console.error('No customer ID provided');
      return;
    }

    if (!navigator.geolocation) {
      console.error('Geolocation is not supported by your browser.');
      return;
    }

    navigator.geolocation.getCurrentPosition(
      function (pos) {
        var lat = pos.coords.latitude;
        var lng = pos.coords.longitude;

        var url = '/api/path?customer_id=' + encodeURIComponent(custId)
          + '&user_lat=' + lat + '&user_lng=' + lng;

        fetch(url)
          .then(function (r) { return r.json(); })
          .then(function (data) {
            if (!data.found) {
              console.warn('No path found for customer ' + custId);
              return;
            }
            drawRoute(data, lat, lng);
          })
          .catch(function (err) {
            console.error('Route finding error:', err);
          });
      },
      function (err) {
        console.error('Geolocation error:', err);
      },
      { enableHighAccuracy: true, timeout: 15000 }
    );
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
      lineJoin: 'round',
      renderer: mainCanvas // Enable Canvas Rendering
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
      '</div>';
  }

  // ── 7. Network Analysis Visualization ──
  function visualizeNetworkAnalysis(type, data, sourceBusId) {
    clearAnalysisHighlights();
    clearAnalysisBtn.style.display = 'flex';

    const visitedBuses = new Set(data.visited_buses || data.downstream_buses || []);
    if (visitedBuses.size === 0) return;

    // 1. Highlight source node
    const sourcePost = busToPostMap[sourceBusId] || poleToPostMap[sourceBusId];
    if (sourcePost && postMarkers[sourcePost.id]) {
        const marker = postMarkers[sourcePost.id];
        if (marker.getElement()) {
            marker.getElement().classList.add('analysis-source-node');
        }
    }

    // 2. Highlight affected poles/transformers
    visitedBuses.forEach(bid => {
        const p = busToPostMap[bid] || poleToPostMap[bid];
        if (p && postMarkers[p.id]) {
            const m = postMarkers[p.id];
            // Create a small highlight circle around affected nodes if they are "secondary"
            // For now, let's just make sure they are visible.
            if (bid !== sourceBusId) {
                const hl = L.circleMarker(m.getLatLng(), {
                    radius: 12,
                    color: type === 'outage' ? '#ef4444' : '#0066ff',
                    weight: 2,
                    opacity: 0.8,
                    fillOpacity: 0.3,
                    className: 'analysis-affected-marker'
                }).addTo(analysisHighlightLayers);
            }
        }
    });

    // 3. Highlight network lines
    networkLinesLayer.eachLayer(layer => {
        if (layer instanceof L.Polyline && layer._allBuses) {
            // If any of the polyline's buses are in the visited set, highlight it
            const isAffected = layer._allBuses.some(bid => visitedBuses.has(bid));
            if (isAffected) {
                const highlightPoly = L.polyline(layer.getLatLngs(), {
                    className: type === 'outage' ? 'analysis-highlight-outage' : 'analysis-highlight-trace',
                    interactive: false,
                    renderer: mainCanvas // Enable Canvas Rendering
                }).addTo(analysisHighlightLayers);
            }
        }
    });

    // 4. Zoom to fit if needed
    const highlightBounds = analysisHighlightLayers.getBounds();
    if (highlightBounds.isValid()) {
        map.fitBounds(highlightBounds, { padding: [50, 50], maxZoom: 18 });
    }
  }

  // Clear active marker and close inspector when clicking on empty map area
  map.on('click', function(e) {
    const layoutEl = document.querySelector('.premium-layout');
    if (layoutEl && layoutEl.classList.contains('inspector-open')) {
      layoutEl.classList.remove('inspector-open');
    }
    if (window._selectionIndicatorMarker) {
      map.removeLayer(window._selectionIndicatorMarker);
      window._selectionIndicatorMarker = null;
    }
  });

});
