# Dashboard Architecture (Phase X)

## Sidebar / routing

Nine top-level sections (`src/lib/nav-config.ts`), each added to `NAV_ITEMS`
only once its real page existed — never a dead link to an unbuilt section:

```
/                Dashboard & Analytics
/conversations   Inbox
/customers       Customer 360
/knowledge       Knowledge Base
/staff           Staff Management
/bookings        Booking Management
/notifications   Notifications
/feedback        Customer Feedback
/settings        Settings (General / Integrations / Audit Logs / System Monitoring tabs)
```

`isActiveNavHref()` matches an href or any of its sub-paths, so e.g.
`/knowledge/[sourceId]/chunks` still highlights "Knowledge Base".

## Auth and route protection

`src/middleware.ts` is the single place every dashboard route's auth check
lives — it replaced a `getServerAccessToken()` + `redirect("/login")` check
that used to be hand-copied into every page. It checks the access-token
cookie's presence (its own `maxAge` already encodes real expiry); if missing
but a refresh-token cookie exists, it silently calls the backend's existing
`/auth/refresh` and sets fresh cookies on the response before continuing —
this avoids bouncing staff back to the login page mid-session.

httpOnly cookies (`art_access_token`/`art_refresh_token`) are set only by
Next.js Route Handlers under `src/app/api/`, never exposed to client JS.
`fetchFromApi()` / `getServerAccessToken()` in `src/lib/server-api.ts` is the
sole pattern for server-to-backend calls from Server Components.

## API proxy layer

Every backend endpoint the dashboard calls has a matching thin Route Handler
under `src/app/api/**` that forwards to `fetchFromApi()` and passes the
upstream JSON body and status straight through. Server Components call
`fetchFromApi()` directly (no round-trip through the proxy); Client
Components call the proxy route with a plain same-origin `fetch()`, since
they cannot hold the httpOnly cookie's underlying token directly.

## Design system

`src/components/ui/` holds the shared primitives introduced in Stage 0
(`Button`, `Card`, `Input`, `EmptyState`, `Skeleton`) so later stages stopped
hand-rolling Tailwind class strings. The brand palette
(`primary`/`accent`/`charcoal`/`ivory`/`sand`) matches the public website's
colors, defined in `tailwind.config.ts`.

## Real-time-ish updates

No WebSocket/SSE infrastructure was introduced — every "live" surface
(Inbox list/thread, notification bell/center) uses short-interval polling
(8s for the Inbox, 15s for notifications) against the existing REST
endpoints, guarded by an in-flight ref so overlapping polls never queue up.
This matches the brief's "use existing polling, no new event infra"
instruction.

## Charts

`recharts` (installed in Stage 9) is the only charting library in the
project. Chart colors are the brand palette's hex values
(`#1E3A2F` primary, `#A3704C` accent) rather than a separate chart palette.
