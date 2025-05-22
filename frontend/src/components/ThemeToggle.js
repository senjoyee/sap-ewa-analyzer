import React from 'react';
import IconButton from '@mui/material/IconButton';
import Tooltip from '@mui/material/Tooltip';
import Brightness4Icon from '@mui/icons-material/Brightness4';
import Brightness7Icon from '@mui/icons-material/Brightness7';
import { useTheme } from '../contexts/ThemeContext';

const ThemeToggle = () => {
  const { theme, toggleTheme } = useTheme();
  
  return (
    <Tooltip title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}>
      <IconButton
        onClick={toggleTheme}
        color="inherit"
        size="small"
        sx={{
          transition: 'transform 0.3s',
          '&:hover': {
            transform: 'rotate(12deg)',
          },
        }}
      >
        {theme === 'dark' ? (
          <Brightness7Icon fontSize="small" />
        ) : (
          <Brightness4Icon fontSize="small" />
        )}
      </IconButton>
    </Tooltip>
  );
};

export default ThemeToggle;
