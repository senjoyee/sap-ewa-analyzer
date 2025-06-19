import { createTheme } from '@mui/material/styles';

// Dark/Black Theme configuration
export const appTheme = createTheme({
  palette: {
    mode: 'dark',
    primary: {
      main: '#ffffff',
      light: '#f5f5f5',
      dark: '#e0e0e0',
    },
    secondary: {
      main: '#bb86fc',
      light: '#d4a8ff',
      dark: '#a266ff',
    },
    background: {
      default: '#000000',
      paper: '#121212',
    },
    text: {
      primary: '#ffffff',
      secondary: 'rgba(255, 255, 255, 0.7)',
      disabled: 'rgba(255, 255, 255, 0.38)',
    },
    divider: 'rgba(255, 255, 255, 0.12)',
  },
  shape: {
    borderRadius: 8,
  },
  typography: {
    fontFamily: '"Noto Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
    h1: { fontWeight: 500, color: '#ffffff' },
    h2: { fontWeight: 500, color: '#ffffff' },
    h3: { fontWeight: 500, color: '#ffffff' },
    h4: { fontWeight: 500, color: '#ffffff' },
    h5: { fontWeight: 500, color: '#ffffff' },
    h6: { fontWeight: 500, color: '#ffffff' },
    button: { fontWeight: 500 },
  },
  components: {
    MuiTableCell: {
      styleOverrides: {
        root: {
          fontFamily: '"Noto Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
          color: '#ffffff',
          borderColor: 'rgba(255, 255, 255, 0.12)',
        }
      }
    },
    MuiAppBar: {
      styleOverrides: {
        root: {
          backgroundImage: 'linear-gradient(to right, #1a1a1a, #333333)',
          backgroundColor: '#000000',
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundImage: 'none',
          backgroundColor: '#121212',
        },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: {
          '&:hover': {
            backgroundColor: 'rgba(255, 255, 255, 0.08)',
          },
        },
      },
    },
  },
});
