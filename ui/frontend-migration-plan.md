# Frontend Migration Plan

This plan outlines the tasks required to migrate the existing Streamlit UI to a scalable React/TypeScript application using Next.js, Mantine, and TanStack Query.

## Stack and Design System
- **Framework**: Next.js with TypeScript
- **UI Library**: Mantine for layout, theming, and components
- **Data Fetching**: TanStack Query with axios-based client
- **Forms/Validation**: React Hook Form + Zod
- **Styling/Theming**: Mantine theme for colors/spacing/typography; include dark/light mode support
- **Tooling**: ESLint, Prettier, Testing Library, Vitest/Playwright for tests
- **Build/Deploy**: Dockerized Next.js app with environment-driven API base URL

## Task Breakdown
1. **Define UI requirements and flows**
   - Map flows for upload, live status, results, history, and re-scan to routes/views.
   - Lock design tokens (colors, spacing, typography) and Mantine theme configuration.
   - Produce route/view map and component hierarchy diagram.

2. **Scaffold the application**
   - Initialize Next.js (TypeScript) with ESLint/Prettier and Testing Library.
   - Add TanStack Query provider, axios client, and typed API layer for MultiAV endpoints.
   - Configure absolute imports and base layout shell.

3. **Configuration and authentication**
   - Read API base URL, timeouts, and feature toggles from environment variables.
   - Add optional auth hook if backend supports tokens; ensure safe handling in server/client components.

4. **Core views**
   - **Upload page**: file selection, size/type limits, submission state, re-upload toggle.
   - **Status page**: live polling for active jobs with progress indicators.
   - **Results page**: verdict/engine tables with filtering and inline preview.
   - **History page**: filters, pagination, and re-scan action.
   - **Shared layout**: navigation, breadcrumbs, and responsive shell.

5. **Data fetching and validation**
   - Wire TanStack Query with polling/backoff for non-terminal jobs (done; polling now stops on terminal statuses and ignores window focus).
   - Use React Hook Form + Zod for upload validation and form states.

6. **UX enhancements**
   - Toasters for success/error, disabled states during uploads, skeletons/spinners, and inline result preview (upload page now renders live results below the form; signatures are flattened and labeled).

7. **Re-scan flow**
   - Cache upload history (bounded) and support opt-in/out semantics for re-scan submissions.

8. **Testing**
   - Component tests for forms and tables.
   - Integration/e2e for upload → status → results flow and re-scan.

9. **Performance and resilience**
   - File-size/type guards, debounced polling intervals, error boundaries, retries/backoff, and graceful fallbacks.

10. **Build, deploy, and observability**
    - Production Dockerfile or static export pipeline with env-injected API base.
    - Add basic logging/monitoring hooks and document setup/run steps.

## Execution Guidance
Tasks can be tackled sequentially for clarity (especially requirements → scaffold → views), but after scaffolding the app you can parallelize feature-specific tasks (e.g., core views, UX polish, testing) provided shared contracts (API layer, theme tokens) are stable.
