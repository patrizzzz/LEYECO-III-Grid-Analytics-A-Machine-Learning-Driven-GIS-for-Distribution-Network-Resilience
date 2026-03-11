## Map Manual Test Checklist

### 1. `/api/posts` → Canonical post markers

- **Goal**: Verify posts load, cluster correctly, and respect feeder/phase filters.
- **Steps**:
  - Ensure backend is running (`python app.py`) and visit `http://127.0.0.1:5000/map`.
  - Open DevTools Network tab and reload; confirm a successful `GET /api/posts?in_ph=1&per_page=1000`.
  - Confirm markers appear and cluster when zoomed out (clusters split into individual poles on zoom in).
  - Toggle feeder checkboxes in **Map Settings → Feeder Filter** and verify:
    - Only markers for selected feeders remain visible.
    - Selection is remembered after page refresh (state persisted via `localStorage`).
  - Toggle phase checkboxes in **Phase Filter** and verify network lines update visibility and that phase selections persist after refresh.

### 2. `/api/distribution-lines` & `/api/network-geometry` → Network lines

- **Goal**: Verify network geometry draws correctly and responds to visualization controls.
- **Steps**:
  - In a terminal, hit the endpoints directly:
    - `curl http://127.0.0.1:5000/api/network-geometry`
    - `curl http://127.0.0.1:5000/api/distribution-lines` (if implemented)
  - On the map page, ensure network lines render and that:
    - **Visualization → Line Color** changes recolor lines immediately.
    - **Color by Phasing** toggles between global and phase-based coloring.
    - Feeder filter also hides/shows corresponding line segments.

### 3. Performance / large data sanity

- **Goal**: Ensure UI remains responsive with many markers and long tables.
- **Steps**:
  - Import a larger dataset of posts and lines (via the Resources admin page).
  - Zoom and pan around the map; check that clustering keeps interaction smooth.
  - Open a customer popup with many consumption records and verify:
    - Only the first ~200 rows are rendered.
    - A small notice indicates that the list is truncated for performance.

### 4. Quick regression checks

- **After any map-related change, quickly verify**:
  - Map loads without JS errors.
  - Base layer toggles (Standard / Satellite / Terrain) still work.
  - Non-admin user can still open the map but cannot use admin-only connection editing tools.

