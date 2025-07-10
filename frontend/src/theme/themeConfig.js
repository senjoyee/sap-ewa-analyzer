import { createTheme } from '@mui/material/styles';

// SAP Belize Theme configuration
export const appTheme = createTheme({
  palette: {
    mode: 'light',
    primary: {
      main: '#0070b1', // SAP Belize primary blue
      light: '#408ac7',
      dark: '#004a80',
    },
    secondary: {
      main: '#6a6d70', // SAP neutral gray
      light: '#899395',
      dark: '#32363a',
    },
    background: {
      default: '#f5f5f5', // SAP light background
      paper: '#ffffff',
    },
    text: {
      primary: '#32363a', // SAP text color
      secondary: '#6a6d70',
      disabled: 'rgba(0, 0, 0, 0.38)',
    },
    divider: 'rgba(0, 0, 0, 0.12)',
  },
  shape: {
    borderRadius: 4, // SAP uses less rounded corners
  },
  typography: {
    fontFamily: '"72", "72-Regular", "Noto Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
    fontSize: 14,
    h1: { fontWeight: 400, color: '#32363a' },
    h2: { fontWeight: 400, color: '#32363a' },
    h3: { fontWeight: 400, color: '#32363a' },
    h4: { fontWeight: 400, color: '#32363a' },
    h5: { fontWeight: 400, color: '#32363a' },
    h6: { fontWeight: 400, color: '#32363a' },
    button: { fontWeight: 400 },
  },
  components: {
    MuiTableCell: {
      styleOverrides: {
        root: {
          fontFamily: '"72", "72-Regular", "Noto Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
          color: '#32363a',
          borderColor: '#e5e5e5',
        }
      }
    },
    MuiAppBar: {
      styleOverrides: {
        root: {
          backgroundImage: 'none',
          backgroundColor: '#0070b1', // SAP blue header
          boxShadow: '0 1px 3px rgba(0,0,0,0.12)',
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundImage: 'none',
          backgroundColor: '#ffffff',
        },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: {
          textTransform: 'none', // SAP buttons don't use all caps
          borderRadius: 4,
          '&:hover': {
            backgroundColor: 'rgba(0, 112, 177, 0.08)', // Light blue hover
          },
        },
        contained: {
          boxShadow: 'none', // SAP buttons have minimal/no shadows
          '&:hover': {
            boxShadow: '0 1px 3px rgba(0,0,0,0.12)',
          }
        }
      },
    },
  },
});
