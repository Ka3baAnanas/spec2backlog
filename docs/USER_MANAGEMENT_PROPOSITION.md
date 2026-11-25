# User Management Architecture Proposition — SpecToBacklog Platform

**Author:** Youssef AMAYED
**Status:** Proposition for review
**Scope:** SpecToBacklog platform

## 1. Context and Problem Statement

SpecToBacklog currently lets any caller upload a specification, build context, generate a backlog, review it, and export it. That is acceptable for a local prototype but not for a platform used by teams: there is no notion of who a user is, which projects they may see, or what actions they may perform.

The platform needs a user management layer that:

- identifies users through the organization identity provider;
- groups users into workspaces that own projects;
- gives different people different levels of access;
- keeps project data isolated between teams and clients;
- records security-relevant actions for audit;
- supports both self-service collaboration and platform administration.

This document proposes an architecture, not an implementation. It is intended to drive a decision before backend and frontend work starts.

## 2. Goals and Non-Goals

### Goals

- **Single identity source:** use EY SSO (OIDC/OAuth2) as the source of truth for employees.
- **Team ownership:** introduce workspaces as the tenant boundary; every project belongs to exactly one workspace.
- **Least-privilege access:** role-based access control at workspace and project levels.
- **Safe collaboration:** invite/remove members, revoke access immediately, and expire sessions.
- **Auditable platform:** record login, invite, role change, project access change, and admin actions.
- **Low-friction adoption:** migrate existing projects into a default workspace without regenerating any backlog.

### Non-Goals

- Building a custom password-based identity system for production.
- Billing, subscription management, or quotas.
- Fine-grained per-field permissions in the first release.
- Full Story/Discussion collaboration features beyond access control.
- Replacing document section `role` (`requirement`, `context`, etc.) — that is a domain concept, not a user role.

## 3. Current Platform Baseline

The current stack is well suited to incremental hardening:

- Backend: FastAPI, Pydantic v2, SQLAlchemy 2, PostgreSQL.
- Async generation: Celery with Redis.
- Frontend: React 18, Vite, TypeScript, React Router 6, TanStack Query.
- Deployment: Docker Compose with `db`, `redis`, `chroma`, `backend`, `celery-worker`, and `frontend`.
- Domain data: almost every table is scoped by `project_id`; `Project` itself has no owner, tenant, or creator field.
- Auth state: none. Endpoints depend only on `get_db`; the API client sends no token; `/admin/*` currently redirects to `/`.
- Architecture docs already list “auth (EY SSO)” as roadmap work.

Important consequence: authorization can be introduced by adding a tenant boundary above `Project` and a common dependency in front of existing routers, without rewriting the generation pipeline.

## 4. Target User Management Architecture

**Recommended direction:** workspace-based RBAC with OIDC login through EY SSO, opaque/rotating refresh sessions in an HttpOnly cookie, short-lived access tokens held in memory on the frontend, and application-level tenant scoping enforced by a central FastAPI dependency layer.

```text
Browser ──OIDC──> EY SSO
   │                 │
   │ access token    │ id token
   ▼                 ▼
SpecToBacklog API ── verifies token, resolves User
   │
   ├─ CurrentUser dependency
   ├─ WorkspaceMembership dependency
   ├─ Permission dependency
   └─ Workspace-scoped Project loader
        │
        └─ existing project/document/backlog routers
```

### 4.1 Identity Model: Users, Workspaces, and Memberships

- **User**: a person authenticated by EY SSO. Unique key is the SSO `sub` claim; email is mutable and synced from the IdP.
- **Workspace**: the tenant. It owns projects, invitations, and role assignments. Examples: `EY — Team A`, `Client X`, `Internal Demo`.
- **Membership**: the join between a user and a workspace with a workspace role and status (`active`, `invited`, `suspended`).
- **Project membership override**: optional. Needed only when a user should have project-level access different from their workspace default (for example, a workspace `Viewer` who owns one project).
- **Invitation**: an email-based, expiring, single-use token that grants a workspace role when accepted.

Every project gets `workspace_id`. All child tables remain linked through `project_id`, so isolation is enforced when the project is loaded through the workspace-scoped dependency.

### 4.2 Authentication

Use EY SSO through OIDC Authorization Code + PKCE.

- Backend endpoints:
  - `/api/v1/auth/login-url` returns the IdP authorization URL and state.
  - `/api/v1/auth/callback` validates state, exchanges the code, verifies the ID token, upserts the user, and issues platform tokens.
- Frontend starts the redirect, stores no secrets, and exchanges nothing directly with the IdP.
- Local development may use an explicit `AUTH_PROVIDER=dev` mode with a seeded local user. It must be disabled by default in deployed environments.
- Provider configuration comes from `Settings`/`.env`: `AUTH_PROVIDER`, `OIDC_ISSUER`, `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET`, `OIDC_AUDIENCE`, `OIDC_REDIRECT_URI`, cookie and session lifetimes.

### 4.3 Authorization and Roles

Two layers are combined:

1. **Platform role**: `platform_admin` for global administration. All other users are `platform_user`.
2. **Workspace role**: `owner`, `admin`, `member`, `reviewer`, `viewer`.

Proposed permission matrix:

| Action | Owner | Admin | Member | Reviewer | Viewer | Platform admin |
|---|---:|---:|---:|---:|---:|---:|
| View workspace projects | Yes | Yes | Yes | Yes | Yes | Yes |
| Create/delete project | Yes | Yes | Yes | No | No | Yes |
| Upload/restructure document | Yes | Yes | Yes | No | No | Yes |
| Approve context / generate | Yes | Yes | Yes | No | No | Yes |
| Review/accept backlog items | Yes | Yes | Yes | Yes | No | Yes |
| Export backlog | Yes | Yes | Yes | Yes | Yes | Yes |
| Invite/manage members | Yes | Yes | No | No | No | Yes |
| Change workspace settings | Yes | Yes | No | No | No | Yes |
| Suspend users / view audit log | No | No | No | No | No | Yes |

`member` is the default for invited contributors. `reviewer` exists for business analysts who validate output without changing the pipeline. `viewer` is for read-only stakeholders.

Authorization is expressed as named permissions (`project.create`, `generation.run`, `backlog.review`, `workspace.member.manage`, etc.) and evaluated by a `require_permission(...)` dependency rather than scattered role checks.

### 4.4 Session, Token, and Credential Lifecycle

- **Access token**: short-lived JWT (15 minutes) containing `sub`, `workspace roles`, `platform role`, and `permissions` snapshot. Kept in frontend memory only.
- **Refresh token**: long-lived opaque random token stored hashed in the database, delivered as `Secure`, `HttpOnly`, `SameSite=Lax` cookie.
- **Rotation**: every refresh rotates the token and invalidates the previous one. Reuse detection revokes the family.
- **Logout**: deletes the refresh token server-side and clears the cookie.
- **Role changes**: increment a `token_version` on the user / membership so existing access tokens become stale at the next request.
- **Suspended users**: blocked at token validation time, not only at login.

No token is persisted in `localStorage`. This reduces XSS exposure and matches the existing simple API-client structure.

### 4.5 Multi-Tenancy and Data Isolation

- `Project.workspace_id` is required and indexed.
- A single dependency resolves `workspace_id` from the current user's active workspace and loads the project only if the user is an active member with the required permission.
- Celery jobs receive `project_id`, `workspace_id`, and `actor_user_id`. The worker re-checks that the project still belongs to the workspace before generation.
- SSE/event streams are filtered by workspace membership; no raw event stream is public.
- Export endpoints reuse the same project loader so a viewer cannot export a project from another workspace.

Application-level scoping is the first release. PostgreSQL Row-Level Security can be added later as defense in depth once Alembic migrations are in place.

### 4.6 Auditability and Security Events

Introduce a dedicated `AuditLog` table rather than overloading `RunEvent`.

Recorded events:

- `auth.login`, `auth.logout`, `auth.refresh_reuse_detected`;
- `user.upserted`, `user.suspended`, `user.role_changed`;
- `workspace.created`, `workspace.member_invited`, `workspace.member_removed`;
- `project.created`, `project.deleted`, `project.transferred`;
- `permission.denied` for sensitive operations.

Each audit row stores actor user ID, workspace ID when applicable, action, target type/id, IP/user agent, and timestamp. Generation progress stays in `RunEvent`; review decisions stay in `ReviewEvent`, but both gain an `actor_user_id` when available.

### 4.7 Self-Service and Admin Flows

- **Login**: user clicks “Sign in with EY”, completes SSO, lands on `/`.
- **Workspace switcher**: if the user belongs to more than one workspace, the header shows a switcher that sets the active workspace in a cookie and refetches queries.
- **Invite**: owner/admin enters an email and role; an expiring invitation is created and emailed.
- **Accept invite**: the invited user logs in through SSO and is added to the workspace.
- **Manage members**: owner/admin can change roles, suspend, or remove members. The last owner of a workspace cannot be removed.
- **Platform admin**: global user search, workspace list, suspension, and audit log. Platform admins do not automatically see project content unless they are also workspace members; the proposal keeps explicit membership for data access.

## 5. Proposed Data Model

| Table | Key fields | Notes |
|---|---|---|
| `users` | `id`, `sso_sub`, `email`, `display_name`, `platform_role`, `status`, `token_version`, `last_login_at` | Unique `sso_sub`; email unique when present. |
| `workspaces` | `id`, `name`, `slug`, `status`, `created_by_user_id`, `created_at` | Tenant boundary. |
| `workspace_memberships` | `id`, `workspace_id`, `user_id`, `role`, `status`, `invited_by_user_id` | Unique `(workspace_id, user_id)`. |
| `invitations` | `id`, `workspace_id`, `email`, `role`, `token_hash`, `expires_at`, `accepted_at`, `invited_by_user_id` | Token is stored hashed only. |
| `refresh_tokens` | `id`, `user_id`, `token_hash`, `family_id`, `expires_at`, `revoked_at`, `replaced_by_id` | Rotating opaque sessions. |
| `audit_logs` | `id`, `actor_user_id`, `workspace_id`, `action`, `target_type`, `target_id`, `metadata_json`, `ip`, `user_agent`, `created_at` | Append-only. |
| `projects` | existing fields **+** `workspace_id`, `created_by_user_id` | Existing rows are backfilled during migration. |
| `review_events` | existing fields **+** `actor_user_id` | Replaces free-text `by` over time. |
| `run_events` | existing fields **+** `actor_user_id` | Useful for “who triggered generation”. |

Indexes to add: `users.sso_sub`, `workspace_memberships(user_id, status)`, `workspace_memberships(workspace_id, role)`, `projects(workspace_id)`, `audit_logs(workspace_id, created_at)`, `refresh_tokens(token_hash)`.

No new domain tables are needed for projects, documents, sections, backlog items, or traces: they remain project-scoped.

## 6. Proposed API Surface

### Authentication and identity

- `GET /api/v1/auth/login-url`
- `GET /api/v1/auth/callback`
- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/logout`
- `GET /api/v1/auth/me` → user, platform role, memberships, active workspace, permissions

### Workspaces and members

- `GET /api/v1/workspaces` → workspaces for current user
- `POST /api/v1/workspaces` → owner-only creation
- `GET /api/v1/workspaces/{workspace_id}/members`
- `POST /api/v1/workspaces/{workspace_id}/invitations`
- `POST /api/v1/workspaces/{workspace_id}/invitations/{id}/resend`
- `PATCH /api/v1/workspaces/{workspace_id}/members/{user_id}` → role/status change
- `DELETE /api/v1/workspaces/{workspace_id}/members/{user_id}`
- `POST /api/v1/auth/invitations/{token}/accept`

### Platform admin

- `GET /api/v1/admin/users`
- `PATCH /api/v1/admin/users/{id}` → suspend / platform role
- `GET /api/v1/admin/workspaces`
- `GET /api/v1/admin/audit-logs`

### Existing routers

All current `/api/v1/*` routers except health and auth callbacks are placed behind the auth dependency. Handlers receive `current_user` and an already-authorized `project` object; they do not re-implement permission checks.

## 7. Integration with Existing SpecToBacklog Modules

- **Backend core**: add `app/modules/identity/` and `app/api/v1/auth.py`, `workspaces.py`, `admin.py`. Keep `Settings` as the single configuration object and extend `config.py`/`.env.example`.
- **Database**: introduce Alembic migrations. The current `create_all()` startup path and SQLite schema guard can remain for local demo, but production must use migrations.
- **Project flows**: `generate`, `retry-failed`, `recover`, export, and review endpoints use the same `WorkspaceProject` dependency.
- **Events/SSE**: `emit()` gains an optional `actor_user_id`; event rows are filtered by workspace when streamed.
- **Celery**: task arguments gain workspace/actor context; worker validates workspace membership before running `run_generation`.
- **Frontend**: add `AuthProvider`, `ProtectedRoute`, workspace switcher in `Header`, user menu, invite/manage member pages, and an admin area. TanStack Query keys include active workspace, e.g. `["projects", workspaceId]`.
- **API client**: attach the in-memory access token through a request interceptor and handle `401` by attempting one refresh before retrying.
- **Tests**: extend `conftest.py` with a seeded test user/workspace; add RBAC tests that assert denied routes return `403`, cross-workspace project access returns `404`, and invitations expire.

## 8. Migration and Rollout Plan

1. **Phase 0 — Decision**: confirm IdP, workspace naming, default roles, and whether external/client users are allowed.
2. **Phase 1 — Schema and migrations**: add identity tables, `projects.workspace_id`, indexes, and Alembic baseline. Create one `Default Workspace` and assign all existing projects to it.
3. **Phase 2 — Backend auth plumbing**: OIDC verification, dependencies, permission registry, and `401/403` semantics. Keep a temporary feature flag to disable enforcement in local dev only.
4. **Phase 3 — Workspace APIs and UI**: workspace switcher, member list, invite flow, role management.
5. **Phase 4 — Protect domain routes**: apply scoping to projects, pipeline, events, backlog, export, and assistant. Add audit events.
6. **Phase 5 — Admin and hardening**: global admin pages, audit filtering, token reuse detection, rate limits on login/refresh/invite endpoints.
7. **Phase 6 — Cleanup**: remove the free-text `ReviewEvent.by` after backfill, require workspace IDs in all fixtures, and enable RLS if chosen.

Rollout is backward-compatible for data: no generated backlog is deleted or regenerated. Users sign in once after Phase 4; existing browser sessions from before auth are invalidated by design.

## 9. Risks, Trade-offs, and Open Questions

### Risks and trade-offs

- **SSO dependency**: if EY SSO is unavailable, new logins fail. Mitigation: short access tokens, refresh sessions, and a clearly isolated dev-only auth mode.
- **Application-level isolation**: simpler to ship, but a missed dependency could leak data. Mitigation: central project loader plus tests for every router; RLS later.
- **Token complexity**: rotating refresh tokens are more work than plain JWTs but reduce long-lived token theft.
- **Audit growth**: high-volume events need retention rules and partitioning later.
- **Invitation emails**: requires an email provider or internal mail relay; without one, invites can be created but not delivered.
- **Admin access**: global admins can manage users but cannot read project content unless members. This avoids implicit data access but can slow support work.

### Open questions

1. Is EY SSO the only IdP, or do clientOrganization accounts need separate identities?
2. Should a user be able to belong to multiple workspaces simultaneously, or switch tenants explicitly?
3. Who is allowed to create a workspace: any authenticated user or platform admin only?
4. What is the retention period for audit logs and refresh tokens?
5. Should `platform_admin` be able to impersonate a member for support, with an audit record?
6. Are exports allowed for `viewer`, or only for `reviewer` and above?

## 10. Acceptance Criteria

- A user cannot call any project, pipeline, backlog, event, or export endpoint without a valid access token: expected `401`.
- A workspace member cannot read a project from another workspace: expected `404` (not `403`, to avoid leaking existence).
- A `viewer` can read and export but cannot generate, review, invite, or change roles.
- A `reviewer` can review backlog items but cannot change document structure or run generation.
- A `member` can generate but cannot invite or remove members.
- Owners/admins can invite, change roles, and remove members; the last owner cannot be removed.
- Revoking/suspending a user blocks refresh and subsequent API calls within one access-token lifetime.
- Refresh-token reuse revokes the token family and emits `auth.refresh_reuse_detected`.
- All admin and membership changes appear in the audit log with actor and timestamp.
- Existing projects and generated backlogs remain available after migration in `Default Workspace`.
- Backend tests, ruff, frontend typecheck/build, and an OIDC integration smoke test pass.

## 11. Decision Summary

Adopt **OIDC via EY SSO + workspace-based RBAC + application-level tenant scoping + rotating refresh sessions + audit log** as the target user management architecture for SpecToBacklog.

This keeps the current generation and backlog engine unchanged, adds a tenant boundary above `Project`, and gives the platform a clear path from prototype to team-safe production use. The main prerequisite before implementation is confirming the IdP details and the workspace ownership rules in Section 9.
