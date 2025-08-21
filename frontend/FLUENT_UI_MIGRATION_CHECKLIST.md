# Fluent UI Migration Checklist (Teams + Web)

This checklist guides migrating the frontend from Material UI (MUI) to Microsoft Fluent UI (v9) to ensure compatibility with Microsoft Teams and web browsers.

Use it incrementally and check off items as you complete them.

---

## 0) Scope and Goals
- [ ] Replace all MUI components, theming, and icons with Fluent UI v9 equivalents
- [ ] Adopt Fluent theming with Teams-compatible themes and tokens
- [ ] Remove Emotion/MUI styling (`sx`) and migrate styles to Fluent v9’s styling (`makeStyles` from Griffel, tokens, shorthands)
- [ ] Validate accessibility and behavior parity
- [ ] Ensure UI renders correctly both in Teams (as a Tab) and in the web browser

Key files impacted (from current codebase):
- `src/App.js`
- `src/components/FileList.js`
- `src/components/FilePreview.js`
- `src/components/FileUpload.js`

---

## 1) Inventory and Preparation
- [ ] Create a feature branch for migration (e.g., `feat/fluent-ui-migration`)
- [ ] Inventory current MUI usage by searching for `@mui` imports across `src/`
- [ ] List all icons from `@mui/icons-material` used in the app
- [ ] Note areas using `sx` prop heavily for styling

---

## 2) Dependencies
Install Fluent UI and Teams SDK packages.

- [ ] Install Fluent UI v9 components and icons
  - `npm install @fluentui/react-components @fluentui/react-icons`
- [ ] Install Microsoft Teams JavaScript SDK (for theme awareness and hosting integration)
  - `npm install @microsoft/teams-js`
- [ ] (Optional) If using charts or other advanced components later, evaluate dedicated Fluent-compatible libs separately

Do not remove MUI yet; keep the app running during incremental migration. Remove MUI after all replacements are done (see Cleanup).

---

## 3) Theming and Providers (App Root)
Goal: Replace MUI ThemeProvider with Fluent v9 `FluentProvider` and adopt Teams-compatible themes.

- [ ] Add `FluentProvider` at the top of the app tree (e.g., wrap contents in `src/App.js` or `src/index.js`)
- [ ] Use shipped themes from Fluent v9 (e.g., `webLightTheme`, `webDarkTheme`) or Teams variants if applicable (`teamsLightTheme`, `teamsDarkTheme`, `teamsHighContrastTheme`)
- [ ] Wire up Teams theme awareness via `@microsoft/teams-js`:
  - Initialize the SDK when hosted in Teams
  - Read current theme and apply the matching Fluent theme
  - Subscribe to theme change events and update the provider theme dynamically
- [ ] Remove MUI’s `ThemeProvider`, `CssBaseline`, and MUI theme configuration when the migration is complete

Notes:
- Fluent v9 encourages tokens and design primitives (e.g., typography levels like `Title3`, `Subtitle2`, `Body1`, etc.) through components and tokens rather than a monolithic theme object.

---

## 4) Styling Migration (from `sx` and Emotion)
- [ ] Replace MUI `sx` usage with Fluent v9 styling:
  - Use `makeStyles` (from Griffel) and `shorthands` utilities from `@fluentui/react-components`
  - Use Fluent `tokens` for colors, spacing, typography, borders, and shadows
- [ ] Prefer composition: className + `makeStyles` + tokens instead of inline styles
- [ ] Remove Emotion packages and MUI theme-only styles after all components have been migrated

References in code to convert:
- `Box` layout + `sx` → Fluent `makeStyles` + CSS flex/grid + tokens
- Custom shadows/borders → use Fluent tokens where available

---

## 5) Component Replacement Map
Use the following mapping to replace MUI components with Fluent v9 equivalents or patterns.

General:
- [ ] `ThemeProvider` (MUI) → `FluentProvider` (Fluent v9)
- [ ] `CssBaseline` (MUI) → No direct equivalent; rely on Fluent defaults and tokens
- [ ] `Typography` (MUI) → Fluent text/typography components (e.g., `Text`, `Title3`, `Subtitle2`, `Caption1`)
- [ ] `Tooltip` (MUI) → `Tooltip` (Fluent v9)
- [ ] `Divider` (MUI) → `Divider` (Fluent v9)
- [ ] `Paper` (MUI) → `Card` (Fluent v9) or a styled container div with tokens
- [ ] `Grid`/`Box` (MUI) → Flex/Grid layout via CSS + `makeStyles`/tokens

Navigation & Layout:
- [ ] `AppBar` + `Toolbar` (MUI) → `Toolbar` (Fluent v9) + custom header layout
- [ ] `Drawer` (MUI) → `Drawer` (Fluent v9) for overlays/side panels, or a persistent left rail built with layout + `Card`/`Accordion`

Inputs & Controls:
- [ ] `Button` (MUI) → `Button` (Fluent v9)
- [ ] `IconButton` (MUI) → `Button` (Fluent v9) with `icon` only or `appearance="transparent"`
- [ ] `TextField` (MUI) → `Input` (Fluent v9) or `Textarea` (for multi-line)
- [ ] `Select` + `MenuItem` (MUI) → `Dropdown` or `Combobox` + `Option` (Fluent v9)
- [ ] `Checkbox` (MUI) → `Checkbox` (Fluent v9)
- [ ] `Chip` (MUI) → `Tag` (Fluent v9) for labeled pills; `Badge` when indicating status/count
- [ ] `Badge` (MUI) → `Badge` (Fluent v9)
- [ ] `Switch`/`Toggle` (if any) → `Switch` (Fluent v9)

Feedback & Overlays:
- [ ] `Alert` (MUI) → `Alert` (Fluent v9) for inline messages
- [ ] `Snackbar` (MUI) → `Toaster`/`Toast` (Fluent v9) for transient notifications
- [ ] `Dialog` (if present) → `Dialog` (Fluent v9)
- [ ] `Popover`/`Menu` equivalents map directly to Fluent v9 `Popover`/`Menu`

Disclosure & Structure:
- [ ] `Accordion`, `AccordionSummary`, `AccordionDetails` (MUI) → `Accordion`, `AccordionItem`, `AccordionHeader`, `AccordionPanel` (Fluent v9)
- [ ] `Table` (MUI) → `Table` (Fluent v9: `Table`, `TableHeader`, `TableBody`, `TableRow`, `TableHeaderCell`, `TableCell`)
  - For virtualization or very large lists, consider custom virtualization around Fluent’s Table
- [ ] `List`/`ListItem` (MUI) → Build with Fluent `Table` rows, or lightweight cards + buttons; choose pattern based on interaction requirements

Progress & Status:
- [ ] `LinearProgress` (MUI) → `ProgressBar` (Fluent v9)
- [ ] `CircularProgress` (MUI) → `Spinner` (Fluent v9)

Icons:
- [ ] `@mui/icons-material` → `@fluentui/react-icons`
  - Import specific icons (e.g., `Add24Regular`, `CloudArrowUp24Regular`, `Dismiss24Regular`, `ChevronLeft24Regular`, `ChevronRight24Regular`, `Document24Regular`, `Image24Regular`, `DocumentPdf24Regular`, `CheckmarkCircle24Regular`, `ErrorCircle24Regular`, `Building24Regular`)
  - Prefer 20px icons in compact UI and 24px in standard spacing

---

## 6) File-by-File Plan

`src/App.js`
- [ ] Replace MUI `ThemeProvider`/`CssBaseline` with `FluentProvider` and a chosen Fluent theme
- [ ] Convert `AppBar` + `Toolbar` to Fluent `Toolbar` (and layout wrappers)
- [ ] Replace `Drawer` with Fluent `Drawer` (or a persistent left rail using layout + `Card`/`Accordion`)
- [ ] Replace `Typography`, `IconButton`, `Tooltip` with Fluent equivalents
- [ ] Remove `sx` styles; migrate to `makeStyles` + tokens

`src/components/FileUpload.js`
- [ ] Replace `Button`, `Typography`, `Alert`, `Paper`, `TextField`, `FormHelperText`, `Select`, `InputLabel`, `MenuItem`, `Chip`, `IconButton`, `LinearProgress`, `Badge`, `Divider`
- [ ] Use `Input`, `Dropdown` or `Combobox` + `Option`, `Alert`, `ProgressBar`, `Tag`, `Badge`, `Card`
- [ ] Replace all icons with `@fluentui/react-icons`, update `getFileIcon()` accordingly
- [ ] Convert all `sx` styling to `makeStyles` + tokens

`src/components/FileList.js`
- [ ] Replace `Paper`, `Typography`, `List*`, `Button`, `IconButton`, `Tooltip`, `Checkbox`, `Accordion*`, `Snackbar`, `Alert`, `Chip`, `CircularProgress`, `Divider`
- [ ] Consider consolidating file entries into a Fluent `Table` to simplify selection, progress, and batch actions
- [ ] Replace notifications: inline `Alert` or transient `Toast` via a `Toaster` provider
- [ ] Convert `sx` styles to `makeStyles`

`src/components/FilePreview.js`
- [ ] Replace `Paper`, `Typography`, `Accordion*`, `Table*`, `Tooltip`, `IconButton`, `Chip`, `Divider`, `CircularProgress`
- [ ] Use Fluent `Accordion` and `Table` family
- [ ] Replace all icons with `@fluentui/react-icons`
- [ ] Migrate `sx` styling to `makeStyles` + tokens

---

## 7) Patterns and UX Notes
- [ ] Keep notification patterns consistent: use `Alert` for inline persistent messages; use `Toast` for transient status
- [ ] Prefer `Button` with `appearance="primary" | "secondary" | "outline" | "subtle"` to map MUI variants
- [ ] Apply spacing, shadows, and colors using tokens; avoid hard-coded hex values where possible
- [ ] Ensure keyboard accessibility (Tab order, ARIA labels for icon-only buttons, focus outlines)

---

## 8) Teams Integration
- [ ] Detect Teams hosting via `@microsoft/teams-js` and initialize the SDK
- [ ] Read the current theme and apply `teamsLightTheme`/`teamsDarkTheme`/`teamsHighContrastTheme` to `FluentProvider`
- [ ] Subscribe to theme change events and update the provider theme accordingly
- [ ] Validate layouts and colors in Teams desktop and web clients

---

## 9) Testing Checklist
- [ ] Smoke test the app in the browser after each file migration
- [ ] Verify component behavior parity (drawer open/close, lists, tables, accordions, form validation)
- [ ] Verify notifications (Alert/Toast) including close actions and auto-dismiss timing
- [ ] Check keyboard navigation and focus states
- [ ] Visual QA in light and dark modes (web and Teams)
- [ ] Run in Teams (sideload) and verify theme switching works

---

## 10) Cleanup
- [ ] Remove all MUI imports and packages: `@mui/material`, `@mui/icons-material`, Emotion packages
- [ ] Remove MUI-specific theme and context code
- [ ] Search for any lingering `sx` usage and replace
- [ ] Update `package.json` and lockfile; ensure only Fluent UI remains for UI components

---

## 11) Rollout Strategy (Incremental)
- [ ] Step 1: Introduce FluentProvider + theme, keep MUI components running
- [ ] Step 2: Migrate `App.js` shell (AppBar/Drawer/Toolbar)
- [ ] Step 3: Migrate `FileUpload.js` (forms, selects, progress, alerts)
- [ ] Step 4: Migrate `FileList.js` (lists/accordions → Table + actions + toasts)
- [ ] Step 5: Migrate `FilePreview.js` (accordion/table + icons)
- [ ] Step 6: Replace remaining icons and remove MUI
- [ ] Step 7: Theming polish + Teams events + accessibility pass

---

## Icon Replacement Reference (common usage)
Replace MUI icons with similarly named Fluent System Icons from `@fluentui/react-icons`.

Examples you will likely need:
- Add → `Add20Regular`/`Add24Regular`
- CloudUpload → `CloudArrowUp20Regular`/`CloudArrowUp24Regular`
- Close → `Dismiss20Regular`/`Dismiss24Regular`
- CheckCircle → `CheckmarkCircle20Regular`/`CheckmarkCircle24Regular`
- Error → `ErrorCircle20Regular`/`ErrorCircle24Regular`
- Description/InsertDriveFile → `Document20Regular`/`Document24Regular`
- PictureAsPdf → `DocumentPdf20Regular`/`DocumentPdf24Regular`
- Image → `Image20Regular`/`Image24Regular`
- TextSnippet → `DocumentText20Regular`/`DocumentText24Regular`
- Business → `Building20Regular`/`Building24Regular`
- Settings → `Settings20Regular`/`Settings24Regular`
- HelpOutline → `QuestionCircle20Regular`/`QuestionCircle24Regular`
- ChevronLeft/Right → `ChevronLeft20Regular`/`ChevronRight20Regular` (or 24)

Pick 20px for dense UIs (e.g., toolbars) and 24px for standard buttons/headers.

---

## Success Criteria
- No `@mui/*` imports remain
- All UI is rendered through `@fluentui/react-components` and `@fluentui/react-icons`
- Teams theme is applied correctly and responds to theme changes
- Accessibility checks pass for keyboard and screen reader basics
- Visual QA matches design intent in both Teams and web
