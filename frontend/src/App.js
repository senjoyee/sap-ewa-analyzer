import React, { useState, useEffect } from 'react';
import { Toolbar as FluentToolbar, ToolbarButton, Tooltip as FluentTooltip, makeStyles, shorthands, tokens, Menu, MenuTrigger, MenuPopover, MenuList, MenuItem, Button } from '@fluentui/react-components';
import { Document24Regular, Settings24Regular, QuestionCircle24Regular, TextFont24Regular, Checkmark24Regular } from '@fluentui/react-icons';

import FileUpload from './components/FileUpload';
import FileList from './components/FileList';
import FilePreview from './components/FilePreview';
import { apiUrl } from './config';
// Theme is managed by FluentProvider in src/index.js

const drawerWidth = 480; // Increased width to accommodate analyze buttons and status and show more file details
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
    minHeight: 0,
    position: 'fixed',
    top: `${topBarHeight}px`,
    bottom: 0,
    left: 0,
  },
  fullscreenOverlay: {
    position: 'fixed',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    zIndex: 9999,
    backgroundColor: tokens.colorNeutralBackground2,
    display: 'flex',
    flexDirection: 'column',
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
const AppContent = ({ fontOptions = {}, currentFont = '', onFontChange }) => {
  const [selectedFileForPreview, setSelectedFileForPreview] = useState(null);
  const [fileListRefreshTrigger, setFileListRefreshTrigger] = useState(0);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [standalonePreview, setStandalonePreview] = useState(false);
  const classes = useStyles();

  const fonts = fontOptions;
  const selectedFontKey = currentFont;

  const handleFontChange = (fontKey) => {
    if (onFontChange && fonts[fontKey]) {
      onFontChange(fontKey);
    }
  };

  const handleUploadSuccess = () => {
    setFileListRefreshTrigger(prev => prev + 1);
  };

  const handleFileSelect = (file) => {
    setSelectedFileForPreview(file);
    // Exit fullscreen when file selection is cleared
    if (!file && isFullscreen) {
      setIsFullscreen(false);
    }
  };

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const preview = params.get('preview');
    if (preview) {
      setStandalonePreview(true);
      const aiFileName = `${preview}_AI.md`;
      fetch(apiUrl(`/api/download/${aiFileName}`))
        .then(async (res) => {
          if (!res.ok) throw new Error(`Failed to fetch analysis: ${res.status}`);
          return res.text();
        })
        .then((analysisContent) => {
          setSelectedFileForPreview({
            name: `${preview}.pdf`,
            analysisContent,
            displayType: 'analysis',
          });
          setIsFullscreen(true);
        })
        .catch(() => {
          setIsFullscreen(true);
        });
    }
  }, []);

  return (
    <div className={classes.root}>
      {standalonePreview && (
        <div className={classes.fullscreenOverlay}>
          <FilePreview 
            selectedFile={selectedFileForPreview} 
            isFullscreen={true}
            onToggleFullscreen={() => {}}
          />
        </div>
      )}

      {!standalonePreview && (
      <>
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

      {!isFullscreen && (
        <aside className={classes.sidebar} style={{ width: drawerWidth }}>
          <div className={classes.sidebarHeaderRow}>
            <span className={classes.sidebarTitle}>File Management</span>
            <Menu>
              <MenuTrigger disableButtonEnhancement>
                <FluentTooltip content="Font settings" relationship="label">
                  <Button
                    appearance="subtle"
                    size="small"
                    icon={<TextFont24Regular />}
                    aria-label="Font settings"
                  />
                </FluentTooltip>
              </MenuTrigger>
              <MenuPopover>
                <MenuList>
                  {Object.entries(fonts).length === 0 ? (
                    <MenuItem disabled>No fonts available</MenuItem>
                  ) : (
                    Object.entries(fonts).map(([key, font]) => (
                      <MenuItem
                        key={key}
                        onClick={() => handleFontChange(key)}
                        icon={selectedFontKey === key ? <Checkmark24Regular /> : null}
                      >
                        {font.name}
                      </MenuItem>
                    ))
                  )}
                </MenuList>
              </MenuPopover>
            </Menu>
          </div>
          <div className={classes.sidebarContent}>
            <FileUpload onUploadSuccess={handleUploadSuccess} />
            <FileList 
              onFileSelect={handleFileSelect} 
              refreshTrigger={fileListRefreshTrigger}
              selectedFile={selectedFileForPreview}
            />
          </div>
        </aside>
      )}

      {!isFullscreen && (
        <main
          className={classes.main}
          style={{
            width: `calc(100% - ${drawerWidth}px)`,
            marginLeft: `${drawerWidth}px`,
          }}
        >
          <div className={classes.toolbarSpacer} />
          <div className={classes.mainInner}>
            <FilePreview 
              selectedFile={selectedFileForPreview} 
              isFullscreen={isFullscreen}
              onToggleFullscreen={() => setIsFullscreen(!isFullscreen)}
            />
          </div>
        </main>
      )}

      {isFullscreen && (
        <div className={classes.fullscreenOverlay}>
          <FilePreview 
            selectedFile={selectedFileForPreview} 
            isFullscreen={isFullscreen}
            onToggleFullscreen={() => setIsFullscreen(!isFullscreen)}
          />
        </div>
      )}
      </>
      )}
    </div>
  );
};

// Main App component that provides the theme context
function App(props) {
  return (
    <AppContent {...props} />
  );
}

export default App;
