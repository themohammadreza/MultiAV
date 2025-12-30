# MultiAV Frontend

Next.js + TypeScript UI using Mantine and TanStack Query. Uploads show inline results under the form, polling stops automatically once a job reaches a terminal state, and the results page shares the same summary layout with engine details and a JSON download action.

## Configuration
- Copy `.env.example` to `.env.local` and adjust API base URL/polling settings.
- For local dev without CORS on the API, leave `NEXT_PUBLIC_API_BASE_URL` empty and set `API_PROXY_TARGET=http://localhost:8000` so Next.js proxies `/api/*` to the backend.
- `NEXT_PUBLIC_UPLOAD_SIZE_LIMIT_MB` (or legacy `NEXT_PUBLIC_UPLOAD_LIMIT_MB`) guards file size for uploads.
- `NEXT_PUBLIC_POLL_INTERVAL_MS` and `NEXT_PUBLIC_POLL_TIMEOUT_MS` control the job polling cadence.
- The history page is backed by server data; client-side upload caching is disabled.
- The UI waits for `/api/v1/health/` before rendering routes and uses `/api/v1/ui/api-key/` to show quota/expiry metadata.

## Scripts
- `npm run dev` – start dev server
- `npm run build` – production build
- `npm run start` – run built app
- `npm run lint` – lint code
- `npm run test` – run unit tests

## Deployment
The provided Dockerfile builds a standalone Next.js image. Inject environment variables at runtime (e.g., via `docker run -e NEXT_PUBLIC_API_BASE_URL=...`). Set `API_PROXY_TARGET=http://app:8000` (or your API host) when you want the container to reverse-proxy `/api/*` to the backend and avoid browser CORS. The UI defaults to `/api/*` proxying in docker-compose.

### Running alongside the backend with Docker Compose
- From the repo root: `docker-compose up --build frontend app worker redis postgres minio clamav windows-defender` (or simply `docker-compose up --build` to start everything).
- Visit http://localhost:3000 for the UI. The frontend proxies `/api/*` to the backend container via `API_PROXY_TARGET`, keeping all requests same-origin.
