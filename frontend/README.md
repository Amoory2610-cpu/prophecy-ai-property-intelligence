# Prophecy frontend

Next.js 16 app for Prophecy AI. See the repository [README](../README.md) for setup, and
[docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md) for how it talks to the API.

```bash
npm ci
npm run dev          # http://localhost:3000, proxies /api to API_ORIGIN (default http://localhost:8000)
npm test             # unit tests (Vitest)
npx playwright test  # end-to-end tests against a running stack (BASE_URL)
```
