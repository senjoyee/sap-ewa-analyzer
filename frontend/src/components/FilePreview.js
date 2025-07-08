import React, { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import Paper from '@mui/material/Paper';
import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import Divider from '@mui/material/Divider';
import CircularProgress from '@mui/material/CircularProgress';
import Accordion from '@mui/material/Accordion';
import AccordionSummary from '@mui/material/AccordionSummary';
import AccordionDetails from '@mui/material/AccordionDetails';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import InsertDriveFileOutlinedIcon from '@mui/icons-material/InsertDriveFileOutlined';
import PictureAsPdfIcon from '@mui/icons-material/PictureAsPdf';
import ImageIcon from '@mui/icons-material/Image';
import DescriptionIcon from '@mui/icons-material/Description';
import TextSnippetIcon from '@mui/icons-material/TextSnippet';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import EqualizerIcon from '@mui/icons-material/Equalizer';
import AssessmentIcon from '@mui/icons-material/Assessment';
import TuneIcon from '@mui/icons-material/Tune';
import PictureAsPdfOutlinedIcon from '@mui/icons-material/PictureAsPdfOutlined';
import Tooltip from '@mui/material/Tooltip';
import IconButton from '@mui/material/IconButton';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableContainer from '@mui/material/TableContainer';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import { useTheme } from '../contexts/ThemeContext';

// Import our custom table components
// import MetricsTable from './MetricsTable';
// import ParametersTable from './ParametersTable';
import DocumentChat from './DocumentChat';

// Import the SAP logo
import sapLogo from '../logo/sap-3.svg';

// Helper function to get appropriate file type label and icon
const getFileTypeInfo = (fileName) => {
  if (!fileName || typeof fileName !== 'string') {
    return { icon: <InsertDriveFileOutlinedIcon />, label: 'UNKNOWN', color: 'default' };
  }
  
  // Extract extension safely
  let extension = '';
  if (fileName.includes('.')) {
    extension = fileName.split('.').pop().toLowerCase();
  }
  
  switch(extension) {
    case 'pdf':
      return { 
        icon: <PictureAsPdfIcon sx={{ color: '#F44336' }} />, 
        label: 'PDF',
        color: 'error' 
      };
    case 'jpg':
    case 'jpeg':
    case 'png':
    case 'gif':
    case 'bmp':
      return { 
        icon: <ImageIcon sx={{ color: '#29B6F6' }} />, 
        label: 'IMAGE',
        color: 'info' 
      };
    case 'doc':
    case 'docx':
      return { 
        icon: <DescriptionIcon sx={{ color: '#90CAF9' }} />, 
        label: 'DOCUMENT',
        color: 'primary' 
      };
    case 'txt':
      return { 
        icon: <TextSnippetIcon sx={{ color: '#CE93D8' }} />, 
        label: 'TEXT',
        color: 'secondary' 
      };
    default:
      return { 
        icon: <InsertDriveFileOutlinedIcon sx={{ color: '#9E9E9E' }} />, 
        label: extension ? extension.toUpperCase() : 'FILE',
        color: 'default' 
      };
  }
};

const JsonCodeBlockRenderer = ({ node, inline, className, children, ...props }) => {
  const match = /language-(\w+)/.exec(className || '');
  const lang = match && match[1];

  if (lang === 'json' && !inline) {
    try {
      const jsonString = String(children).replace(/\n$/, ''); // Remove trailing newline
      const jsonData = JSON.parse(jsonString);

      // Case 1: Check if it's the Key System Information format with items (parameter/value pairs)
      if (jsonData && jsonData.tableTitle && Array.isArray(jsonData.items)) {
        return (
          <Box sx={{ my: 2, boxShadow: 3, borderRadius: 2, overflow: 'hidden' }}>
            <Typography variant="h6" sx={{ 
              p: 2, 
              bgcolor: (theme) => theme.palette.mode === 'dark' ? 'primary.dark' : 'primary.light',
              color: (theme) => theme.palette.mode === 'dark' ? 'primary.contrastText' : 'primary.dark',
              fontWeight: 'bold'
            }}>
              {jsonData.tableTitle}
            </Typography>
            <TableContainer component={Paper} elevation={0}>
              <Table size="small" sx={{
                borderCollapse: 'collapse',
                tableLayout: 'auto',
                width: '100%',
                '& th, & td': {
                  borderRight: (theme) => `1px solid ${theme.palette.divider}`,
                  '&:last-child': {
                    borderRight: 'none'
                  }
                }
              }}>
                <TableHead>
                  <TableRow sx={{ bgcolor: (theme) => theme.palette.mode === 'dark' ? 'grey.800' : 'grey.100' }}>
                    <TableCell sx={{ 
                      fontWeight: 'bold', 
                      width: '40%', 
                      fontSize: '0.9rem',
                      borderBottom: (theme) => `2px solid ${theme.palette.primary.main}`,
                      paddingLeft: 2
                    }}>Parameter</TableCell>
                    <TableCell sx={{ 
                      fontWeight: 'bold', 
                      width: '60%', 
                      fontSize: '0.9rem',
                      borderBottom: (theme) => `2px solid ${theme.palette.primary.main}`,
                      paddingLeft: 2
                    }}>Value</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {jsonData.items.map((item, index) => {
                    // Determine if the value is numeric or short text
                    // We'll consider anything with alphanumeric content over 20 chars as long text
                    const isLongText = item.value.length > 20 && /[a-zA-Z]/.test(item.value);
                    const isNumericOrShort = !isLongText && (/^[\d.,\s%]+$/.test(item.value) || item.value.length < 10);
                    
                    return (
                      <TableRow key={index} sx={{ 
                        '&:nth-of-type(odd)': {
                          bgcolor: (theme) => theme.palette.mode === 'dark' ? 'rgba(255, 255, 255, 0.05)' : 'rgba(0, 0, 0, 0.02)'
                        },
                        '&:hover': {
                          bgcolor: (theme) => theme.palette.mode === 'dark' ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.04)'
                        }
                      }}>
                        <TableCell sx={{ fontWeight: 500, paddingLeft: 2 }}>{item.parameter}</TableCell>
                        <TableCell sx={{ 
                          textAlign: isNumericOrShort ? 'center' : 'left',
                          paddingLeft: isNumericOrShort ? 0 : 2
                        }}>{item.value}</TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </TableContainer>
          </Box>
        );
      }
      
      // Case 2: Check if it's our table structure with headers and rows
      else if (jsonData && jsonData.tableTitle && Array.isArray(jsonData.headers) && Array.isArray(jsonData.rows)) {
        return (
          <Box sx={{ my: 2, boxShadow: 3, borderRadius: 2, overflow: 'hidden' }}>
            <Typography variant="h6" sx={{ 
              p: 2, 
              bgcolor: (theme) => theme.palette.mode === 'dark' ? 'primary.dark' : 'primary.light',
              color: (theme) => theme.palette.mode === 'dark' ? 'primary.contrastText' : 'primary.dark',
              fontWeight: 'bold'
            }}>
              {jsonData.tableTitle}
            </Typography>
            <TableContainer component={Paper} elevation={0}>
              <Table size="small" sx={{
                borderCollapse: 'collapse',
                tableLayout: 'auto',
                width: '100%',
                '& th, & td': {
                  borderRight: (theme) => `1px solid ${theme.palette.divider}`,
                  '&:last-child': {
                    borderRight: 'none'
                  }
                }
              }}>
                <TableHead>
                  <TableRow sx={{ bgcolor: (theme) => theme.palette.mode === 'dark' ? 'grey.800' : 'grey.100' }}>
                    {jsonData.headers.map((header, index) => {
                      // Check if any cell in this column has long text content
                      const hasLongTextInColumn = jsonData.rows.some(row => {
                        const val = String(row[header] === undefined || row[header] === null ? '' : row[header]);
                        return val.length > 20 && /[a-zA-Z]/.test(val);
                      });
                      
                      // Determine if this is a numeric column header
                      const isNumericHeader = !hasLongTextInColumn && (
                        header.toLowerCase().includes('count') || 
                        header.toLowerCase().includes('value') ||
                        header.toLowerCase().includes('qty') ||
                        header.toLowerCase().includes('mhz') ||
                        header.toLowerCase().includes('cpus')
                      );

                      return (
                        <TableCell key={index} sx={{ 
                          fontWeight: 600,
                          fontSize: '0.8125rem',
                          fontFamily: '"Noto Sans", "Noto Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
                          color: (theme) => theme.palette.mode === 'dark' ? '#ffffff' : '#2d3748',
                          background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                          borderBottom: '2px solid transparent',
                          borderImage: 'linear-gradient(90deg, #667eea 0%, #764ba2 100%) 1',
                          textAlign: isNumericHeader ? 'center' : 'left',
                          paddingLeft: isNumericHeader ? 0 : 2,
                          padding: '16px 12px',
                          textTransform: 'uppercase',
                          letterSpacing: '0.08em',
                          position: 'relative',
                          transition: 'all 0.3s ease',
                          textShadow: '0 1px 2px rgba(0,0,0,0.3)',
                          '&:hover': {
                            color: '#ffffff',
                            transform: 'translateY(-1px)',
                            textShadow: '0 2px 4px rgba(0,0,0,0.4)',
                          },
                          // Make ID and name columns less wide
                          ...(header.toLowerCase().includes('id') && { maxWidth: '120px' }),
                          ...(header.toLowerCase().includes('name') && { maxWidth: '200px' }),
                          // Make numeric columns narrower
                          ...(isNumericHeader && { width: 'fit-content', minWidth: '90px' }),
                          '&::after': {
                            content: '""',
                            position: 'absolute',
                            bottom: 0,
                            left: 0,
                            right: 0,
                            height: '2px',
                            background: 'linear-gradient(90deg, transparent, #667eea, transparent)',
                            transform: 'scaleX(0)',
                            transition: 'transform 0.3s ease',
                          },
                          '&:hover::after': {
                            transform: 'scaleX(1)',
                          }
                        }}>
                          {header.charAt(0).toUpperCase() + header.slice(1).replace(/_/g, ' ')}
                        </TableCell>
                      );
                    })}
                  </TableRow>
                </TableHead>
                <TableBody>
                  {jsonData.rows.map((row, rowIndex) => (
                    <TableRow key={rowIndex} sx={{ 
                      '&:nth-of-type(odd)': {
                        bgcolor: (theme) => theme.palette.mode === 'dark' ? 'rgba(255, 255, 255, 0.05)' : 'rgba(0, 0, 0, 0.02)'
                      },
                      '&:hover': {
                        bgcolor: (theme) => theme.palette.mode === 'dark' ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.04)'
                      }
                    }}>
                      {jsonData.headers.map((header, cellIndex) => {
                        const cellValue = String(row[header] === undefined || row[header] === null ? '' : row[header]);
                        
                        // Check if any cell in this column has long text content
                        const hasLongTextInColumn = jsonData.rows.some(r => {
                          const val = String(r[header] === undefined || r[header] === null ? '' : r[header]);
                          return val.length > 20 && /[a-zA-Z]/.test(val);
                        });
                        
                        // Determine if this cell contains numeric data
                        const isNumeric = !hasLongTextInColumn && (
                          /^[\d.,\s%]+$/.test(cellValue) || 
                          header.toLowerCase().includes('count') || 
                          header.toLowerCase().includes('value') ||
                          header.toLowerCase().includes('qty') ||
                          header.toLowerCase().includes('mhz') ||
                          header.toLowerCase().includes('cpus')
                        );
                        
                        return (
                          <TableCell key={cellIndex} sx={{
                            ...(cellIndex === 0 && { fontWeight: 500 }),
                            textAlign: isNumeric ? 'center' : 'left',
                            paddingLeft: isNumeric ? 0 : 2,
                            // Truncate very long text
                            ...(cellValue.length > 50 && {
                              maxWidth: '300px',
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                              whiteSpace: 'nowrap'
                            })
                          }}>{cellValue}</TableCell>
                        );
                      })}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </Box>
        );
      }
      
      // Case 3: Special handling for Performance Indicators and other tables
      // This is for sections like 4.1 Performance Indicators shown in the screenshot
      else if (jsonData && typeof jsonData === 'object') {
        // Extract the first key as the title, assuming it's a proper table
        const tableTitle = Object.keys(jsonData)[0];
        const tableData = jsonData[tableTitle];
        
        // If we have an array of objects, render as a table
        if (Array.isArray(tableData)) {
          // Extract headers from the first item's keys
          const firstItem = tableData[0] || {};
          const headers = Object.keys(firstItem);
          
          if (headers.length > 0) {
            return (
              <Box sx={{ 
                my: 3, 
                borderRadius: 3,
                overflow: 'hidden',
                background: (theme) => theme.palette.mode === 'dark' 
                  ? 'linear-gradient(145deg, #1a1a1a 0%, #0a0a0a 100%)'
                  : 'linear-gradient(145deg, #ffffff 0%, #f5f5f5 100%)',
                boxShadow: (theme) => theme.palette.mode === 'dark'
                  ? '0 8px 32px 0 rgba(0, 0, 0, 0.5), 0 2px 8px 0 rgba(0, 0, 0, 0.3)'
                  : '0 8px 32px 0 rgba(31, 38, 135, 0.15), 0 2px 8px 0 rgba(31, 38, 135, 0.08)',
                border: (theme) => `1px solid ${theme.palette.mode === 'dark' ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.08)'}`,
                transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
                '&:hover': {
                  transform: 'translateY(-2px)',
                  boxShadow: (theme) => theme.palette.mode === 'dark'
                    ? '0 12px 40px 0 rgba(0, 0, 0, 0.6), 0 4px 12px 0 rgba(0, 0, 0, 0.4)'
                    : '0 12px 40px 0 rgba(31, 38, 135, 0.2), 0 4px 12px 0 rgba(31, 38, 135, 0.1)',
                }
              }}>
                <Typography variant="h6" sx={{ 
                  p: 2.5,
                  background: (theme) => theme.palette.mode === 'dark'
                    ? 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)'
                    : 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                  color: '#ffffff',
                  fontWeight: 600,
                  fontFamily: '"Noto Sans", "Noto Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
                  fontSize: '1.125rem',
                  letterSpacing: '0.5px',
                  textShadow: '0 1px 2px rgba(0,0,0,0.3)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 1,
                  '&::before': {
                    content: '""',
                    width: '4px',
                    height: '24px',
                    bgcolor: '#ffffff',
                    borderRadius: '2px',
                    opacity: 0.8,
                  }
                }}>
                  {tableTitle}
                </Typography>
                <TableContainer sx={{ 
                  maxHeight: 600,
                  '&::-webkit-scrollbar': {
                    height: '10px',
                    width: '10px',
                  },
                  '&::-webkit-scrollbar-track': {
                    background: (theme) => theme.palette.mode === 'dark' ? '#1a1a1a' : '#f5f5f5',
                    borderRadius: '5px',
                  },
                  '&::-webkit-scrollbar-thumb': {
                    background: (theme) => theme.palette.mode === 'dark'
                      ? 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)'
                      : 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                    borderRadius: '5px',
                    '&:hover': {
                      background: (theme) => theme.palette.mode === 'dark'
                        ? 'linear-gradient(135deg, #764ba2 0%, #667eea 100%)'
                        : 'linear-gradient(135deg, #764ba2 0%, #667eea 100%)',
                    }
                  }
                }}>
                  <Table stickyHeader sx={{ 
                    '& .MuiTableCell-root': {
                      fontFamily: '"Noto Sans", "Noto Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
                      WebkitFontSmoothing: 'antialiased',
                      MozOsxFontSmoothing: 'grayscale',
                    }
                  }}>
                    <TableHead>
                      <TableRow>
                        {headers.map((header, idx) => {
                          // Check if any cell in this column has long text content
                          const hasLongTextInColumn = tableData.some(row => {
                            const val = String(row[header] === undefined || row[header] === null ? '' : row[header]);
                            return val.length > 20 && /[a-zA-Z]/.test(val);
                          });
                          
                          // Determine if this is a numeric column header
                          const isNumericHeader = !hasLongTextInColumn && (
                            header.toLowerCase().includes('count') || 
                            header.toLowerCase().includes('value') ||
                            header.toLowerCase().includes('qty') ||
                            header.toLowerCase().includes('mhz') ||
                            header.toLowerCase().includes('cpus')
                          );

                          return (
                            <TableCell key={idx} sx={{ 
                              fontWeight: 600,
                              fontSize: '0.8125rem',
                              fontFamily: '"Noto Sans", "Noto Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
                              color: (theme) => theme.palette.mode === 'dark' ? '#ffffff' : '#2d3748',
                              background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                              borderBottom: '2px solid transparent',
                              borderImage: 'linear-gradient(90deg, #667eea 0%, #764ba2 100%) 1',
                              textAlign: isNumericHeader ? 'center' : 'left',
                              paddingLeft: isNumericHeader ? 0 : 2,
                              padding: '16px 12px',
                              textTransform: 'uppercase',
                              letterSpacing: '0.08em',
                              position: 'relative',
                              transition: 'all 0.3s ease',
                              textShadow: '0 1px 2px rgba(0,0,0,0.3)',
                              '&:hover': {
                                color: '#ffffff',
                                transform: 'translateY(-1px)',
                                textShadow: '0 2px 4px rgba(0,0,0,0.4)',
                              },
                              // Make ID and name columns less wide
                              ...(header.toLowerCase().includes('id') && { maxWidth: '120px' }),
                              ...(header.toLowerCase().includes('name') && { maxWidth: '200px' }),
                              // Make numeric columns narrower
                              ...(isNumericHeader && { width: 'fit-content', minWidth: '90px' }),
                              '&::after': {
                                content: '""',
                                position: 'absolute',
                                bottom: 0,
                                left: 0,
                                right: 0,
                                height: '2px',
                                background: 'linear-gradient(90deg, transparent, #667eea, transparent)',
                                transform: 'scaleX(0)',
                                transition: 'transform 0.3s ease',
                              },
                              '&:hover::after': {
                                transform: 'scaleX(1)',
                              }
                            }}>
                              {header.charAt(0).toUpperCase() + header.slice(1).replace(/_/g, ' ')}
                            </TableCell>
                          );
                        })}
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {tableData.map((row, rowIndex) => (
                        <TableRow key={rowIndex} sx={{ 
                          transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
                          '&:nth-of-type(odd)': {
                            bgcolor: (theme) => theme.palette.mode === 'dark' 
                              ? 'rgba(102, 126, 234, 0.03)' 
                              : 'rgba(102, 126, 234, 0.02)'
                          },
                          '&:hover': {
                            bgcolor: (theme) => theme.palette.mode === 'dark' 
                              ? 'rgba(102, 126, 234, 0.12)' 
                              : 'rgba(102, 126, 234, 0.08)',
                            transform: 'scale(1.01)',
                            boxShadow: (theme) => theme.palette.mode === 'dark'
                              ? '0 4px 12px rgba(102, 126, 234, 0.2)'
                              : '0 4px 12px rgba(102, 126, 234, 0.15)',
                            '& td': {
                              color: (theme) => theme.palette.mode === 'dark' ? '#ffffff' : '#1a202c',
                            }
                          },
                          cursor: 'pointer',
                        }}>
                          {headers.map((header, cellIndex) => {
                            const cellValue = String(row[header] === undefined || row[header] === null ? '' : row[header]);
                            
                            // Check if any cell in this column has long text content
                            const hasLongTextInColumn = tableData.some(r => {
                              const val = String(r[header] === undefined || r[header] === null ? '' : r[header]);
                              return val.length > 20 && /[a-zA-Z]/.test(val);
                            });
                            
                            // Determine if this cell contains numeric data
                            const isNumeric = !hasLongTextInColumn && (
                              /^[\d.,\s%]+$/.test(cellValue) || 
                              header.toLowerCase().includes('count') || 
                              header.toLowerCase().includes('value') ||
                              header.toLowerCase().includes('qty') ||
                              header.toLowerCase().includes('mhz') ||
                              header.toLowerCase().includes('cpus')
                            );

                            // Host columns should be left-aligned
                            const isHostColumn = header.toLowerCase() === 'host';
                            
                            return (
                              <TableCell key={cellIndex} sx={{
                                ...(cellIndex === 0 && { 
                                  fontWeight: 600,
                                  color: (theme) => theme.palette.mode === 'dark' ? '#a78bfa' : '#6366f1',
                                }),
                                textAlign: isNumeric ? 'center' : 'left',
                                paddingLeft: (isNumeric || (!isHostColumn && cellIndex === 0)) ? 0 : 2,
                                padding: '14px 12px',
                                fontSize: '0.8125rem',
                                fontFamily: '"Noto Sans", "Noto Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
                                color: (theme) => theme.palette.mode === 'dark' ? '#e2e8f0' : '#4a5568',
                                transition: 'all 0.2s ease',
                                position: 'relative',
                                WebkitFontSmoothing: 'antialiased',
                                MozOsxFontSmoothing: 'grayscale',
                                lineHeight: 1.5,
                                // Truncate very long text
                                ...(cellValue.length > 50 && {
                                  maxWidth: '300px',
                                  overflow: 'hidden',
                                  textOverflow: 'ellipsis',
                                  whiteSpace: 'nowrap'
                                })
                              }}>
                                {cellValue}
                              </TableCell>
                            );
                          })}
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              </Box>
            );
          }
        }
      }
    } catch (error) {
      // Not a valid JSON or not our table structure, render as normal code block
      console.warn('Failed to parse JSON for table or invalid table structure:', error);
    }
  }

  // Fallback to default code rendering or use a syntax highlighter if available
  // For simplicity, rendering as a preformatted code block here.
  return (
    <Box component="pre" sx={{ p: 1, my: 1, backgroundColor: 'action.selected', borderRadius: 1, overflowX: 'auto', fontSize: '0.875rem' }}>
      <Box component="code" className={className} {...props}>
        {children}
      </Box>
    </Box>
  );
};

const FilePreview = ({ selectedFile }) => {
  const fileTypeInfo = selectedFile ? getFileTypeInfo(selectedFile.name) : null;
  const { theme } = useTheme();
  const isDark = true; // Force dark mode to true since we switched to black theme
  const [error, setError] = useState(null);
  const [originalContent, setOriginalContent] = useState('');
  
  // Function to export Markdown to PDF via backend endpoint
  const handleExportPDF = async (file) => {
    try {
      const baseName = file.name.split('.').slice(0, -1).join('.');
      const mdFileName = file.ai_analyzed ? `${baseName}_AI.md` : `${baseName}.md`;
      // Determine API base URL: env var or same-origin
      const API_BASE = (process.env.REACT_APP_API_BASE || window.__ENV__?.REACT_APP_API_BASE || window.location.origin).replace(/\/$/, '');
      const url = `${API_BASE}/api/export-pdf?blob_name=${encodeURIComponent(mdFileName)}&page_size=A3`;
      window.open(url, '_blank');
    } catch (err) {
      console.error(`Error exporting PDF for ${file.name}:`, err);
      alert(`Failed to export PDF: ${err.message}`);
    }
  };
  
  // Check if we're displaying AI analysis
  const isAnalysisView = selectedFile?.displayType === 'analysis' && selectedFile?.analysisContent;
  
  // Use metrics and parameters data passed directly from parent component
  const metricsData = selectedFile?.metricsData;
  const parametersData = selectedFile?.parametersData;
  
  // Fetch original document content for chat context
  useEffect(() => {
    const fetchOriginalContent = async () => {
      if (!selectedFile?.name) {
        console.log('No file selected');
        setOriginalContent('');
        return;
      }
      
      try {
        console.log(`Fetching content for file: ${selectedFile.name}`);
        
        // IMPORTANT: Try different file formats in a specific order to ensure we get the best content
        // 1. ALWAYS use the original markdown file as primary source for chat context
        const baseName = selectedFile.name.replace(/\.[^/.]+$/, "");
        // Determine API base URL: env var or same-origin
const API_BASE = (process.env.REACT_APP_API_BASE || window.__ENV__?.REACT_APP_API_BASE || window.location.origin).replace(/\/$/, '');

const mdFileName = `${baseName}.md`;
        console.log(`Loading original markdown file for context: ${mdFileName}`);
        
        let response = await fetch(`${API_BASE}/api/download/${mdFileName}`);
        
        // 2. Only if original markdown not found, try others as fallback
        if (!response.ok) {
          console.log(`Original markdown file not found, this is unusual`);
          // Try AI file as fallback (not ideal but better than nothing)
          const aiFileName = `${baseName}_AI.md`;
          console.log(`Trying AI file as fallback: ${aiFileName}`);
          response = await fetch(`${API_BASE}/api/download/${aiFileName}`);
        }
        
        // 3. If markdown not found, try the original file as last resort
        if (!response.ok) {
          console.log(`Markdown file not found, trying original file: ${selectedFile.name}`);
          response = await fetch(`${API_BASE}/api/download/${selectedFile.name}`);
        }
        
        if (response.ok) {
          const content = await response.text();
          console.log(`Successfully loaded content: ${content.length} characters`);
          
          // Log content snippets to verify what we're getting
          console.log(`Content starts with: ${content.substring(0, 100)}...`);
          console.log(`Content ends with: ...${content.substring(content.length - 100)}`);
          
          // Check if content is HTML or has proper text
          if (content.includes('<html') || content.includes('</html>')) {
            console.warn('Warning: Content appears to be HTML, may not be ideal for chat');
          }
          
          if (content.includes('SAP') || content.includes('EWA') || content.includes('Early Watch')) {
            console.log('Content contains expected SAP keywords - good!');
          } else {
            console.warn('Warning: Content does not contain expected SAP keywords');
          }
          
          setOriginalContent(content);
        } else {
          console.error(`Could not load any content for ${selectedFile.name}`);
          setOriginalContent(`Could not load content for ${selectedFile.name}. Please make sure the file has been processed.`);
        }
      } catch (error) {
        console.error('Error fetching original content:', error);
        setOriginalContent(`Error loading document content: ${error.message}`);
      }
    };

    fetchOriginalContent();
  }, [selectedFile?.name]);

  // Debug: Log the beginning of analysisContent
  useEffect(() => {
    if (isAnalysisView && selectedFile?.analysisContent) {
      const contentStart = selectedFile.analysisContent.substring(0, 20);
      const charCodes = [];
      for (let i = 0; i < contentStart.length; i++) {
        charCodes.push(contentStart.charCodeAt(i));
      }
      console.log('Analysis Content Start:', contentStart);
      console.log('Analysis Content Char Codes:', JSON.stringify(charCodes));
    }
  }, [selectedFile, isAnalysisView]);
  
  // Debug the actual structure
  console.log('DEBUG - Full metricsData:', JSON.stringify(metricsData, null, 2));
  console.log('DEBUG - metricsData type:', typeof metricsData);
  console.log('DEBUG - metricsData is array:', Array.isArray(metricsData));
  if (metricsData && typeof metricsData === 'object') {
    console.log('DEBUG - metricsData keys:', Object.keys(metricsData));
    console.log('DEBUG - metricsData.metrics exists:', 'metrics' in metricsData);
    console.log('DEBUG - metricsData.metrics type:', typeof metricsData.metrics);
  }
  
  // Enhanced metrics detection logic to handle all possible data structures
  const hasMetrics = metricsData && (
    // Check if it's an object with metrics property that is an array
    (metricsData.metrics && Array.isArray(metricsData.metrics) && metricsData.metrics.length > 0) ||
    // Check if it's a direct array
    (Array.isArray(metricsData) && metricsData.length > 0) ||
    // Check if it has a length property (for array-like objects)
    (typeof metricsData === 'object' && 'length' in metricsData && metricsData.length > 0) ||
    // Check if it's an object with any keys (that isn't empty)
    (typeof metricsData === 'object' && Object.keys(metricsData).length > 0)
  );
  const hasParameters = parametersData && parametersData.parameters && parametersData.parameters.length > 0;
  
  // Log metrics and parameters data for debugging
  useEffect(() => {
    if (isAnalysisView) {
      if (hasMetrics) {
        console.log('Displaying metrics data in FilePreview:', metricsData);
        // Log the actual metrics array we'll pass to the table
        const metricsArray = metricsData.metrics || metricsData;
        console.log('Metrics array for table:', metricsArray);
      } else {
        console.log('No metrics data available for this analysis');
      }
      
      if (hasParameters) {
        console.log('Displaying parameters data in FilePreview:', parametersData.parameters);
      } else {
        console.log('No parameters data available for this analysis');
      }
    }
  }, [isAnalysisView, hasMetrics, hasParameters, metricsData, parametersData]);
  
  return (
    <Paper
      elevation={3}
      sx={{
        padding: 0,
        background: isDark 
          ? 'linear-gradient(145deg, #161616, #1E1E1E)'
          : 'linear-gradient(145deg, #f8f9fa, #ffffff)',
        borderRadius: 3,
        height: '100%',
        width: '100%',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        border: isDark 
          ? '1px solid rgba(255, 255, 255, 0.05)'
          : '1px solid rgba(0, 0, 0, 0.05)',
      }}
    >
      <Box sx={{ 
        px: 2, 
        py: 1.5, 
        borderBottom: isDark
          ? '1px solid rgba(255, 255, 255, 0.05)'
          : '1px solid rgba(0, 0, 0, 0.05)',
        display: 'flex',
        alignItems: 'center',
      }}>
        <Typography variant="h6" component="div" sx={{ flexGrow: 1, fontWeight: 500 }}>
          {isAnalysisView ? 'AI Analysis' : 'File Preview'}
        </Typography>
        {selectedFile && (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            {selectedFile && selectedFile.name && (
              <Tooltip title="Export to PDF">
                <IconButton 
                  size="small"
                  onClick={() => handleExportPDF(selectedFile)}
                  sx={{ 
                    color: isDark ? 'rgba(255, 255, 255, 0.7)' : 'rgba(0, 0, 0, 0.7)',
                    '&:hover': {
                      color: '#F44336',
                      backgroundColor: isDark ? 'rgba(244, 67, 54, 0.08)' : 'rgba(244, 67, 54, 0.04)'
                    }
                  }}
                >
                  <PictureAsPdfOutlinedIcon fontSize="small" />
                </IconButton>
              </Tooltip>
            )}
            <Chip
              icon={isAnalysisView ? 
                <Box component="img" 
                  src={sapLogo} 
                  alt="SAP Logo"
                  sx={{ 
                    height: 28, 
                    width: 28, 
                    objectFit: 'contain',
                    marginRight: '2px'
                  }} 
                /> : fileTypeInfo?.icon
              }
              label={isAnalysisView ? '' : fileTypeInfo?.label}
              size={isAnalysisView ? "medium" : "small"}
              color={isAnalysisView ? 'info' : fileTypeInfo?.color}
              variant="outlined"
              sx={{ 
                borderRadius: 1,
                height: isAnalysisView ? 36 : 'auto',
                '& .MuiChip-icon': { 
                  marginLeft: isAnalysisView ? '8px' : '5px' 
                }
              }}
            />
          </Box>
        )}
      </Box>
      
      <Box sx={{
        flexGrow: 1,
        display: 'flex',
        alignItems: isAnalysisView ? 'flex-start' : 'center',
        justifyContent: isAnalysisView ? 'flex-start' : 'center',
        p: isAnalysisView ? 0 : 3,
        background: isAnalysisView ? 'transparent' : 'rgba(0, 0, 0, 0.2)',
        overflow: 'auto'
      }}>
        {selectedFile ? (
          isAnalysisView ? (
            <Box sx={{ 
              width: '100%', 
              height: '100%',
              p: 3,
              overflow: 'auto'
            }}>
              {/* Main Analysis Content - We'll add metrics at the end */}
              
              {/* Analysis Content Section */}
              <ReactMarkdown
                key={selectedFile ? selectedFile.name : 'default-key'}
                remarkPlugins={[remarkGfm]}
                components={{
                  table: ({ children }) => (
                    <Box sx={{ 
                      overflowX: 'auto', 
                      mb: 3,
                      mt: 2,
                      borderRadius: 3,
                      overflow: 'hidden',
                      background: isDark 
                        ? 'linear-gradient(145deg, #1a1a1a 0%, #0a0a0a 100%)'
                        : 'linear-gradient(145deg, #ffffff 0%, #f5f5f5 100%)',
                      boxShadow: isDark
                        ? '0 8px 32px 0 rgba(0, 0, 0, 0.5), 0 2px 8px 0 rgba(0, 0, 0, 0.3)'
                        : '0 8px 32px 0 rgba(31, 38, 135, 0.15), 0 2px 8px 0 rgba(31, 38, 135, 0.08)',
                      border: `1px solid ${isDark ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.08)'}`,
                      transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
                      '&:hover': {
                        transform: 'translateY(-2px)',
                        boxShadow: isDark
                          ? '0 12px 40px 0 rgba(0, 0, 0, 0.6), 0 4px 12px 0 rgba(0, 0, 0, 0.4)'
                          : '0 12px 40px 0 rgba(31, 38, 135, 0.2), 0 4px 12px 0 rgba(31, 38, 135, 0.1)',
                      },
                      '& table': {
                        width: '100%',
                        borderCollapse: 'separate',
                        borderSpacing: 0,
                        fontSize: '0.875rem',
                        fontFamily: '"Noto Sans", "Noto Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
                        WebkitFontSmoothing: 'antialiased',
                        MozOsxFontSmoothing: 'grayscale',
                      },
                      '&::-webkit-scrollbar': {
                        height: '10px',
                      },
                      '&::-webkit-scrollbar-track': {
                        background: isDark ? '#1a1a1a' : '#f5f5f5',
                        borderRadius: '5px',
                      },
                      '&::-webkit-scrollbar-thumb': {
                        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                        borderRadius: '5px',
                        '&:hover': {
                          background: 'linear-gradient(135deg, #764ba2 0%, #667eea 100%)',
                        }
                      }
                    }}>
                      <table>{children}</table>
                    </Box>
                  ),
                  thead: ({ children }) => (
                    <thead style={{ 
                      background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                    }}>
                      {children}
                    </thead>
                  ),
                  tr: ({ children, index }) => {
                    // Determine if this is an odd or even row
                    const isEven = index % 2 === 0;
                    return (
                      <tr style={{ 
                        transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
                        backgroundColor: isEven ? 
                          (isDark ? 'rgba(102, 126, 234, 0.03)' : 'rgba(102, 126, 234, 0.02)') : 
                          'transparent',
                        cursor: 'pointer',
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.backgroundColor = isDark 
                          ? 'rgba(102, 126, 234, 0.12)' 
                          : 'rgba(102, 126, 234, 0.08)';
                        e.currentTarget.style.transform = 'scale(1.01)';
                        e.currentTarget.style.boxShadow = isDark
                          ? '0 4px 12px rgba(102, 126, 234, 0.2)'
                          : '0 4px 12px rgba(102, 126, 234, 0.15)';
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.backgroundColor = isEven ? 
                          (isDark ? 'rgba(102, 126, 234, 0.03)' : 'rgba(102, 126, 234, 0.02)') : 
                          'transparent';
                        e.currentTarget.style.transform = 'scale(1)';
                        e.currentTarget.style.boxShadow = 'none';
                      }}
                      >
                        {children}
                      </tr>
                    );
                  },
                  th: ({ children }) => (
                    <th style={{ 
                      padding: '16px 12px', 
                      textAlign: 'center', 
                      fontWeight: 600,
                      fontSize: '0.8125rem',
                      fontFamily: '"Noto Sans", "Noto Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
                      color: '#ffffff',
                      textTransform: 'uppercase',
                      letterSpacing: '0.08em',
                      position: 'relative',
                      borderBottom: '2px solid transparent',
                      borderImage: 'linear-gradient(90deg, #667eea 0%, #764ba2 100%) 1',
                      borderRight: '1px solid rgba(255, 255, 255, 0.1)',
                      whiteSpace: 'nowrap',
                      textShadow: '0 1px 2px rgba(0,0,0,0.3)',
                      WebkitFontSmoothing: 'antialiased',
                      MozOsxFontSmoothing: 'grayscale',
                    }}>
                      {children}
                    </th>
                  ),
                  td: ({ children }) => {
                    // Detect if cell contains status icons and apply appropriate styling
                    const content = children?.toString() || '';
                    const hasStatusIcon = content.includes('✅') || content.includes('❌') || content.includes('⚠️');
                    
                    // Check if this is the first cell (usually contains primary identifier)
                    const isFirstCell = false; // Can't determine position in ReactMarkdown context
                    
                    // Check if content is numeric
                    const isNumeric = /^[\d.,\s%]+$/.test(content) || 
                                    content.includes('ms') || 
                                    content.includes('GB') ||
                                    content.includes('MHz');
                    
                    let textColor = isDark ? '#e2e8f0' : '#4a5568';
                    let fontWeight = '400';
                    let fontSize = '0.8125rem';
                    let fontFamily = '"Noto Sans", "Noto Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif';
                    
                    if (hasStatusIcon) {
                      fontWeight = '600';
                      fontSize = '0.9375rem';
                      
                      if (content.includes('✅')) {
                        textColor = '#4CAF50'; // Green for success
                      } else if (content.includes('❌')) {
                        textColor = '#F44336'; // Red for error/critical
                      } else if (content.includes('⚠️')) {
                        textColor = '#FF9800'; // Orange for warning
                      }
                    }
                    
                    return (
                      <td style={{ 
                        padding: '14px 12px',
                        fontSize: fontSize,
                        fontWeight: fontWeight,
                        fontFamily: fontFamily,
                        color: textColor,
                        verticalAlign: 'middle',
                        textAlign: hasStatusIcon ? 'center' : 'left',
                        borderBottom: '1px solid rgba(102, 126, 234, 0.06)',
                        borderRight: '1px solid rgba(102, 126, 234, 0.04)',
                        transition: 'background-color 0.2s ease, color 0.2s ease',
                        WebkitFontSmoothing: 'antialiased',
                        MozOsxFontSmoothing: 'grayscale',
                        lineHeight: 1.5,
                      }}>
                        {children}
                      </td>
                    );
                  },
                  tbody: ({ children }) => (
                    <tbody style={{
                      backgroundColor: 'transparent',
                    }}>
                      {children}
                    </tbody>
                  ),
                  code: JsonCodeBlockRenderer,
                  h1: ({ children }) => (
                    <Typography 
                      variant="h4" 
                      sx={{ 
                        mt: 3, 
                        mb: 2, 
                        fontWeight: 600,
                        fontFamily: '"Noto Sans", "Noto Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
                        fontSize: '1.75rem',
                        letterSpacing: '-0.02em',
                        color: isDark ? '#f3f4f6' : '#111827',
                        WebkitFontSmoothing: 'antialiased',
                        MozOsxFontSmoothing: 'grayscale',
                      }}
                    >
                      {children}
                    </Typography>
                  ),
                  h2: ({ children }) => (
                    <Typography 
                      variant="h5" 
                      sx={{ 
                        mt: 2.5, 
                        mb: 1.5, 
                        fontWeight: 600,
                        fontFamily: '"Noto Sans", "Noto Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
                        fontSize: '1.375rem',
                        letterSpacing: '-0.01em',
                        color: isDark ? '#e5e7eb' : '#1f2937',
                        WebkitFontSmoothing: 'antialiased',
                        MozOsxFontSmoothing: 'grayscale',
                      }}
                    >
                      {children}
                    </Typography>
                  ),
                  h3: ({ children }) => (
                    <Typography 
                      variant="h6" 
                      sx={{ 
                        mt: 2, 
                        mb: 1, 
                        fontWeight: 600,
                        fontFamily: '"Noto Sans", "Noto Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
                        fontSize: '1.125rem',
                        letterSpacing: '0',
                        color: isDark ? '#d1d5db' : '#374151',
                        WebkitFontSmoothing: 'antialiased',
                        MozOsxFontSmoothing: 'grayscale',
                      }}
                    >
                      {children}
                    </Typography>
                  ),
                  p: ({ children }) => (
                    <Typography 
                      paragraph 
                      sx={{ 
                        mb: 1.5,
                        fontFamily: '"Noto Sans", "Noto Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
                        fontSize: '0.85rem',
                        lineHeight: 1.7,
                        color: isDark ? '#d1d5db' : '#4b5563',
                        WebkitFontSmoothing: 'antialiased',
                        MozOsxFontSmoothing: 'grayscale',
                      }}
                    >
                      {children}
                    </Typography>
                  ),
                  ul: ({ children }) => (
                    <Box component="ul" sx={{ 
                      mb: 2, 
                      pl: 3,
                      '& li': {
                        fontFamily: '"Noto Sans", "Noto Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
                        fontSize: '0.85rem',
                        lineHeight: 1.7,
                        color: isDark ? '#d1d5db' : '#4b5563',
                        WebkitFontSmoothing: 'antialiased',
                        MozOsxFontSmoothing: 'grayscale',
                      }
                    }}>
                      {children}
                    </Box>
                  ),
                  ol: ({ children }) => (
                    <Box component="ol" sx={{ 
                      mb: 2, 
                      pl: 3,
                      '& li': {
                        fontFamily: '"Noto Sans", "Noto Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
                        fontSize: '0.85rem',
                        lineHeight: 1.7,
                        color: isDark ? '#d1d5db' : '#4b5563',
                        WebkitFontSmoothing: 'antialiased',
                        MozOsxFontSmoothing: 'grayscale',
                      }
                    }}>
                      {children}
                    </Box>
                  ),
                  li: ({ children }) => (
                    <Box component="li" sx={{ 
                      mb: 0.5,
                      '&::marker': {
                        color: isDark ? '#9ca3af' : '#6b7280',
                      }
                    }}>
                      {children}
                    </Box>
                  ),
                  strong: ({ children }) => (
                    <Box 
                      component="strong" 
                      sx={{ 
                        fontWeight: 400,
                        color: isDark ? '#f3f4f6' : '#111827',
                      }}
                    >
                      {children}
                    </Box>
                  ),
                  em: ({ children }) => (
                    <Box 
                      component="em" 
                      sx={{ 
                        fontStyle: 'normal',
                        fontWeight: 400,
                      }}
                    >
                      {children}
                    </Box>
                  ),
                  blockquote: ({ children }) => (
                    <Box 
                      component="blockquote" 
                      sx={{ 
                        borderLeft: '4px solid',
                        borderColor: 'primary.main',
                        pl: 2,
                        ml: 0,
                        my: 2,
                        fontStyle: 'italic',
                        color: isDark ? '#9ca3af' : '#6b7280',
                        fontFamily: '"Noto Sans", "Noto Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
                        fontSize: '0.85rem',
                      }}
                    >
                      {children}
                    </Box>
                  ),
                  a: ({ children, href }) => (
                    <Box 
                      component="a" 
                      href={href}
                      target="_blank"
                      rel="noopener noreferrer"
                      sx={{ 
                        color: isDark ? '#60a5fa' : '#2563eb', // Light blue for dark theme, darker blue for light theme
                        textDecoration: 'underline',
                        fontWeight: 500,
                        '&:hover': {
                          color: isDark ? '#93c5fd' : '#1d4ed8',
                          textDecoration: 'none',
                        },
                        '&:visited': {
                          color: isDark ? '#a78bfa' : '#7c3aed',
                        }
                      }}
                    >
                      {children}
                    </Box>
                  ),
                  // ... other custom components like h1, p, table etc. should remain here
                }}
              >
                {selectedFile.analysisContent}
              </ReactMarkdown>
              
              {/* Collapsible Metrics Section at the end */}
              {hasMetrics && (
                <Box sx={{ mt: 4 }}>
                  <Accordion 
                    defaultExpanded={false}
                    sx={{
                      boxShadow: isDark ? '0 2px 8px rgba(0, 0, 0, 0.5)' : '0 1px 4px rgba(0, 0, 0, 0.1)',
                      borderRadius: '8px !important',
                      overflow: 'hidden',
                      '&:before': { display: 'none' }, // Remove the default MUI expansion panel line
                      border: isDark ? '1px solid rgba(255, 255, 255, 0.1)' : '1px solid rgba(0, 0, 0, 0.1)',
                      mb: 3,
                    }}
                  >
                    <AccordionSummary
                      expandIcon={<ExpandMoreIcon />}
                      sx={{
                        backgroundColor: isDark ? 'rgba(25, 118, 210, 0.15)' : 'rgba(25, 118, 210, 0.08)',
                        '&:hover': {
                          backgroundColor: isDark ? 'rgba(25, 118, 210, 0.25)' : 'rgba(25, 118, 210, 0.12)',
                        }
                      }}
                    >
                      <Box sx={{ display: 'flex', alignItems: 'center' }}>
                        <AssessmentIcon sx={{ mr: 1.5, color: 'primary.main' }} />
                        <Typography variant="h6" sx={{ fontWeight: 500, color: 'primary.main' }}>
                          Key Metrics Summary
                        </Typography>
                      </Box>
                    </AccordionSummary>
                    <AccordionDetails sx={{ p: 0 }}>
                      <Box sx={{ p: 3 }}>
                        {/* <MetricsTable metricsData={metricsData} /> */}
                      </Box>
                    </AccordionDetails>
                  </Accordion>
                </Box>
              )}
              
              {/* Collapsible Parameters Section after metrics */}
              {hasParameters && (
                <Box sx={{ mt: 2, mb: 4 }}>
                  <Accordion 
                    defaultExpanded={false}
                    sx={{
                      boxShadow: isDark ? '0 2px 8px rgba(0, 0, 0, 0.5)' : '0 1px 4px rgba(0, 0, 0, 0.1)',
                      borderRadius: '8px !important',
                      overflow: 'hidden',
                      '&:before': { display: 'none' }, // Remove the default MUI expansion panel line
                      border: isDark ? '1px solid rgba(255, 255, 255, 0.1)' : '1px solid rgba(0, 0, 0, 0.1)',
                      mb: 3,
                    }}
                  >
                    <AccordionSummary
                      expandIcon={<ExpandMoreIcon />}
                      sx={{
                        backgroundColor: isDark ? 'rgba(76, 175, 80, 0.15)' : 'rgba(76, 175, 80, 0.08)',
                        '&:hover': {
                          backgroundColor: isDark ? 'rgba(76, 175, 80, 0.25)' : 'rgba(76, 175, 80, 0.12)',
                        }
                      }}
                    >
                      <Box sx={{ display: 'flex', alignItems: 'center' }}>
                        <TuneIcon sx={{ mr: 1.5, color: 'success.main' }} />
                        <Typography variant="h6" sx={{ fontWeight: 500, color: 'success.main' }}>
                          Recommended Parameters
                        </Typography>
                      </Box>
                    </AccordionSummary>
                    <AccordionDetails sx={{ p: 0 }}>
                      <Box sx={{ p: 3 }}>
                        {/* <ParametersTable parametersData={parametersData} /> */}
                      </Box>
                    </AccordionDetails>
                  </Accordion>
                </Box>
              )}
              
              {/* Error display if metrics failed to load */}
              {error && (
                <Box sx={{ 
                  p: 2, 
                  mt: 3,
                  mb: 3, 
                  borderRadius: 1, 
                  bgcolor: isDark ? 'rgba(244, 67, 54, 0.1)' : 'rgba(244, 67, 54, 0.05)', 
                  border: '1px solid rgba(244, 67, 54, 0.3)'
                }}>
                  <Typography variant="subtitle2" color="error" gutterBottom>
                    Error loading metrics: {error}
                  </Typography>
                </Box>
              )}
            </Box>
          ) : (
            <Box sx={{ 
              width: '100%', 
              height: '100%',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              textAlign: 'center',
              px: 4,
            }}> 
              {fileTypeInfo && fileTypeInfo.icon && React.cloneElement(fileTypeInfo.icon, { 
                sx: { fontSize: 48, mb: 2, opacity: 0.7 } 
              })}
              <Typography variant="subtitle1" sx={{ fontWeight: 500, mb: 1 }}>
                {selectedFile.name}
              </Typography>
              <Typography variant="body2" sx={{ color: 'text.secondary', mb: 3, maxWidth: '80%' }}>
                Preview functionality will be added in a future update
              </Typography>
              <Box sx={{ 
                p: 2, 
                borderRadius: 2, 
                bgcolor: 'rgba(255, 255, 255, 0.03)', 
                border: '1px dashed rgba(255, 255, 255, 0.1)',
                maxWidth: '100%',
                width: '100%',
                height: '60%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}>
                <Typography variant="body2" color="text.disabled">
                  Content preview placeholder
                </Typography>
              </Box>
            </Box>
          )
        ) : (
          <Box sx={{ textAlign: 'center', maxWidth: 400 }}>
            <InsertDriveFileOutlinedIcon sx={{ fontSize: 64, color: 'text.disabled', mb: 2 }} />
            <Typography variant="h6" color="text.secondary" gutterBottom>
              No File Selected
            </Typography>
            <Typography variant="body2" color="text.disabled">
              Select a file from the list to preview its contents
            </Typography>
          </Box>
        )}
      </Box>
      
      {/* Document Chat Component */}
      {selectedFile && (
        <DocumentChat 
          fileName={selectedFile.name}
          documentContent={originalContent}
        />
      )}
    </Paper>
  );
};

export default FilePreview;
