# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

WallSense is a cinematic, scroll-driven frontend for a through-wall human detection and tracking system. This is an immersive product interface — not a marketing site. The experience communicates sensing through walls, human tracking, intelligent signal processing, and futuristic system visualization.

## Commands

```bash
npm run dev      # Start dev server (localhost:3000)
npm run build    # Production build
npm run start    # Serve production build
npm run lint     # ESLint
```

## Tech Stack

- **Next.js 16** (App Router) with TypeScript (strict mode)
- **Tailwind CSS v4** (uses `@import "tailwindcss"` syntax, `@theme inline` for tokens)
- **Framer Motion** for scroll-driven animations (`useScroll`, `useTransform`)
- **Spline** (`@splinetool/react-spline`) for 3D scenes — must be lazy-loaded
- Glassmorphism design system throughout

## Architecture

```
src/
  app/              # Next.js App Router (layout.tsx, page.tsx, globals.css)
  components/
    ui/             # All UI components (shadcn structure)
      spline.tsx    # 3D scene wrappers
      tracking-overlay.tsx  # Pose estimation overlays
  lib/
    scroll/         # Scroll-based animation hooks and utilities
```

**Path alias:** `@/*` maps to `./src/*`

### Scroll Experience Sections (in order)

1. **Brick Wall Intro** — Fullscreen brick wall, "WallSense" embedded in wall, dark monochrome. On scroll: text evaporates, wall dissolves with parallax.
2. **Human/Robot Reveal** — Skeletal tracking overlay (MediaPipe-style) on a human figure. Glowing pose estimation lines. Short scroll height. Subtle cursor reactivity. System-style copy only (e.g., "INITIALIZING", "SCANNING SIGNALS").
3. **Hacker Text** — Scroll-controlled text scramble. Characters morph into final words tied to scroll position. Reverses on scroll-up. No auto-play. Sequence: SCANNING → SIGNAL ACQUIRED → THROUGH-WALL DETECTION → HUMAN TRACKING ACTIVE.

Page ends after Section 3. No content beyond this yet.

## Design Rules

**Glassmorphism required on all panels:**
- `backdrop-blur`, semi-transparent backgrounds, subtle borders, soft gradients, layered depth
- No flat UI blocks

**Typography:** Futuristic fonts only — Geist (already configured), Space Grotesk, Satoshi, Orbitron (headlines only). Headings must feel sharp and premium.

**Motion:** All animations must be scroll-driven via Framer Motion. Smooth easing, GPU-accelerated. No janky transitions, no auto-play animations.

**Aesthetic:** Futuristic, minimal, premium, smooth, glassy, cinematic. No generic templates, default fonts, or marketing fluff.

## Code Conventions

- Strict TypeScript — no `any` types
- All UI components go in `src/components/ui/` (shadcn structure)
- Scroll logic lives in `src/lib/scroll/`
- No `console.log` in production code
- No hardcoded magic numbers — extract to constants
- Lazy-load Spline scenes, optimize scroll listeners, avoid layout thrashing
- Keep animations GPU-accelerated (`transform`, `opacity` — avoid animating `width`, `height`, `top`, `left`)

## What Not To Do

- No generic hero sections or marketing copy
- No default Tailwind typography
- No basic fade-only animations
- No content after Section 3 (future phases: live dashboard, signal viz, system state panels — not yet)
- Do not regress animation smoothness or cinematic feel when making changes
