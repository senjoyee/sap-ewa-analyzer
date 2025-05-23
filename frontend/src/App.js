import React, { useState, useMemo } from 'react';
import { ThemeProvider as MuiThemeProvider } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import Box from '@mui/material/Box';
import Drawer from '@mui/material/Drawer';
import AppBar from '@mui/material/AppBar';
import Toolbar from '@mui/material/Toolbar';
import Typography from '@mui/material/Typography';
import Container from '@mui/material/Container';
import Grid from '@mui/material/Grid';
import IconButton from '@mui/material/IconButton';
import Tooltip from '@mui/material/Tooltip';
import DescriptionIcon from '@mui/icons-material/Description';
import SettingsIcon from '@mui/icons-material/Settings';
import HelpOutlineIcon from '@mui/icons-material/HelpOutline';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';

import FileUpload from './components/FileUpload';
import FileList from './components/FileList';
import FilePreview from './components/FilePreview';
import ThemeToggle from './components/ThemeToggle';
import { ThemeProvider, useTheme } from './contexts/ThemeContext';
import { lightTheme, darkTheme } from './theme/themeConfig';

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
const drawerWidth = 380; // Increased width to accommodate analyze buttons and status
const collapsedDrawerWidth = 0; // Width when drawer is collapsed

// Inner App component that uses the theme context
const AppContent = () => {
  const [selectedFileForPreview, setSelectedFileForPreview] = useState(null);
  const [fileListRefreshTrigger, setFileListRefreshTrigger] = useState(0);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const { theme: themeMode } = useTheme(); // Renamed to avoid conflicts with MUI theme parameter
  
  // Dynamically select theme based on theme context
  const currentTheme = useMemo(() => {
    // Add the spinner animation to whichever theme is active
    if (themeMode === 'dark') {
      return {
        ...darkTheme,
        components: {
          ...darkTheme.components,
          MuiCssBaseline: {
            styleOverrides: {
              '@global': {
                ...spinAnimation
              },
            },
          },
        }
      };
    } else {
      return {
        ...lightTheme,
        components: {
          ...lightTheme.components,
          MuiCssBaseline: {
            styleOverrides: {
              '@global': {
                ...spinAnimation
              },
            },
          },
        }
      };
    }
  }, [themeMode]);

  const handleUploadSuccess = () => {
    setFileListRefreshTrigger(prev => prev + 1);
  };

  return (
    <MuiThemeProvider theme={currentTheme}>
      <Box sx={{ display: 'flex', height: '100vh' }}>
        <CssBaseline />
        <AppBar
          position="fixed"
          elevation={0}
          sx={{ 
            zIndex: (muiTheme) => muiTheme.zIndex.drawer + 1,
            background: themeMode === 'dark' 
              ? 'linear-gradient(to right, #1A1A1A, #2C2C2C)'
              : 'linear-gradient(to right, #2193b0, #6dd5ed)',
            borderBottom: themeMode === 'dark'
              ? '1px solid rgba(255, 255, 255, 0.05)'
              : '1px solid rgba(0, 0, 0, 0.05)'
          }}
        >
          <Toolbar>
            <Box sx={{ display: 'flex', alignItems: 'center' }}>
              <DescriptionIcon sx={{ mr: 1.5 }} />
              <Typography variant="h6" noWrap component="div">
                EWA Analyzer
              </Typography>
            </Box>
            <Box sx={{ flexGrow: 1 }} />
            <ThemeToggle />
            <Tooltip title="Settings">
              <IconButton color="inherit">
                <SettingsIcon />
              </IconButton>
            </Tooltip>
            <Tooltip title="Help">
              <IconButton color="inherit">
                <HelpOutlineIcon />
              </IconButton>
            </Tooltip>
          </Toolbar>
        </AppBar>
        
        <Drawer
          variant="permanent"
          sx={{
            width: sidebarCollapsed ? collapsedDrawerWidth : drawerWidth,
            flexShrink: 0,
            transition: 'width 225ms cubic-bezier(0.4, 0, 0.6, 1) 0ms',
            [`& .MuiDrawer-paper`]: {
              width: sidebarCollapsed ? collapsedDrawerWidth : drawerWidth,
              boxSizing: 'border-box',
              background: themeMode === 'dark'
                ? 'linear-gradient(180deg, #1A1A1A 0%, #222222 100%)'
                : 'linear-gradient(180deg, #f5f5f5 0%, #e0e0e0 100%)',
              borderRight: themeMode === 'dark'
                ? '1px solid rgba(255, 255, 255, 0.05)'
                : '1px solid rgba(0, 0, 0, 0.05)',
              transition: 'width 225ms cubic-bezier(0.4, 0, 0.6, 1) 0ms',
              overflow: 'hidden',
            },
          }}
        >
          <Toolbar /> {/* Spacer to offset content below AppBar */}
          {/* Collapse button */}
          <Box sx={{ display: 'flex', justifyContent: 'flex-end', pr: 1, mt: 1 }}>
            <IconButton
              onClick={() => setSidebarCollapsed(true)}
              size="small"
              sx={{
                backgroundColor: themeMode === 'dark' ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)',
                '&:hover': {
                  backgroundColor: themeMode === 'dark' ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)',
                }
              }}
            >
              <ChevronLeftIcon />
            </IconButton>
          </Box>
          <Box sx={{ overflow: 'auto', padding: 2, display: 'flex', flexDirection: 'column', gap: 2 }}>
            <FileUpload onUploadSuccess={handleUploadSuccess} />
            <FileList 
              onFileSelect={setSelectedFileForPreview} 
              refreshTrigger={fileListRefreshTrigger}
              selectedFile={selectedFileForPreview}
            />
          </Box>
        </Drawer>
        
        {/* Toggle button for sidebar collapse that appears on the edge of the screen when sidebar is collapsed */}
        {sidebarCollapsed && (
          <Box
            sx={{
              position: 'fixed',
              top: '50%',
              left: 0,
              zIndex: 1200,
              transform: 'translateY(-50%)',
              backgroundColor: themeMode === 'dark' ? '#2C2C2C' : '#e0e0e0',
              borderRadius: '0 4px 4px 0',
              boxShadow: '2px 0 8px rgba(0,0,0,0.15)',
              transition: 'left 225ms cubic-bezier(0.4, 0, 0.6, 1) 0ms',
            }}
          >
            <IconButton
              onClick={() => setSidebarCollapsed(false)}
              size="small"
              sx={{ borderRadius: '0 4px 4px 0', padding: '12px 4px' }}
            >
              <ChevronRightIcon />
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
            background: themeMode === 'dark'
              ? 'linear-gradient(135deg, #121212 0%, #1A1A1A 100%)'
              : 'linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%)',
            transition: 'width 225ms cubic-bezier(0.4, 0, 0.6, 1) 0ms, margin 225ms cubic-bezier(0.4, 0, 0.6, 1) 0ms',
          }}
        >
          <Toolbar /> {/* Spacer to offset content below AppBar */}
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
