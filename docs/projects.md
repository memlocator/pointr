# Projects and ACLs

This document describes how projects and access control work for Pointr data sources, custom POIs, and custom areas.

## Overview

- Every stored entity belongs to a **project**.
- A project has an **allow list** of members (no deny list).
- By default, each user gets a private project named after their username.
- Data sources (uploaded GeoJSON) are project-scoped unless explicitly marked global later.

## Technical Model (ACLs)

**Storage**

- `projects`: `id (uuid)`, `name`, `created_by`, `default_acl_mode` (`NONE` or `ALL`)
- `project_members`: `(project_id, username, role)` with `role` = `owner`, `admin`, or `member`
- Project-scoped tables include a `project_id` column:
  - `custom_pois`
  - `custom_areas`
  - `uploaded_sources`
  - `uploaded_pois`

**ACL behavior**

- ACLs are **allow-only**. There are no deny lists.
- `default_acl_mode` currently uses:
  - `NONE` (default): only members can access
  - `ALL`: reserved for future global sharing (not enabled yet)
- Effective access rule: a request is authorized if the user is present in
  `project_members` for that `project_id`.

**Request resolution**

- The backend derives a default project by calling `EnsureUserProject(username)` on every request.
- The frontend persists the active project in `localStorage` and sends it as `project_id`.
- The backend validates overrides via `CheckProjectAccess(user, project_id)` before using it.

**Ownership**

- `owner` and `admin` can add/remove members. Only `owner` can delete a project.
- Only one `owner` exists per project. Owners can transfer ownership.
- Owners cannot leave until ownership is transferred. Admins/members can leave.

**Deletion**

- Deleting a project removes all project-scoped data:
  - `custom_pois`, `custom_areas`, `uploaded_sources`, `uploaded_pois`
  - and all `project_members` rows for the project.

## Rules

1. **Project required**  
   `custom_pois`, `custom_areas`, and uploaded sources must all have a `project_id`.

2. **Default project = username**  
   On first request from `X-User`, the backend ensures a project named after the user exists and adds them as `owner`.

3. **No deny lists**  
   Access is controlled only by membership in `project_members`.

4. **Default privacy**  
   New projects are private: only their members can read/write.

## Managing Projects (UI)

- **Create**: Open the project dropdown (left of `?`) and click **Create new project**.  
  You can optionally add members during creation (comma/newline separated list).

- **Edit members**: Click the ✎ icon next to a project (owners only).  
  Add or remove members in the modal. Owners cannot be removed.

- **Delete**: Click the ✕ icon next to a project (owners only), then confirm.  
  Deleting a project removes all its project-scoped data (custom POIs, custom areas, uploaded sources).

## Access Model (Read)

- A user can read a project if they are listed in `project_members` for that project.
- Requests that do not specify a project use the user’s default project (their username).
- The UI stores the active project ID in `localStorage` and sends it as `project_id`
  (query param for GET, JSON field for POST/PATCH).

## Data Sources

- Uploaded GeoJSON sources are tied to a project.
- When enriching, the backend only queries sources that belong to the user’s project.

## Dev Impersonation

In dev mode only, you can impersonate another user via a header (e.g. `X-Dev-Impersonate`). This is intended for local testing.

Example:

```bash
curl -H "X-User: local-dev" \
     -H "X-Dev-Impersonate: alice" \
     http://localhost:8000/api/projects
```

## API Summary

- `GET /api/projects` — list projects for the current user.
- `POST /api/projects` — create a project (owner = current user).
- `DELETE /api/projects/{project_id}` — delete a project (owner only).
- `GET /api/projects/{project_id}/members` — list members (project members only).
- `POST /api/projects/{project_id}/members` — add members (`role`: `member`/`admin`; admin+owner only).
- `DELETE /api/projects/{project_id}/members/{username}` — remove member (admin+owner only; owner cannot be removed; members can remove themselves).
- `POST /api/projects/{project_id}/owner` — transfer ownership (single owner).

---

If you need shared projects later, add additional rows to `project_members` for the same project.
