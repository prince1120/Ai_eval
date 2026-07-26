# EvalPulse - Call Evaluation & Audio Analysis Frontend Web App

A modern, responsive Next.js 16 (Turbopack) web application for audio call transcriptions, real-time multi-step progress tracking, generic speaker dialogue chat view, custom scorecard template configurations, and CSV/JSON report exports.

---

## 🛠️ Technology Stack

- **Framework**: [Next.js 16](https://nextjs.org/) (App Router, Turbopack)
- **Styling**: TailwindCSS + Lucide Icons + Custom CSS Keyframe Animations
- **State & Data Fetching**: TanStack React Query (`@tanstack/react-query`)
- **Authentication**: JWT Cookie-based Authentication Context (`auth-context.tsx`)
- **Modal Architecture**: Portal-based edge-to-edge modals (`React.createPortal`)
- **Language**: TypeScript

---

## ✨ Key Frontend Features

1. **Real-Time Audio Processing Modal**:
   - Multi-step live timer progress (Uploading -> Speech-to-Text -> Diarization & Evaluation).
   - Dynamic step descriptions sensitive to the "Auto-analyze" checkbox state.

2. **Full-Viewport Portal Modals**:
   - Portal rendering directly on `document.body` eliminating CSS transform trapping.
   - 100% full-screen dark backdrop overlay (`bg-slate-950/80`) across all devices and screen sizes.

3. **Dialogue Chat vs Raw Text View**:
   - Dual view switcher on transcript detail pages:
     - **Dialogue Chat**: Clean speaker bubbles for `Agent / Support Rep` vs `Customer / Caller`.
     - **Raw Original Text**: Untouched, exact original transcription text.
   - AI Speaker Separation Notice disclaimer banner for clear user expectation setting.

4. **Multi-Selection & Bulk Actions**:
   - Select multiple call transcripts with bulk export to CSV Excel reports.
   - **Bulk Delete**: Delete selected transcripts in 1 click with a portal confirmation modal.

5. **Robust Date Filtering & Timezone Conversion**:
   - **Today Filter**: Matches any call uploaded within the past 24 hours (`diffHours <= 24`) or local calendar date.
   - **UTC to Region Conversion**: `formatToUserLocalTime` utility automatically parses backend UTC timestamps and renders local time based on the user's browser timezone.

---

## 🚀 Getting Started

### 1. Install Dependencies

```bash
npm install
```

### 2. Run Development Server

```bash
npm run dev
```

Open [http://localhost:3001](http://localhost:3001) in your browser.

### 3. Production Build

To test production build compilation:

```bash
npm run build
npm run start
```

---

## 📁 Directory Structure

```
frontend/
├── app/
│   ├── (auth)/          # Login & Registration Pages
│   ├── (dashboard)/     # Authenticated App Routes
│   │   ├── dashboard/   # Executive Analytics Overview
│   │   ├── templates/   # Scorecard Template Builder
│   │   ├── transcripts/ # Transcripts List, Bulk Actions & Detail Views
│   │   └── analysis-runs/ # Scorecard Parameter Breakdown Reports
│   ├── globals.css      # Design System Tokens & Animation Keyframes
│   └── layout.tsx       # Root Layout & Query Provider
├── components/          # Reusable UI Components (Navbar, Modal, DynamicResultsList)
├── lib/                 # Utilities (api.ts, auth-context.tsx, date-utils.ts, export-utils.ts)
├── package.json         # Package Manifest
└── README.md            # Frontend Documentation
```
