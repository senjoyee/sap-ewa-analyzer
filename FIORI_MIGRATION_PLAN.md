# EWA Analyzer – Frontend Migration Plan to Full SAP Fiori (SAPUI5)

> **Goal:** Replace the current React + Fluent UI frontend with a full SAPUI5/Fiori app that can run standalone (e.g., on Azure Web App) and later be deployed to SAP BTP (SAP Build Work Zone / Launchpad) without another rewrite.

This document focuses **only** on the frontend. Backend APIs and data structures remain as they are.

---

## 0. Scope, Assumptions, and Constraints

- **Current frontend stack**
  - React (CRA-style entry at `src/index.js`, main shell in `src/App.js`).
  - Fluent UI v9 (`@fluentui/react-components`) + Griffel for styling.
  - Main feature components:
    - `FileUpload` – upload PDFs and assign customer
    - `FileList` – list/group files by customer, batch process, delete
    - `FilePreview` – analysis markdown viewer, KPI tiles, capacity section, parameters accordion
    - `DocumentChat` – per-document chat against `/api/chat`
  - Teams-aware theming via Microsoft Teams SDK.
  - Docker + nginx for static hosting.

- **Target frontend stack**
  - **SAPUI5 (Fiori 3 / Quartz theme)**, freestyle app (XML views + controllers), not Fiori Elements.
  - Runs:
    - **Standalone** on generic web hosting (e.g., Azure Web App) using `index.html` + SAPUI5 bootstrap.
    - Later as a **Fiori app** on BTP (HTML5 App Repo + Work Zone / Launchpad), reusing the same UI5 app code.

- **Out of scope for this plan**
  - Backend refactors (APIs, auth, AI flows remain the same).
  - Non-UI build infra changes beyond what is needed to build and serve the UI5 app.

**Impact level:** Large (new UI framework, new app), but this plan is designed so the React app can coexist until the UI5 app is ready.

---

## 1. High-Level Migration Strategy

1. **Keep the current React frontend running** as the primary UI during migration.
2. **Introduce a new SAPUI5/Fiori app in parallel** within the same repo (e.g. a `fiori-ui/` folder).
3. **Re-implement the key screens and flows** from React into UI5, one by one:
   - File upload & customer assignment
   - File list & batch operations
   - Analysis preview (markdown/HTML)
   - Document chat
   - Deep-link preview (`?preview=` behaviour)
4. **Align UX with Fiori patterns** (List Report-like list + Object Page-like detail, dialogs for flows).
5. Once functionally complete and validated:
   - Decide whether to **switch the default UI** on the current host to the UI5 app.
   - Prepare **deployment artefacts for BTP** (xs-app, `manifest.json` `sap.cloud`, destinations).

This avoids a big-bang cutover and lets you test the UI5 app independently.

---

## 2. Repository & Project Layout for the UI5 App

**Objective:** Introduce a clean UI5 app structure alongside the existing React app.

### Step 2.1 – Create UI5 app folder

- **Create** a new folder in the repo root (sibling of `frontend/`):
  - `fiori-ui/`
- Inside `fiori-ui/`, create a standard UI5 structure:
  - `webapp/`
    - `index.html` (UI5 bootstrap, loads `Component.js`)
    - `Component.js` (UI component entry)
    - `manifest.json` (app descriptor: routing, models, dataSources, etc.)
    - `view/` (XML views)
    - `controller/` (JS controllers)
    - `i18n/` (texts)
    - `model/` (helpers: API base URL, JSON models)
    - `css/` (custom styles if needed)
  - `ui5.yaml` (if using UI5 Tooling for local dev)

**Impact:** Small (new files only). No existing frontend files are touched.

### Step 2.2 – Decide UI5 bootstrap source

- **Option A – SAP CDN (simpler for start):**
  - `index.html` includes `<script src="https://ui5.sap.com/resources/sap-ui-core.js" ...>`
  - Good for initial dev and Azure hosting.
- **Option B – Self-hosted UI5 (for BTP/controlled environments):**
  - Use UI5 Tooling and build pipeline to bundle UI5 resources.

For the initial migration plan, assume **Option A** (CDN) to keep complexity low.

**Impact:** Small. Configuration choice only.

---

## 3. Map Existing React Features to Fiori Floorplans

**Objective:** Translate what you have now into Fiori concepts so you know what to build.

### 3.1 Existing React feature map

- **Shell & layout (`App.js`)**
  - Sidebar: File upload + file list
  - Main area: File preview
  - Fullscreen preview & deep-link `?preview=<reportBaseName>`

- **File upload (`FileUpload.js`)**
  - Select multiple files
  - For each file, assign a customer (combobox) then upload
  - Shows per-file progress + overall status

- **File list (`FileList.js`)**
  - Group files by customer (accordion)
  - Select files, batch process, batch delete
  - Show processing status per file (pending/processing/completed/error)

- **File preview (`FilePreview.js`)**
  - Show EWA analysis (markdown → rich view, KPIs, tables)
  - Show KPI tiles
  - Show Capacity Outlook section
  - Placeholder when no file selected

- **Document chat (`DocumentChat.js`)**
  - Floating chat dialog bound to current document
  - Calls `/api/chat` with `fileName`, `documentContent`, `chatHistory`

### 3.2 Proposed Fiori mapping

- **Overall shell (target pattern):**
  - Use `sap.f.FlexibleColumnLayout` as the primary shell (Files + Analysis master–detail); `sap.m.SplitApp` is not planned for this app:
    - Column 1: Files list (uploaded/processed files, grouped by customer).
    - Column 2: Analysis detail for the selected file (preview, KPIs, future chat).
    - Chat as overlay (`sap.m.Dialog`) or side panel anchored to the analysis column.
  - The exact Fiori layout inside the Analysis column (for example, whether to use an Object Page-style layout or a simpler Page) is intentionally left open and will be decided later.

- **File list & batch actions:**
  - `sap.m.Page` + `sap.m.Table` or `sap.m.List` with grouping by customer.
  - Toolbar with buttons: Process, Delete, etc.
  - Target UX follows the left pane of `Fiori_design.png`: upload area at the top, a "Your Files" style table with status pills and search in the middle, and optional error/warning details below.
  - **Future UX refinements (not required for initial rollout, but recommended):**
    - Use `sap.m.Panel`/`Card` around the table to frame the "Your Files" section.
    - Replace raw timestamps with formatted dates/times for Uploaded/Processed columns.
    - Represent status using `sap.m.ObjectStatus` with semantic colors (Processing, Processed, Failed, Analyzed).
    - Add a simple filter strip (All/Processing/Processed/Failed) above the table.
    - Add a search field in the header toolbar for quick file filtering.
    - Add a secondary table/card below for "Error & Warning Details" per analysis, similar to the mock.

- **File upload & customer assignment:**
  - `sap.m.UploadCollection` or simple `sap.m.FileUploader` + `sap.m.Dialog` with `sap.m.ComboBox` for customer.

- **Analysis preview:**
  - `sap.f.DynamicPage` / `sap.m.Page` with sections, following the right pane of `Fiori_design.png` as the visual reference:
    - Header: file name, status pill, and main actions (for example, download/refresh analysis).
    - KPI strip: key metrics for the selected file (records, issues, warnings, quality score, etc.).
    - Content sections: executive summary text, data quality overview (charts), capacity outlook, and recommendations.

- **Document chat:**
  - `sap.m.Dialog` with list of messages (`sap.m.List` or `sap.m.FeedListItem`).
  - `sap.m.TextArea` + send button at the bottom.

- **Deep-link preview:**
  - UI5 routing (`manifest.json` `sap.ui5.routing`) with a route like `preview/{baseName}` that opens the analysis page directly.

---

## 4. Phase 1 – Foundation: UI5 App Skeleton & Routing

**Goal:** Get a minimal UI5 app running with navigation structure but **no business logic** yet.

### Step 4.1 – Implement `index.html`, `Component.js`, `manifest.json`

- `index.html`
  - Bootstrap UI5 (Quartz theme, Fiori 3)
  - Define `data-sap-ui-resourceroots` for your namespace (e.g. `"ewa.analyzer": "./"`).

- `Component.js`
  - Extend `sap.ui.core.UIComponent`.
  - Init router.
  - Set content density class.

- `manifest.json`
  - Define:
    - `sap.app` (id, title, application type `"sap.ui5"`).
    - `sap.ui5` (rootView, routing, models).
    - Basic routes:
      - `Main` route with pattern `""` → main shell view.
      - `Preview` route with pattern `"preview/{baseName}"` for deep-link.

**Impact:** Medium (new app descriptor and component, but isolated).

### Step 4.2 – Create shell views and controllers

- `view/App.view.xml`
  - Hosts a `sap.f.FlexibleColumnLayout` shell for Files (master) and Analysis (detail). The concrete layout of the Analysis content area will be refined in a later design step.

- `controller/App.controller.js`
  - Handles routing events.
  - Loads initial data models if needed.

- Define subviews:
  - `view/FileList.view.xml` + `controller/FileList.controller.js`
  - `view/Analysis.view.xml` + `controller/Analysis.controller.js`

**Impact:** Medium. No backend calls yet, purely structural.

---

## 5. Phase 2 – Integrate Backend APIs in UI5

**Goal:** Reuse the existing backend endpoints from the new UI5 app.

### Step 5.1 – Centralize API base URL

- Create `model/config.js` or similar to mirror `src/config.js`:
  - Reads base URL (environment or window variable).
  - Exposes helper to build full URLs.

- Decide whether to use:
  - `sap.ui.model.json.JSONModel` with `loadData`/`attachRequestCompleted`, or
  - `fetch`/`jQuery.ajax` + manual model updates.

**Impact:** Small.

### Step 5.2 – Wire file list endpoint

- Identify which React calls retrieve the file list (in `FileList.js`).
- Implement equivalent GET in `FileList.controller.js`.
  - Populate a JSON model (e.g. `/files`) bound to `FileList.view.xml` table/list.

**Impact:** Medium (business code, but straightforward mapping).

### Step 5.3 – Wire upload endpoints

- Mirror the `FileUpload` logic:
  - Use `sap.m.FileUploader` or `sap.m.UploadCollection`.
  - For each file, send customer assignment in the payload, matching current backend contract.
  - Show progress states (uploading/success/error) with Fiori messaging (`sap.m.MessageToast`, `sap.m.MessageStrip`, or status column).

**Impact:** Medium.

### Step 5.4 – Wire process & delete endpoints

- Implement batch process & delete actions in `FileList.controller.js`:
  - Bind selection to table/list items.
  - Call existing process/delete APIs.
  - Refresh `/files` model on success.

**Impact:** Medium.

### Step 5.5 – Wire analysis download endpoint

- Equivalent of React deep-link fetch in `App.js`:
  - For `preview/{baseName}` route, call backend download endpoint (e.g. `/api/download/{baseName}_AI.md`).
  - Parse/handle markdown (see next phase) and bind to `/analysis` model.

**Impact:** Medium.

### Step 5.6 – Wire `/api/chat` endpoint

- Implement chat controller:
  - Prepare request body as in `DocumentChat.js` (message, fileName, documentContent, chatHistory).
  - Call `/api/chat` via fetch or JSONModel and push messages into a `/chat` model.

**Impact:** Medium.

### Current implementation status (UI5 app)

- **Phase 1 – Foundation**
  - Basic UI5 app skeleton is in place (`index.html`, `Component.js`, `manifest.json`).
  - `App.view.xml` currently hosts a simple `sap.m.App` with two pages: `FileList` (start) and `Analysis`. The `sap.f.FlexibleColumnLayout` shell remains a **target pattern** for later refinement, not yet implemented.
  - `Analysis.view.xml` and `Analysis.controller.js` provide a placeholder analysis page layout (selected file summary, preview area, KPIs area, future chat area), with no backend logic yet.

- **Phase 2 – Backend integration and Files UX**
  - **Step 5.1 (API base URL):** Implemented via `webapp/model/config.js`, which reads `window.__ENV__.REACT_APP_API_BASE` when present and otherwise defaults to the Azure backend URL `https://sap-ewa-analyzer-backend.azurewebsites.net`.
  - **Step 5.2 (file list wiring):** Implemented in `FileList.controller.js` + `FileList.view.xml`:
    - `FileList.controller.js` calls `/api/files`, handles error cases, and populates a `JSONModel` with both raw files and derived display fields for dates.
    - `FileList.view.xml` shows a table with columns *File Name*, *Customer*, *Status*, *Uploaded On*, *Report Date*, and *Actions*, with a `View Analysis` action that navigates to the Analysis page.
    - The Files page toolbar already includes a search field, a (placeholder) filter button, and selection-aware Process/Delete buttons (UI-only; endpoints not yet wired).
  - **Step 5.3–5.6 (upload, process/delete, analysis download, chat):** Not yet implemented in UI5; all Upload/Process/Delete/Chat behaviour is still provided by the existing React app.

  - **UX alignment with `Fiori_design.png`**
    - Files page now approximates the "Your Files" card: panel-framed table, status chips, search, and a dedicated *View Analysis* action that opens a separate Analysis page.
    - The analysis page layout now shows real markdown content for analyzed files using a basic markdown-to-HTML conversion and `sap.m.FormattedText`. The overall layout (KPI tiles, charts, etc.) still follows the right-hand mock only at a placeholder level.

---

## 6. Phase 3 – Analysis Rendering & KPIs in UI5

**Goal:** Recreate the `FilePreview` experience with UI5 controls.

### Step 6.1 – Decide on markdown handling

Options:

1. **Backend converts markdown to HTML** (preferred for UI5 simplicity):
   - Extend backend to provide an HTML version of the analysis (or reuse existing converter, if any).
   - UI5 uses `sap.ui.core.HTML` or `sap.m.FormattedText` to render the HTML.

2. **UI5-side markdown parsing:**
   - Include a lightweight markdown parser in the UI5 app.
   - Convert markdown to HTML at runtime and feed `sap.ui.core.HTML`.

The plan assumes **Option 1** for cleaner UI5 code; adjust if backend changes are not allowed.

**Impact:** Medium (cross-layer decision but manageable).

### Step 6.2 – Layout analysis view

- In `Analysis.view.xml`:
  - Use `sap.f.DynamicPage` with:
    - Title area: file name, customer, maybe a status badge.
    - Content area: results sections.

- Create named sections matching your current React layout:
  - Main narrative / tables (from analysis HTML/markdown).
  - KPI section.
  - Capacity Outlook.
  - Parameters (collapsible section).

**Impact:** Medium.

### Step 6.3 – Implement KPI tiles

- Define a model structure equivalent to your current `metricsData`.
- Use `sap.m.GenericTile` or custom responsive layout to display:
  - Indicator
  - Value
  - Area
  - Trend (↑/↓/→) with color coding.

**Impact:** Small–Medium.

### Step 6.4 – Capacity Outlook & parameters

- For tabular sections:
  - Use `sap.m.Table` or `sap.m.ResponsiveTable` bound to arrays from the analysis model.
  - Apply status/risk styling similar to your current `getStatusStyle` logic (map to `sap.m.ObjectStatus`, colored texts, or custom CSS classes).

**Impact:** Medium.

---

## 7. Phase 4 – Document Chat UX in UI5

**Goal:** Recreate `DocumentChat` floating assistant in Fiori.

### Step 7.1 – Chat container

- Use `sap.m.Dialog` or `sap.m.Panel` anchored to the analysis view.
- Provide a button in the analysis header (e.g. "Ask about this report") that opens the dialog.

### Step 7.2 – Messages list

- Model: array of messages `{ text, isUser, isError, timestamp }`.
- View:
  - `sap.m.List` with custom `ObjectListItem` or `CustomListItem` templates.
  - Different visual styling based on `isUser`/`isError`.

### Step 7.3 – Input and send logic

- `sap.m.TextArea` + `sap.m.Button`.
- On send:
  - Append user message to model.
  - Call `/api/chat` (Section 5.6).
  - Append assistant/error message on completion.

**Impact:** Medium.

---

## 8. Phase 5 – UX Polish, Error Handling, and Parity Checks

**Goal:** Match current UX features and quality as closely as possible.

### Step 8.1 – Busy indicators and error feedback

- Replace React spinners/alerts with Fiori equivalents:
  - `sap.m.BusyIndicator` or `setBusy(true/false)` on views.
  - `sap.m.MessageStrip` for persistent messages.
  - `sap.m.MessageToast` for transient notifications.

### Step 8.2 – Empty states and placeholders

- Recreate existing empty states (no files uploaded, no file selected, limited content) as:
  - `sap.m.IllustratedMessage` where appropriate, or
  - Simple `sap.m.VBox` with icon + title + subtext.

### Step 8.3 – Parity checklist

- For each React component, verify parity:
  - **FileUpload**
    - Multiple file selection
    - Customer assignment per file
    - Per-file progress + overall status
  - **FileList**
    - Grouping by customer
    - Batch process/delete
    - Status indicators
  - **FilePreview**
    - KPI tiles
    - Capacity Outlook tables
    - Deep-link route opens same analysis
  - **DocumentChat**
    - Chat history persisted during session
    - Error messages surfaced clearly

**Impact:** Medium.

---

## 9. Phase 6 – Coexistence and Cutover Strategy

**Goal:** Switch from React to UI5 without breaking users.

### Step 9.1 – Run both UIs in parallel

- Keep current React app served as today.
- Expose UI5 app under a different path/URL (e.g. `/fiori/` or separate host).
- Internal users validate functionality and performance.

### Step 9.2 – Feature flag / routing switch

- Option A (host-level): switch Nginx (or Azure Web App routing) to point the main URL to the UI5 app once stable.
- Option B (app-level): keep React as a shell that redirects users to UI5 via link/tile (only if needed).

**Impact:** Small–Medium (mostly infra/routing changes).

---

## 10. Phase 7 – Preparing for BTP / Work Zone Deployment

**Goal:** Make the UI5 app ready to run as a tile in SAP Build Work Zone / Launchpad.

### Step 10.1 – Enhance `manifest.json` for Launchpad

- Add `sap.cloud` section with:
  - `service` name
- Add cross-navigation intent in `sap.app`:
  - Semantic object + action (e.g. `"EWAReport"-"display"`).

### Step 10.2 – Introduce BTP routing config (xs-app)

- Create `xs-app.json` with:
  - Routes for static resources (UI5 app).
  - Route(s) for backend APIs (destinations) mapping to your existing backend.

### Step 10.3 – HTML5 App Repo & Work Zone config

- Package the UI5 app as an HTML5 app.
- Configure:
  - Destination(s) to your backend.
  - Work Zone site, roles, groups/spaces, tiles.

**Impact:** Medium–Large (BTP-specific tasks), but UI code changes minimal if app was designed with this in mind.

---

## 11. Suggested Implementation Order & Risk Notes

**Recommended order:**

1. **Phase 1** – UI5 skeleton + routing (get something running).
2. **Phase 2** – Core data integration (file list, upload, process/delete).
3. **Phase 3** – Analysis view (HTML/markdown + KPI + Capacity Outlook).
4. **Phase 4** – Document chat.
5. **Phase 5** – UX polish and parity checks.
6. **Phase 6** – Parallel run + cutover.
7. **Phase 7** – BTP/Work Zone enablement.

**Key risks to watch:**

- **Markdown → UI5 rendering**: decide early whether backend will serve HTML.
- **API contract drift**: keep React and UI5 pointing to the same backend contracts to avoid divergence.
- **Performance**: ensure UI5 app handles large reports gracefully (busy indicators, chunked rendering if needed).

---

## 12. Next Steps

- Confirm:
  - Whether backend can expose an **HTML analysis endpoint** (for easier UI5 rendering).
  - Preferred **Fiori layout pattern** (FlexibleColumnLayout vs SplitApp).
- Once confirmed, start implementing **Phase 1** in `fiori-ui/` while keeping React frontend untouched until parity is reached.
