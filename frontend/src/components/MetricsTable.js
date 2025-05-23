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
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorIcon from '@mui/icons-material/Error';
import WarningIcon from '@mui/icons-material/Warning';
import { useTheme } from '../contexts/ThemeContext';

// Helper function to render status indicators with appropriate icons and colors
const StatusIndicator = ({ status }) => {
  let icon, label, color;

  switch(status.toLowerCase()) {
    case 'success':
      icon = <CheckCircleIcon />;
      label = 'Good';
      color = 'success';
      break;
    case 'warning':
      icon = <WarningIcon />;
      label = 'Warning';
      color = 'warning';
      break;
    case 'critical':
      icon = <ErrorIcon />;
      label = 'Critical';
      color = 'error';
      break;
    default:
      icon = <WarningIcon />;
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

const MetricsTable = ({ metricsData }) => {
  const { theme } = useTheme();
  const isDark = theme === 'dark';
  const [error, setError] = useState(null);
  
  // Validate metrics data structure
  useEffect(() => {
    try {
      // Log the raw metrics data for debugging
      console.log('DEBUG - Raw metrics data in MetricsTable:', metricsData);
      console.log('DEBUG - Type of metrics data:', typeof metricsData);
      if (metricsData) {
        console.log('DEBUG - Keys in metrics data:', Object.keys(metricsData));
      }
      
      if (!metricsData) {
        return;
      }
      
      // Handle different data structures
      let metricsArray;
      if (Array.isArray(metricsData)) {
        // Direct array format
        console.log('DEBUG - Metrics is an array');
        metricsArray = metricsData;
      } else if (metricsData.metrics && Array.isArray(metricsData.metrics)) {
        // Object with metrics property
        console.log('DEBUG - Metrics is an object with metrics array property');
        metricsArray = metricsData.metrics;
      } else if (typeof metricsData === 'object') {
        // Try to extract metrics from the object structure
        console.log('DEBUG - Metrics is an object, attempting to extract metrics');
        
        // If it's an object with a data property that contains metrics
        if (metricsData.data && (Array.isArray(metricsData.data) || metricsData.data.metrics)) {
          metricsArray = Array.isArray(metricsData.data) ? metricsData.data : metricsData.data.metrics;
          console.log('DEBUG - Found metrics in data property:', metricsArray);
        }
        // If it has any property that looks like an array of metrics
        else {
          // Find the first property that's an array and might contain metrics
          const potentialMetricsProps = Object.keys(metricsData).filter(key => 
            Array.isArray(metricsData[key]) || 
            (typeof metricsData[key] === 'object' && metricsData[key]?.metrics)
          );
          
          if (potentialMetricsProps.length > 0) {
            const firstProp = potentialMetricsProps[0];
            metricsArray = Array.isArray(metricsData[firstProp]) ? 
              metricsData[firstProp] : 
              metricsData[firstProp].metrics;
            console.log(`DEBUG - Found metrics in ${firstProp} property:`, metricsArray);
          } else {
            // Last resort: treat the entire object as a single metrics entry
            // This is for backward compatibility with older data formats
            console.log('DEBUG - No array found, treating object as metrics');
            metricsArray = [metricsData];
          }
        }
      } else {
        throw new Error('Invalid metrics data format: expected array or object with "metrics" property');
      }
      
      console.log('DEBUG - Final metrics array to be displayed:', metricsArray);
      
      // Check if all metrics have the required properties
      const requiredProps = ['name', 'current', 'target', 'status'];
      const invalidMetrics = metricsArray.filter(metric => 
        !metric || typeof metric !== 'object' || requiredProps.some(prop => !(prop in metric))
      );
      
      if (invalidMetrics.length > 0) {
        console.warn(`Found ${invalidMetrics.length} invalid metrics`, invalidMetrics);
      }
      
      setError(null);
    } catch (err) {
      console.error('Error validating metrics data:', err);
      setError(err.message);
    }
  }, [metricsData]);
  
  if (error) {
    return (
      <Box sx={{ my: 2, p: 2, borderRadius: 2, bgcolor: isDark ? 'rgba(244, 67, 54, 0.1)' : 'rgba(244, 67, 54, 0.05)', border: '1px solid rgba(244, 67, 54, 0.3)' }}>
        <Typography variant="subtitle1" color="error">
          Error in metrics data: {error}
        </Typography>
      </Box>
    );
  }
  
  if (!metricsData) {
    return (
      <Box sx={{ my: 2, p: 2, borderRadius: 2, bgcolor: 'background.paper' }}>
        <Typography variant="subtitle1" color="text.secondary">
          No metrics data available
        </Typography>
      </Box>
    );
  }

  // Group metrics by category
  let metricsArray;
  
  // Determine the metrics array based on the structure
  if (Array.isArray(metricsData)) {
    // Direct array format
    metricsArray = metricsData;
  } else if (metricsData.metrics && Array.isArray(metricsData.metrics)) {
    // Object with metrics property
    metricsArray = metricsData.metrics;
  } else if (typeof metricsData === 'object') {
    // Handle potential nested structures
    if (metricsData.data && Array.isArray(metricsData.data)) {
      metricsArray = metricsData.data;
    } else if (metricsData.data && metricsData.data.metrics && Array.isArray(metricsData.data.metrics)) {
      metricsArray = metricsData.data.metrics;
    } else {
      // As a fallback, try to convert the object to an array if it has required properties
      const requiredProps = ['name', 'current', 'target', 'status'];
      if (requiredProps.every(prop => prop in metricsData)) {
        // If the object itself looks like a metric, wrap it in an array
        metricsArray = [metricsData];
      } else {
        // Last resort - empty array with error
        metricsArray = [];
        console.error('Could not extract metrics array from data:', metricsData);
      }
    }
  } else {
    // Fallback to empty array if no valid structure found
    metricsArray = [];
    console.error('Invalid metrics data format:', metricsData);
  }
  
  // Log the extracted metrics array
  console.log('Final metrics array for display:', metricsArray);
  
  // If we have no metrics after all this processing, show a message
  if (!metricsArray || metricsArray.length === 0) {
    return (
      <Box sx={{ my: 2, p: 2, borderRadius: 2, bgcolor: isDark ? 'rgba(244, 67, 54, 0.1)' : 'rgba(244, 67, 54, 0.05)', border: '1px solid rgba(244, 67, 54, 0.3)' }}>
        <Typography variant="subtitle1" color="error">
          No valid metrics found in the provided data
        </Typography>
      </Box>
    );
  }
  
  // Organize metrics by category
  const metricsByCategory = {};
  metricsArray.forEach(metric => {
    if (!metric || typeof metric !== 'object') return;
    
    // Skip any metrics that don't have the required properties
    const requiredProps = ['name', 'current', 'target', 'status'];
    if (!requiredProps.every(prop => prop in metric)) {
      console.warn('Skipping invalid metric:', metric);
      return;
    }
    
    const category = metric.category || 'Uncategorized';
    if (!metricsByCategory[category]) {
      metricsByCategory[category] = [];
    }
    metricsByCategory[category].push(metric);
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
        Key Metrics Summary
      </Typography>

      {Object.entries(metricsByCategory).map(([category, metrics]) => (
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
            <Table sx={{ minWidth: 650 }} aria-label={`${category} metrics table`}>
              <TableHead>
                <TableRow sx={{ 
                  bgcolor: isDark ? 'rgba(97, 97, 255, 0.15)' : 'rgba(63, 81, 181, 0.08)',
                }}>
                  <TableCell 
                    sx={{ 
                      fontWeight: 600, 
                      fontSize: '0.9rem', 
                      color: isDark ? 'rgba(255, 255, 255, 0.95)' : 'rgba(0, 0, 0, 0.85)',
                      width: '40%'
                    }}
                  >
                    Metric
                  </TableCell>
                  <TableCell 
                    sx={{ 
                      fontWeight: 600, 
                      fontSize: '0.9rem',
                      color: isDark ? 'rgba(255, 255, 255, 0.95)' : 'rgba(0, 0, 0, 0.85)',
                      width: '20%'
                    }}
                  >
                    Current Value
                  </TableCell>
                  <TableCell 
                    sx={{ 
                      fontWeight: 600, 
                      fontSize: '0.9rem',
                      color: isDark ? 'rgba(255, 255, 255, 0.95)' : 'rgba(0, 0, 0, 0.85)',
                      width: '20%'
                    }}
                  >
                    Target/Threshold
                  </TableCell>
                  <TableCell 
                    align="center"
                    sx={{ 
                      fontWeight: 600, 
                      fontSize: '0.9rem',
                      color: isDark ? 'rgba(255, 255, 255, 0.95)' : 'rgba(0, 0, 0, 0.85)',
                      width: '20%'
                    }}
                  >
                    Status
                  </TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {metrics.map((metric, index) => (
                  <TableRow
                    key={index}
                    sx={{ 
                      '&:nth-of-type(even)': { 
                        bgcolor: isDark ? 'rgba(255, 255, 255, 0.05)' : 'rgba(0, 0, 0, 0.02)' 
                      },
                      '&:hover': {
                        bgcolor: isDark ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.04)',
                        transition: 'background-color 0.2s'
                      }
                    }}
                  >
                    <TableCell 
                      component="th" 
                      scope="row"
                      sx={{ 
                        fontWeight: 500,
                        fontSize: '0.875rem',
                        py: 1.5
                      }}
                    >
                      {metric.name}
                    </TableCell>
                    <TableCell 
                      sx={{ 
                        fontFamily: 'monospace',
                        fontSize: '0.875rem',
                        py: 1.5,
                        fontWeight: metric.status === 'critical' ? 600 : 400,
                        color: metric.status === 'critical' ? 
                          (isDark ? '#ff6b6b' : '#d32f2f') : 
                          'inherit'
                      }}
                    >
                      {metric.current}
                    </TableCell>
                    <TableCell 
                      sx={{ 
                        fontFamily: 'monospace',
                        fontSize: '0.875rem',
                        py: 1.5
                      }}
                    >
                      {metric.target}
                    </TableCell>
                    <TableCell 
                      align="center"
                      sx={{ py: 1.5 }}
                    >
                      <StatusIndicator status={metric.status} />
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

export default MetricsTable;
