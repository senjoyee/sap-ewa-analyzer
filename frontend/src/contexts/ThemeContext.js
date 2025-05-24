import React, { createContext, useContext } from 'react';

// Create the theme context
const ThemeContext = createContext();

// Theme provider component - simplified to only use light theme
export const ThemeProvider = ({ children }) => {
  // Fixed light theme
  const theme = 'light';
  
  // For backwards compatibility, providing empty functions
  const toggleTheme = () => {};
  const setSpecificTheme = () => {};

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

