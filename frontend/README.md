# Frontend

This repository contains the frontend application for the project — a Vite + TypeScript + React app using Tailwind CSS and shadcn-ui.

## Local development

Prerequisites:

- Node.js (LTS recommended)
- npm or yarn

Quick start:

```bash
git clone https://github.com/ouemnaa/vectors-in-orbit.git
cd vectors-in-orbit/frontend
npm install
npm run dev
```

Common commands:

- `npm run dev` — start dev server (hot reload)
- `npm run build` — build production assets
- `npm run preview` — locally preview the production build

## Environment & configuration

Place environment variables in a `.env` file in the `frontend/` folder if needed (example: `VITE_API_URL=https://api.example.com`). Do not commit secrets.

## Deployment

This is a standard static frontend that can be deployed to Vercel, Netlify, GitHub Pages, or any static host. Use the build step (`npm run build`) and publish the `dist/` output.

## Tech stack

- Vite
- TypeScript
- React
- Tailwind CSS
- shadcn-ui

## Contributing

- Edit files locally and open a PR.
- Follow repository linting and formatting rules if present.

If you'd like, I can add a minimal `package.json` scripts checklist or CI config for deploying the frontend.
