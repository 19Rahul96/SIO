---
description: "Use when working in frontend React, Zustand store, page flow, styling, or API integration code under frontend/src."
applyTo: "frontend/src/**/*.{js,jsx}"
---

# Frontend Working Rules

- Keep backend calls centralized in [frontend/src/services/api.js](../frontend/src/services/api.js). Do not scatter `fetch` calls across pages or components.
- Keep app-level workflow and async state transitions in [frontend/src/store/index.js](../frontend/src/store/index.js); page components should stay focused on presentation and user interaction.
- When changing API connectivity, update [frontend/src/services/api.js](../frontend/src/services/api.js) and [frontend/vite.config.js](../frontend/vite.config.js) together when needed. The client defaults to `VITE_API_URL` or `http://localhost:8000`, while Vite only proxies `/api` paths.
- Preserve the existing step-flow structure rooted in [frontend/src/App.jsx](../frontend/src/App.jsx) unless the user asks for a navigation redesign.
- Validate frontend changes with `npm run dev` from `frontend/`, and use `npm run build` for build-sensitive changes. There are no repo-defined frontend test or lint scripts.