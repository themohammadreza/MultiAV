# MultiAV Frontend

Next.js + TypeScript UI using Mantine and TanStack Query.

## Configuration
- Copy `.env.example` to `.env.local` and adjust API base URL/timeouts.
- Feature flags: `NEXT_PUBLIC_FEATURE_HISTORY` controls client-side caching of uploads; `NEXT_PUBLIC_UPLOAD_SIZE_LIMIT_MB` guards file size.

## Scripts
- `npm run dev` – start dev server
- `npm run build` – production build
- `npm run start` – run built app
- `npm run lint` – lint code
- `npm run test` – run unit tests

## Deployment
The provided Dockerfile builds a standalone Next.js image. Inject environment variables at runtime (e.g., via `docker run -e NEXT_PUBLIC_API_BASE_URL=...`).
