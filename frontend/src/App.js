import React, { useState, useMemo } from 'react';
import { ThemeProvider as MuiThemeProvider } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import Box from '@mui/material/Box';
import MuiToolbar from '@mui/material/Toolbar';
import Typography from '@mui/material/Typography';
import IconButton from '@mui/material/IconButton';
import { Toolbar as FluentToolbar, ToolbarButton, Tooltip as FluentTooltip } from '@fluentui/react-components';
import { Document24Regular, Settings24Regular, QuestionCircle24Regular, ChevronLeft24Regular, ChevronRight24Regular } from '@fluentui/react-icons';

import FileUpload from './components/FileUpload';
import FileList from './components/FileList';
import FilePreview from './components/FilePreview';
// ThemeToggle removed as we're using only light theme
import { ThemeProvider, useTheme } from './contexts/ThemeContext';
import { appTheme, createTeamsTheme } from './theme/themeConfig';

// Add a keyframe animation for the spinning loader
const spinAnimation = {
  '@keyframes spin': {
    '0%': {
      transform: 'rotate(0deg)',
    },
    '100%': {
      transform: 'rotate(360deg)',
    },
  },
};
const drawerWidth = 480; // Increased width to accommodate analyze buttons and status and show more file details
const collapsedDrawerWidth = 0; // Width when drawer is collapsed

// Inner App component that uses the theme context
const AppContent = () => {
  const [selectedFileForPreview, setSelectedFileForPreview] = useState(null);
  const [fileListRefreshTrigger, setFileListRefreshTrigger] = useState(0);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const { theme: themeMode } = useTheme(); // Renamed to avoid conflicts with MUI theme parameter
  
  // Pick SAP Belize or Microsoft Teams themes based on ThemeContext
  const currentTheme = useMemo(() => {
    const mode = themeMode;
    const baseTheme = mode === 'sap'
      ? appTheme
      : createTeamsTheme(mode === 'teams-dark' ? 'dark' : mode === 'teams-contrast' ? 'contrast' : 'light');

    return {
      ...baseTheme,
      components: {
        ...baseTheme.components,
        MuiCssBaseline: {
          styleOverrides: {
            '@global': {
              ...spinAnimation,
            },
          },
        },
      },
    };
  }, [themeMode]);

  const handleUploadSuccess = () => {
    setFileListRefreshTrigger(prev => prev + 1);
  };

  return (
    <MuiThemeProvider theme={currentTheme}>
      <Box sx={{ display: 'flex', height: '100vh' }}>
        <CssBaseline />
        <Box 
          sx={{ 
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            zIndex: (muiTheme) => muiTheme.zIndex.drawer + 1,
            background: (muiTheme) => muiTheme.palette.primary.main,
            borderBottom: (muiTheme) => `1px solid ${muiTheme.palette.divider}`
          }}
        >
          <Box sx={{ px: 2, py: 1, color: (muiTheme) => muiTheme.palette.primary.contrastText }}>
            <FluentToolbar>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'inherit' }}>
                <Document24Regular />
                <Typography variant="h6" noWrap component="div" sx={{ color: (muiTheme) => muiTheme.palette.primary.contrastText, fontWeight: 400 }}>
                  EWA Analyzer
                </Typography>
              </div>
              <div style={{ flex: 1 }} />
              <FluentTooltip content="Settings" relationship="label">
                <ToolbarButton aria-label="Settings" icon={<Settings24Regular />} />
              </FluentTooltip>
              <FluentTooltip content="Help" relationship="label">
                <ToolbarButton aria-label="Help" icon={<QuestionCircle24Regular />} />
              </FluentTooltip>
            </FluentToolbar>
          </Box>
        </Box>
        
        <Box
          component="aside"
          role="complementary"
          sx={{
            width: sidebarCollapsed ? collapsedDrawerWidth : drawerWidth,
            flexShrink: 0,
            transition: 'width 225ms cubic-bezier(0.4, 0, 0.6, 1) 0ms',
            height: '100vh',
            boxSizing: 'border-box',
            background: (muiTheme) => muiTheme.palette.background.paper,
            borderRight: (muiTheme) => `1px solid ${muiTheme.palette.divider}`,
            overflow: 'hidden',
            boxShadow: '0 1px 4px rgba(0, 0, 0, 0.1)',
            color: (muiTheme) => muiTheme.palette.text.primary,
          }}
        >
          <MuiToolbar /> {/* Spacer to offset content below top bar */}
          {/* Collapse button */}
          <Box sx={{ 
            display: 'flex', 
            justifyContent: 'space-between', 
            alignItems: 'center',
            px: 2, 
            pt: 2,
            pb: 1
          }}>
            <Typography variant="h6" sx={{ 
              fontWeight: 500,
              color: (muiTheme) => muiTheme.palette.text.primary,
              fontSize: '1.1rem'
            }}>
              File Management
            </Typography>
            <IconButton
              onClick={() => setSidebarCollapsed(true)}
              size="small"
              sx={{
                color: (muiTheme) => muiTheme.palette.text.secondary,
                '&:hover': {
                  backgroundColor: (muiTheme) => muiTheme.palette.action.hover,
                }
              }}>
              <ChevronLeft24Regular />
            </IconButton>
          </Box>
          <Box sx={{ 
            overflow: 'auto', 
            px: 2,
            pb: 2,
            display: 'flex', 
            flexDirection: 'column', 
            gap: 3,
            background: (muiTheme) => muiTheme.palette.background.paper,
            '&::-webkit-scrollbar': {
              width: '6px',
            },
            '&::-webkit-scrollbar-track': {
              background: (muiTheme) => muiTheme.palette.background.default,
            },
            '&::-webkit-scrollbar-thumb': {
              background: (muiTheme) => muiTheme.palette.divider,
              borderRadius: '3px',
              '&:hover': {
                background: (muiTheme) => muiTheme.palette.text.secondary,
              },
            },
          }}>
            <FileUpload onUploadSuccess={handleUploadSuccess} />
            <FileList 
              onFileSelect={setSelectedFileForPreview} 
              refreshTrigger={fileListRefreshTrigger}
              selectedFile={selectedFileForPreview}
            />
          </Box>
        </Box>
        
        {/* Toggle button for sidebar collapse that appears on the edge of the screen when sidebar is collapsed */}
        {sidebarCollapsed && (
          <Box
            sx={{
              position: 'fixed',
              top: '50%',
              left: 0,
              zIndex: 1200,
              transform: 'translateY(-50%)',
              backgroundColor: (muiTheme) => muiTheme.palette.primary.main,
              borderRadius: '0 4px 4px 0',
              boxShadow: '2px 0 8px rgba(0,0,0,0.5)',
              transition: 'left 225ms cubic-bezier(0.4, 0, 0.6, 1) 0ms',
            }}
          >
            <IconButton
              onClick={() => setSidebarCollapsed(false)}
              size="small"
              sx={{ borderRadius: '0 4px 4px 0', padding: '12px 4px', color: (muiTheme) => muiTheme.palette.primary.contrastText }}
            >
              <ChevronRight24Regular />
            </IconButton>
          </Box>
        )}
        
        <Box
          component="main"
          sx={{
            flexGrow: 1,
            p: 3,
            width: `calc(100% - ${sidebarCollapsed ? collapsedDrawerWidth : drawerWidth}px)`,
            display: 'flex',
            flexDirection: 'column',
            background: (muiTheme) => muiTheme.palette.background.default,
            transition: 'width 225ms cubic-bezier(0.4, 0, 0.6, 1) 0ms, margin 225ms cubic-bezier(0.4, 0, 0.6, 1) 0ms',
          }}
        >
          <MuiToolbar /> {/* Spacer to offset content below top bar */}
          <Box sx={{flexGrow: 1, height: '100%', display: 'flex', alignItems: 'stretch'}}>
             <FilePreview selectedFile={selectedFileForPreview} />
          </Box>
        </Box>
      </Box>
    </MuiThemeProvider>
  );
};

// Main App component that provides the theme context
function App() {
  return (
    <ThemeProvider>
      <AppContent />
    </ThemeProvider>
  );
}

export default App;
