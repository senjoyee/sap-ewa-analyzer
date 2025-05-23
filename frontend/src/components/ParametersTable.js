import React, { useState, useEffect } from 'react';
import { 
  Box, 
  Paper, 
  Typography,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Chip
} from '@mui/material';
import PriorityHighIcon from '@mui/icons-material/PriorityHigh';
import ArrowDownwardIcon from '@mui/icons-material/ArrowDownward';
import ArrowUpwardIcon from '@mui/icons-material/ArrowUpward';
import { useTheme } from '../contexts/ThemeContext';

// Helper function to render impact indicators with appropriate icons and colors
const ImpactIndicator = ({ impact }) => {
  let icon, label, color;

  switch(impact.toLowerCase()) {
    case 'high':
      icon = <PriorityHighIcon />;
      label = 'High';
      color = 'error';
      break;
    case 'medium':
      icon = <ArrowUpwardIcon />;
      label = 'Medium';
      color = 'warning';
      break;
    case 'low':
      icon = <ArrowDownwardIcon />;
      label = 'Low';
      color = 'info';
      break;
    default:
      icon = <ArrowUpwardIcon />;
      label = 'Unknown';
      color = 'default';
  }

  return (
    <Chip
      icon={icon}
      label={label}
      color={color}
      size="small"
      variant="filled"
      sx={{ minWidth: '90px' }}
    />
  );
};

const ParametersTable = ({ parametersData }) => {
  const { theme } = useTheme();
  const isDark = theme === 'dark';
  const [error, setError] = useState(null);
  
  // Validate parameters data structure
  useEffect(() => {
    try {
      if (!parametersData) {
        return;
      }
      
      if (!parametersData.parameters || !Array.isArray(parametersData.parameters)) {
        throw new Error('Invalid parameters data format: "parameters" property missing or not an array');
      }
      
      // Check if all parameters have the required properties
      const requiredProps = ['name', 'current', 'recommended', 'impact', 'description'];
      const invalidParameters = parametersData.parameters.filter(param => 
        !param || typeof param !== 'object' || requiredProps.some(prop => !(prop in param))
      );
      
      if (invalidParameters.length > 0) {
        console.warn(`Found ${invalidParameters.length} invalid parameters`, invalidParameters);
      }
      
      setError(null);
    } catch (err) {
      console.error('Error validating parameters data:', err);
      setError(err.message);
    }
  }, [parametersData]);
  
  if (error) {
    return (
      <Box sx={{ my: 2, p: 2, borderRadius: 2, bgcolor: isDark ? 'rgba(244, 67, 54, 0.1)' : 'rgba(244, 67, 54, 0.05)', border: '1px solid rgba(244, 67, 54, 0.3)' }}>
        <Typography variant="subtitle1" color="error">
          Error in parameters data: {error}
        </Typography>
      </Box>
    );
  }
  
  if (!parametersData || !parametersData.parameters || parametersData.parameters.length === 0) {
    return (
      <Box sx={{ my: 2, p: 2, borderRadius: 2, bgcolor: 'background.paper' }}>
        <Typography variant="subtitle1" color="text.secondary">
          No parameter recommendations available
        </Typography>
      </Box>
    );
  }

  // Group parameters by category
  const parametersByCategory = {};
  parametersData.parameters.forEach(param => {
    const category = param.category || 'Uncategorized';
    if (!parametersByCategory[category]) {
      parametersByCategory[category] = [];
    }
    parametersByCategory[category].push(param);
  });

  return (
    <Box sx={{ width: '100%', mb: 4 }}>
      <Typography variant="h5" component="h2" gutterBottom sx={{ 
        fontWeight: 600, 
        color: 'primary.main', 
        display: 'flex',
        alignItems: 'center',
        mb: 3,
        mt: 2
      }}>
        Recommended Parameters
      </Typography>

      {Object.entries(parametersByCategory).map(([category, parameters]) => (
        <Box key={category} sx={{ mb: 4 }}>
          <Typography variant="h6" gutterBottom sx={{ fontWeight: 500, color: 'text.primary', mb: 2 }}>
            {category}
          </Typography>
          
          <TableContainer 
            component={Paper} 
            elevation={2}
            sx={{ 
              borderRadius: 2,
              overflow: 'hidden',
              border: isDark ? '1px solid rgba(255, 255, 255, 0.12)' : '1px solid rgba(0, 0, 0, 0.12)',
            }}
          >
            <Table sx={{ minWidth: 650 }} aria-label={`${category} parameters table`}>
              <TableHead>
                <TableRow sx={{ 
                  bgcolor: isDark ? 'rgba(97, 97, 255, 0.15)' : 'rgba(63, 81, 181, 0.08)',
                }}>
                  <TableCell 
                    sx={{ 
                      fontWeight: 600, 
                      fontSize: '0.9rem', 
                      color: isDark ? 'rgba(255, 255, 255, 0.95)' : 'rgba(0, 0, 0, 0.85)',
                      width: '20%'
                    }}
                  >
                    Parameter
                  </TableCell>
                  <TableCell 
                    sx={{ 
                      fontWeight: 600, 
                      fontSize: '0.9rem',
                      color: isDark ? 'rgba(255, 255, 255, 0.95)' : 'rgba(0, 0, 0, 0.85)',
                      width: '15%'
                    }}
                  >
                    Current Value
                  </TableCell>
                  <TableCell 
                    sx={{ 
                      fontWeight: 600, 
                      fontSize: '0.9rem',
                      color: isDark ? 'rgba(255, 255, 255, 0.95)' : 'rgba(0, 0, 0, 0.85)',
                      width: '15%'
                    }}
                  >
                    Recommended
                  </TableCell>
                  <TableCell 
                    align="center"
                    sx={{ 
                      fontWeight: 600, 
                      fontSize: '0.9rem',
                      color: isDark ? 'rgba(255, 255, 255, 0.95)' : 'rgba(0, 0, 0, 0.85)',
                      width: '15%'
                    }}
                  >
                    Impact
                  </TableCell>
                  <TableCell 
                    sx={{ 
                      fontWeight: 600, 
                      fontSize: '0.9rem',
                      color: isDark ? 'rgba(255, 255, 255, 0.95)' : 'rgba(0, 0, 0, 0.85)',
                      width: '35%'
                    }}
                  >
                    Description
                  </TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {parameters.map((param, index) => (
                  <TableRow
                    key={index}
                    sx={{ 
                      '&:nth-of-type(even)': { 
                        bgcolor: isDark ? 'rgba(255, 255, 255, 0.03)' : 'rgba(0, 0, 0, 0.03)' 
                      },
                      '&:hover': {
                        bgcolor: isDark ? 'rgba(255, 255, 255, 0.08)' : 'rgba(0, 0, 0, 0.08)'
                      }
                    }}
                  >
                    <TableCell 
                      component="th" 
                      scope="row"
                      sx={{ 
                        fontFamily: 'monospace',
                        fontWeight: 600,
                        fontSize: '0.85rem'
                      }}
                    >
                      {param.name}
                    </TableCell>
                    <TableCell sx={{ fontFamily: 'monospace', fontSize: '0.85rem' }}>
                      {param.current}
                    </TableCell>
                    <TableCell sx={{ 
                      fontFamily: 'monospace', 
                      fontSize: '0.85rem',
                      fontWeight: 600,
                      color: param.current !== param.recommended ? 
                        (isDark ? 'success.light' : 'success.dark') : 
                        'text.primary'
                    }}>
                      {param.recommended}
                    </TableCell>
                    <TableCell align="center">
                      <ImpactIndicator impact={param.impact} />
                    </TableCell>
                    <TableCell sx={{ fontSize: '0.85rem' }}>
                      {param.description}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Box>
      ))}
    </Box>
  );
};

export default ParametersTable;
