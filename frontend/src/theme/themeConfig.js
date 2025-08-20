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

// Microsoft Teams Theme factory
// mode: 'light' | 'dark' | 'contrast'
export const createTeamsTheme = (mode = 'light') => {
  if (mode === 'dark') {
    return createTheme({
      palette: {
        mode: 'dark',
        primary: {
          main: '#8B8CC7', // Teams brand tint for dark
          light: '#A6A7D6',
          dark: '#6B6DA7',
          contrastText: '#000000',
        },
        secondary: {
          main: '#5B5FC7',
        },
        background: {
          default: '#1F1F1F',
          paper: '#252423',
        },
        text: {
          primary: '#FFFFFF',
          secondary: '#D4D4D4',
        },
        divider: '#3D3D3D',
      },
      typography: {
        fontFamily: '"Segoe UI", system-ui, -apple-system, Roboto, Arial, sans-serif',
      },
      components: {
        MuiAppBar: {
          styleOverrides: {
            root: {
              backgroundImage: 'none',
              backgroundColor: '#2B2B2B',
              boxShadow: '0 1px 3px rgba(0,0,0,0.4)',
            },
          },
        },
      },
    });
  }

  if (mode === 'contrast') {
    return createTheme({
      palette: {
        mode: 'dark',
        primary: {
          main: '#FFD335', // High contrast accent
          contrastText: '#000000',
        },
        secondary: {
          main: '#FFFFFF',
        },
        background: {
          default: '#000000',
          paper: '#000000',
        },
        text: {
          primary: '#FFFFFF',
          secondary: '#FFD335',
        },
        divider: '#FFFFFF',
      },
      typography: {
        fontFamily: '"Segoe UI", system-ui, -apple-system, Roboto, Arial, sans-serif',
      },
    });
  }

  // Default to Teams light
  return createTheme({
    palette: {
      mode: 'light',
      primary: {
        main: '#6264A7', // Teams brand
        light: '#8B8CC7',
        dark: '#464775',
        contrastText: '#ffffff',
      },
      secondary: {
        main: '#464775',
      },
      background: {
        default: '#F3F2F1', // Fluent neutral
        paper: '#FFFFFF',
      },
      text: {
        primary: '#201F1E',
        secondary: '#605E5C',
      },
      divider: 'rgba(0,0,0,0.12)',
    },
    typography: {
      fontFamily: '"Segoe UI", system-ui, -apple-system, Roboto, Arial, sans-serif',
    },
    components: {
      MuiAppBar: {
        styleOverrides: {
          root: {
            backgroundImage: 'none',
            backgroundColor: '#6264A7',
            boxShadow: '0 1px 3px rgba(0,0,0,0.12)',
          },
        },
      },
    },
  });
};
