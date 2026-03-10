# API Reference Documentation

This document provides a summary of the available REST API endpoints for the Leyeco Electrical Post Mapping System.

Base URL paths are prefixed with `/api`.

## Authentication

Authentication is handled via session cookies. Some endpoints require the user to be logged in, while data-modifying endpoints typically require the `Admin` role.

The UI authenticates users via the `/auth` blueprint:
* `POST /login`: Authenticates either admin (using `username` and `password`) or viewer (using `username` and `access_code`).
* `GET /auth/whoami`: Returns details about the currently authenticated user session.
* `GET /auth/logout`: Clears the current session.

---

## Posts (Poles)

### `GET /api/posts`
Fetches a paginated list of electrical posts.
- **Parameters**: 
  - `page` (int): Page number (default: 1)
  - `per_page` (int): Items per page (default: 10)
  - `in_ph` (boolean): Optionally filter posts constrained within Philippine lat/lng bounds.
- **Returns**: A JSON object containing a `data` array and `pagination` details.

### `POST /api/posts`
**Admin Only**. Creates a single new post.
- **Payload**: `{ "name": "...", "lat": 14.5, "lng": 121.0, "status": "Active" }`
- **Returns**: The created post object.

### `GET /api/posts/<post_id>`
Fetches detailed info for a specific post, including its meter readings.

### `PUT /api/posts/<post_id>`
**Admin Only**. Updates post attributes (like lat, lng, status).

### `DELETE /api/posts/<post_id>`
**Admin Only**. Permanently deletes a post by ID.

### `GET /api/posts/<post_id>/connections`
Fetches all Primary and Secondary lines physically connected to this post.

### `GET /api/posts/<post_id>/service-drops`
Fetches downstream secondary service drops (customers) traced to this specific post.

---

## Bulk Imports (Admin Only)

The following endpoints expect a `multipart/form-data` POST request holding a CSV/Excel file in the `file` attribute. They return parsing statistics and validation messages.

* `POST /api/posts/bulk-import`: Imports basic Post data.
* `POST /api/primary-lines/bulk-import`: Imports Primary Distribution Line Segments.
* `POST /api/secondary-lines/bulk-import`: Imports Secondary Line Segments.
* `POST /api/bus-nodes/bulk-import`: Imports Bus Nodes.
* `POST /api/transformers/bulk-import`: Imports Distribution Transformers.
* `POST /api/secondary-service-drops/bulk-import`: Imports Customer Service Drops.

---

## Network Tracing & Lines

### `GET /api/distribution-lines`
Fetches a paginated list of all primary distribution lines.

### `GET /api/secondary-lines`
Fetches a list of all secondary line segments.

### `GET /api/primary-lines/by-bus/<bus_id>`
Returns primary distribution lines connected directly to the specific `bus_id`.

### `GET /api/secondary-lines/by-bus/<bus_id>`
Returns secondary lines connected directly to the specific `bus_id`.

### `GET /api/transformers/by-bus/<bus_id>`
Locates distribution transformers mounted at or near a specific `bus_id`.

### `GET /api/secondary-service-drops/by-bus/<bus_id>`
Returns consumer service drops traced specifically from this `bus_id`.

### `GET /api/network-geometry`
Generates a full GeoJSON representation of the electrical network graph suitable for Mapbox/Leaflet visualization. Enriches the data with Grid Health Analytics (Load Stress & ML Failure Risk).

---

## User Management (Admin Only)

### `GET /api/users`
Lists all users in the system.

### `POST /api/users`
Creates a new Viewer-level user. A unique, secure `access_code` is auto-generated and returned to the admin, who then shares it with the viewer.
- **Payload**: `{ "display_name": "Field Technician Alpha" }`

### `DELETE /api/users/<user_id>`
Deletes a user. Admins cannot delete other Admins via API.

---

## System / Maintenance

### `POST /api/data/delete-all`
**Admin Only**. Permanently flushes all network infrastructure data from the database, effectively resetting the application to an empty state. Also resets auto-increment IDs on MySQL.

### `GET /api/data/upload-history`
Returns logs of past successful CSV imports/uploads.
