# MultiAV Frontend

Next.js + TypeScript UI using Mantine and TanStack Query.

## Configuration
- Copy `.env.example` to `.env.local` and adjust API base URL/timeouts.
- For local dev without CORS on the API, leave `NEXT_PUBLIC_API_BASE_URL` empty and set `API_PROXY_TARGET=http://localhost:8000` so Next.js proxies `/api/*` to the backend.
- Feature flags: `NEXT_PUBLIC_FEATURE_HISTORY` controls client-side caching of uploads; `NEXT_PUBLIC_UPLOAD_SIZE_LIMIT_MB` guards file size.

## Scripts
- `npm run dev` – start dev server
- `npm run build` – production build
- `npm run start` – run built app
- `npm run lint` – lint code
- `npm run test` – run unit tests

## Deployment
The provided Dockerfile builds a standalone Next.js image. Inject environment variables at runtime (e.g., via `docker run -e NEXT_PUBLIC_API_BASE_URL=...`). Set `API_PROXY_TARGET=http://app:8000` (or your API host) when you want the container to reverse-proxy `/api/*` to the backend and avoid browser CORS.

### Running alongside the backend with Docker Compose
- From the repo root: `docker-compose up --build frontend app worker redis postgres minio clamav windows-defender` (or simply `docker-compose up --build` to start everything).
- Visit http://localhost:3000 for the UI. The frontend proxies `/api/*` to the backend container via `API_PROXY_TARGET`, keeping all requests same-origin.
