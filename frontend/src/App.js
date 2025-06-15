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
// ThemeToggle removed as we're using only light theme
import { ThemeProvider, useTheme } from './contexts/ThemeContext';
import { appTheme } from './theme/themeConfig';

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
  
  // Using only light theme with spinner animation
  const currentTheme = useMemo(() => {
    return {
      ...appTheme,
      components: {
        ...appTheme.components,
        MuiCssBaseline: {
          styleOverrides: {
            '@global': {
              ...spinAnimation
            },
          },
        },
      }
    };
  }, []);

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
            background: 'linear-gradient(to right, #2193b0, #6dd5ed)',
            borderBottom: '1px solid rgba(0, 0, 0, 0.05)'
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
            {/* Theme toggle removed as we're using only light theme */}
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
              background: '#ffffff',
              borderRight: '1px solid #e0e0e0',
              transition: 'width 225ms cubic-bezier(0.4, 0, 0.6, 1) 0ms',
              overflow: 'hidden',
              boxShadow: '2px 0 8px rgba(0, 0, 0, 0.05)',
            },
          }}
        >
          <Toolbar /> {/* Spacer to offset content below AppBar */}
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
              fontWeight: 600,
              color: '#1a1a1a',
              fontSize: '1.1rem'
            }}>
              File Management
            </Typography>
            <IconButton
              onClick={() => setSidebarCollapsed(true)}
              size="small"
              sx={{
                color: '#666',
                '&:hover': {
                  backgroundColor: 'rgba(0,0,0,0.04)',
                }
              }}
            >
              <ChevronLeftIcon fontSize="small" />
            </IconButton>
          </Box>
          <Box sx={{ 
            overflow: 'auto', 
            px: 2,
            pb: 2,
            display: 'flex', 
            flexDirection: 'column', 
            gap: 3,
            '&::-webkit-scrollbar': {
              width: '6px',
            },
            '&::-webkit-scrollbar-track': {
              background: '#f1f1f1',
            },
            '&::-webkit-scrollbar-thumb': {
              background: '#c1c1c1',
              borderRadius: '3px',
              '&:hover': {
                background: '#a8a8a8',
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
              backgroundColor: '#e0e0e0',
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
            background: 'linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%)',
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
