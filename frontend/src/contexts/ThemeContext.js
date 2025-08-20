import React, { createContext, useContext, useEffect, useState } from 'react';

// Create the theme context
const ThemeContext = createContext();

// Theme provider component with Teams detection via URL (?theme=light|dark|contrast)
export const ThemeProvider = ({ children }) => {
  // Modes: 'sap', 'teams-light', 'teams-dark', 'teams-contrast'
  const [theme, setTheme] = useState('sap');

  useEffect(() => {
    try {
      const params = new URLSearchParams(window.location.search || '');
      const themeParam = (params.get('theme') || '').toLowerCase();
      if (themeParam === 'dark') {
        setTheme('teams-dark');
      } else if (themeParam === 'contrast' || themeParam === 'high-contrast') {
        setTheme('teams-contrast');
      } else if (themeParam === 'light') {
        setTheme('teams-light');
      } else {
        // default stays SAP Belize
        setTheme('sap');
      }
    } catch (e) {
      setTheme('sap');
    }
  }, []);

  const toggleTheme = () => {
    setTheme((prev) => (prev.startsWith('teams') ? 'sap' : 'teams-light'));
  };

  const setSpecificTheme = (mode) => {
    // Guard: only allow supported modes
    const allowed = ['sap', 'teams-light', 'teams-dark', 'teams-contrast'];
    if (allowed.includes(mode)) {
      setTheme(mode);
    }
  };

  return (
    <ThemeContext.Provider value={{ theme, toggleTheme, setSpecificTheme }}>
      {children}
    </ThemeContext.Provider>
  );
};

// Custom hook to use the theme context
export const useTheme = () => {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('useTheme must be used within a ThemeProvider');
  }
  return context;
};

