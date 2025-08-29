import React, { useState } from 'react';
import { Toolbar as FluentToolbar, ToolbarButton, Tooltip as FluentTooltip, Button as FluentButton, makeStyles, shorthands, tokens, Menu, MenuTrigger, MenuPopover, MenuList, MenuItemRadio } from '@fluentui/react-components';
import { Document24Regular, Settings24Regular, QuestionCircle24Regular } from '@fluentui/react-icons';

import FileUpload from './components/FileUpload';
import FileList from './components/FileList';
import FilePreview from './components/FilePreview';
// Theme is managed by FluentProvider in src/index.js

const drawerWidth = 480; // Increased width to accommodate analyze buttons and status and show more file details
const collapsedDrawerWidth = 0; // Width when drawer is collapsed
const topBarHeight = 0;

const useStyles = makeStyles({
  root: {
    display: 'flex',
    height: '100vh',
  },
  topBar: {
    position: 'fixed',
    top: 0,
    left: 0,
    right: 0,
    zIndex: 1000,
    display: 'none',
    backgroundColor: 'transparent',
    borderBottom: 'none',
  },
  topBarInner: {
    display: 'flex',
    alignItems: 'center',
    ...shorthands.padding('8px', '16px'),
    color: tokens.colorNeutralForegroundOnBrand,
  },
  appTitle: {
    color: 'inherit',
    fontWeight: 400,
  },
  sidebar: {
    flexShrink: 0,
    transition: 'width 225ms cubic-bezier(0.4, 0, 0.6, 1) 0ms',
    height: 'auto',
    boxSizing: 'border-box',
    backgroundColor: tokens.colorNeutralBackground1,
    borderRight: `1px solid ${tokens.colorNeutralStroke1}`,
    overflow: 'hidden',
    boxShadow: tokens.shadow8,
    color: tokens.colorNeutralForeground1,
    display: 'flex',
    flexDirection: 'column',
    minHeight: 0, // allow inner content to shrink and scroll
    // no scrollbar here; inner content owns scrolling
    position: 'fixed',
    top: `${topBarHeight}px`,
    bottom: 0,
    left: 0,
  },
  toolbarSpacer: {
    height: `${topBarHeight}px`,
  },
  sidebarHeaderRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingLeft: '16px',
    paddingRight: '16px',
    paddingTop: '16px',
    paddingBottom: '8px',
  },
  sidebarTitle: {
    fontWeight: 500,
    color: tokens.colorNeutralForeground1,
    fontSize: '1.1rem',
  },
  sidebarContent: {
    overflowY: 'auto',
    paddingLeft: '16px',
    paddingRight: '16px',
    paddingBottom: '16px',
    display: 'flex',
    flexDirection: 'column',
    gap: '24px',
    backgroundColor: tokens.colorNeutralBackground1,
    flex: 1,
    minHeight: 0,
    // Make dragging the scrollbar responsive and prevent scroll chaining to the page
    overscrollBehavior: 'contain',
    selectors: {
      '&::-webkit-scrollbar': { width: '12px' },
      '&::-webkit-scrollbar-track': { background: tokens.colorNeutralBackground2 },
      '&::-webkit-scrollbar-thumb': { background: tokens.colorNeutralStroke1, borderRadius: '6px' },
      '&::-webkit-scrollbar-thumb:hover': { background: tokens.colorNeutralForeground3 },
    },
  },
  collapseEdge: {
    position: 'fixed',
    top: '50%',
    left: 0,
    zIndex: 1200,
    transform: 'translateY(-50%)',
    backgroundColor: tokens.colorBrandBackground,
    borderRadius: '0 4px 4px 0',
    boxShadow: '2px 0 8px rgba(0,0,0,0.5)',
    transition: 'left 225ms cubic-bezier(0.4, 0, 0.6, 1) 0ms',
  },
  main: {
    flexGrow: 1,
    padding: '24px',
    display: 'flex',
    flexDirection: 'column',
    backgroundColor: tokens.colorNeutralBackground2,
    transition: 'width 225ms cubic-bezier(0.4, 0, 0.6, 1) 0ms, margin 225ms cubic-bezier(0.4, 0, 0.6, 1) 0ms',
  },
  mainInner: {
    flexGrow: 1,
    height: '100%',
    display: 'flex',
    alignItems: 'stretch',
  },
});

// Inner App component that uses the theme context
const AppContent = () => {
  const [selectedFileForPreview, setSelectedFileForPreview] = useState(null);
  const [fileListRefreshTrigger, setFileListRefreshTrigger] = useState(0);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [fontPrefUI, setFontPrefUI] = useState(() => {
    try {
      const allowed = ['inter', 'roboto', 'open-sans', 'source-sans-3', 'system-ui', 'teams'];
      const v = window.localStorage.getItem('fontPref');
      return allowed.includes(v) ? v : 'open-sans';
    } catch { return 'open-sans'; }
  });
  const classes = useStyles();

  const handleUploadSuccess = () => {
    setFileListRefreshTrigger(prev => prev + 1);
  };

  return (
    <div className={classes.root}>
      <div className={classes.topBar}>
        <div className={classes.topBarInner}>
          <FluentToolbar>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'inherit' }}>
              <Document24Regular />
              <span className={classes.appTitle}>EWA Analyzer</span>
            </div>
            <div style={{ flex: 1 }} />
            <FluentTooltip content="Settings" relationship="label">
              <ToolbarButton aria-label="Settings" icon={<Settings24Regular />} />
            </FluentTooltip>
            <FluentTooltip content="Help" relationship="label">
              <ToolbarButton aria-label="Help" icon={<QuestionCircle24Regular />} />
            </FluentTooltip>
          </FluentToolbar>
        </div>
      </div>

      <aside className={classes.sidebar} style={{ width: sidebarCollapsed ? collapsedDrawerWidth : drawerWidth }}>
        <div className={classes.sidebarHeaderRow}>
          <span className={classes.sidebarTitle}>File Management</span>
          <Menu
            checkedValues={{ font: [fontPrefUI] }}
            onCheckedValueChange={(e, { name, checkedItems }) => {
              if (name === 'font') {
                const next = checkedItems[0] || 'inter';
                setFontPrefUI(next);
                try { window.localStorage.setItem('fontPref', next); } catch {}
                if (typeof window.__setAppFontPref === 'function') window.__setAppFontPref(next);
              }
            }}
          >
            <MenuTrigger disableButtonEnhancement>
              <FluentButton
                appearance="subtle"
                size="small"
                aria-label="App settings"
                icon={<Settings24Regular />}
              />
            </MenuTrigger>
            <MenuPopover>
              <MenuList>
                <MenuItemRadio name="font" value="inter">Inter</MenuItemRadio>
                <MenuItemRadio name="font" value="roboto">Roboto</MenuItemRadio>
                <MenuItemRadio name="font" value="open-sans">Open Sans</MenuItemRadio>
                <MenuItemRadio name="font" value="source-sans-3">Source Sans 3</MenuItemRadio>
                <MenuItemRadio name="font" value="system-ui">System UI</MenuItemRadio>
                <MenuItemRadio name="font" value="teams">Teams Default</MenuItemRadio>
              </MenuList>
            </MenuPopover>
          </Menu>
        </div>
        <div className={classes.sidebarContent}>
          <FileUpload onUploadSuccess={handleUploadSuccess} />
          <FileList 
            onFileSelect={setSelectedFileForPreview} 
            refreshTrigger={fileListRefreshTrigger}
            selectedFile={selectedFileForPreview}
          />
        </div>
      </aside>

      {/* Sidebar toggle removed by design */}

      <main
        className={classes.main}
        style={{
          width: `calc(100% - ${sidebarCollapsed ? collapsedDrawerWidth : drawerWidth}px)`,
          marginLeft: `${sidebarCollapsed ? collapsedDrawerWidth : drawerWidth}px`,
        }}
      >
        <div className={classes.toolbarSpacer} />
        <div className={classes.mainInner}>
          <FilePreview selectedFile={selectedFileForPreview} />
        </div>
      </main>
    </div>
  );
};

// Main App component that provides the theme context
function App() {
  return (
    <AppContent />
  );
}

export default App;
