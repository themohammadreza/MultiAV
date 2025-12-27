# Frontend Migration Plan

This plan tracks what has already landed in the Next.js UI and what remains for future iterations.

## Stack and Design System (current)
- **Framework**: Next.js with TypeScript
- **UI Library**: Mantine for layout, theming, and components
- **Data Fetching**: TanStack Query with a typed Fetch-based client
- **Forms/Validation**: React Hook Form + Zod
- **Styling/Theming**: Mantine theme for colors/spacing/typography with auto color scheme
- **Tooling**: ESLint, Testing Library, Vitest (unit tests)
- **Build/Deploy**: Dockerized Next.js app with environment-driven API base URL

## Implemented
- **Routes/views**: Upload, status dashboard, results detail, and history pages with a shared layout shell.
- **Authentication**: API key modal stored in browser local storage and surfaced in the header with quota/expiry info from `/api/v1/ui/api-key`.
- **Data flow**: Typed API layer, polling that stops on terminal status, and health gating via `/api/v1/health`.
- **UX**: Inline results under upload, notifications for success/error, and recent-job autocomplete on the status page.
- **History**: Server-backed recent jobs table (no client-side upload cache).

## Remaining / backlog
- **Re-scan flow**: Optional, bounded upload caching and re-scan toggle (not currently exposed).
- **History enhancements**: Filters/pagination and export actions if needed.
- **Testing**: Broader component coverage and e2e for upload → status → results.
- **Resilience**: Error boundaries, retry/backoff polish, and richer empty/error states.
- **Observability**: Logging hooks and documentation for production monitoring.
