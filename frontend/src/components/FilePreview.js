import React, { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
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
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableContainer from '@mui/material/TableContainer';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import { useTheme } from '../contexts/ThemeContext';

// Import our custom table components
import MetricsTable from './MetricsTable';
import ParametersTable from './ParametersTable';
import DocumentChat from './DocumentChat';

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

      // Check if it's our specific table structure
      if (jsonData && jsonData.tableTitle && Array.isArray(jsonData.headers) && Array.isArray(jsonData.rows)) {
        return (
          <Box sx={{ my: 2, border: '1px solid', borderColor: 'divider', borderRadius: 1, overflow: 'hidden' }}>
            <Typography variant="h6" sx={{ p: 2, bgcolor: 'action.hover' }}>
              {jsonData.tableTitle}
            </Typography>
            <TableContainer component={Paper} elevation={0} square>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    {jsonData.headers.map((header, index) => (
                      <TableCell key={index} sx={{ fontWeight: 'bold' }}>{header}</TableCell>
                    ))}
                  </TableRow>
                </TableHead>
                <TableBody>
                  {jsonData.rows.map((row, rowIndex) => (
                    <TableRow key={rowIndex}>
                      {jsonData.headers.map((header, cellIndex) => (
                        <TableCell key={cellIndex}>{String(row[header] === undefined || row[header] === null ? '' : row[header])}</TableCell>
                      ))}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </Box>
        );
      }
    } catch (error) {
      // Not a valid JSON or not our table structure, render as normal code block
      console.warn('Failed to parse JSON for table or invalid table structure:', error);
    }
  }

  // Fallback to default code rendering or use a syntax highlighter if available
  // For simplicity, rendering as a preformatted code block here.
  // You might want to integrate react-syntax-highlighter for better code display.
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
  const isDark = theme === 'dark';
  const [error, setError] = useState(null);
  const [originalContent, setOriginalContent] = useState('');
  
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
        const mdFileName = `${baseName}.md`;
        console.log(`Loading original markdown file for context: ${mdFileName}`);
        
        let response = await fetch(`/api/download/${mdFileName}`);
        
        // 2. Only if original markdown not found, try others as fallback
        if (!response.ok) {
          console.log(`Original markdown file not found, this is unusual`);
          // Try AI file as fallback (not ideal but better than nothing)
          const aiFileName = `${baseName}_AI.md`;
          console.log(`Trying AI file as fallback: ${aiFileName}`);
          response = await fetch(`/api/download/${aiFileName}`);
        }
        
        // 3. If markdown not found, try the original file as last resort
        if (!response.ok) {
          console.log(`Markdown file not found, trying original file: ${selectedFile.name}`);
          response = await fetch(`/api/download/${selectedFile.name}`);
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
          <Chip
            icon={isAnalysisView ? <SmartToyIcon /> : fileTypeInfo?.icon}
            label={isAnalysisView ? 'AI ANALYSIS' : fileTypeInfo?.label}
            size="small"
            color={isAnalysisView ? 'secondary' : fileTypeInfo?.color}
            variant="outlined"
            sx={{ borderRadius: 1 }}
          />
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
                components={{
                  h1: ({ children }) => (
                    <Typography 
                      variant="h4" 
                      component="h1" 
                      gutterBottom 
                      sx={{ 
                        fontWeight: 700, 
                        color: 'primary.main',
                        fontSize: '1.6rem',
                        letterSpacing: '-0.01em',
                        mt: 2,
                        mb: 2,
                        pb: 1.5,
                        borderBottom: isDark ? '1px solid rgba(255, 255, 255, 0.1)' : '1px solid rgba(0, 0, 0, 0.1)'
                      }}
                    >
                      {children}
                    </Typography>
                  ),
                  h2: ({ children }) => (
                    <Typography 
                      variant="h5" 
                      component="h2" 
                      gutterBottom 
                      sx={{ 
                        fontWeight: 600, 
                        mt: 3, 
                        mb: 1.5,
                        fontSize: '1.25rem',
                        color: isDark ? 'rgba(246, 130, 61, 0.95)' : '#FF6B3D',
                        paddingBottom: 0.75,
                        borderBottom: isDark ? '1px solid rgba(246, 130, 61, 0.3)' : '1px solid rgba(255, 107, 61, 0.2)'
                      }}
                    >
                      {children}
                    </Typography>
                  ),
                  h3: ({ children }) => (
                    <Typography 
                      variant="h6" 
                      component="h3" 
                      gutterBottom 
                      sx={{ 
                        fontWeight: 600, 
                        mt: 2.5, 
                        mb: 1,
                        fontSize: '1.05rem',
                        color: isDark ? 'rgba(246, 184, 61, 0.95)' : '#D96B00'
                      }}
                    >
                      {children}
                    </Typography>
                  ),
                  h1: ({ children }) => (
                    <Typography 
                      variant="h4" 
                      component="h1" 
                      gutterBottom 
                      sx={{ 
                        fontWeight: 700, 
                        mt: 4, 
                        mb: 2,
                        fontSize: '1.75rem',
                        color: isDark ? 'primary.light' : 'primary.dark'
                      }}
                    >
                      {children}
                    </Typography>
                  ),
                  h2: ({ children }) => (
                    <Typography 
                      variant="h5" 
                      component="h2" 
                      gutterBottom 
                      sx={{ 
                        fontWeight: 600, 
                        mt: 3, 
                        mb: 1.5,
                        fontSize: '1.4rem',
                        color: isDark ? 'secondary.light' : 'secondary.dark'
                      }}
                    >
                      {children}
                    </Typography>
                  ),
                  em: ({ children }) => (
                    <Typography 
                      component="em" 
                      sx={{ 
                        fontStyle: 'italic',
                        color: isDark ? 'info.light' : 'info.dark'
                      }}
                    >
                      {children}
                    </Typography>
                  ),
                  p: ({ children }) => (
                    <Typography 
                      variant="body1" 
                      paragraph 
                      sx={{ 
                        lineHeight: 1.6,
                        mb: 1.75,
                        fontSize: '0.925rem',
                        letterSpacing: '0.01em'
                      }}
                    >
                      {children}
                    </Typography>
                  ),
                  ul: ({ children }) => (
                    <Box 
                      component="ul" 
                      sx={{ 
                        pl: 4, 
                        mb: 3,
                        mt: 1.5
                      }}
                    >
                      {children}
                    </Box>
                  ),
                  li: ({ children }) => (
                    <Typography 
                      component="li" 
                      variant="body1" 
                      sx={{ 
                        mb: 0.9, 
                        lineHeight: 1.5,
                        fontSize: '0.925rem',
                        position: 'relative',
                        '&::before': {
                          content: '"\u2022"',
                          position: 'absolute',
                          left: -18,
                          color: 'primary.main',
                          fontWeight: 'bold'
                        }
                      }}
                    >
                      {children}
                    </Typography>
                  ),
                  strong: ({ children }) => (
                    <Typography 
                      component="strong" 
                      sx={{ 
                        fontWeight: 700,
                        color: isDark ? 'primary.light' : 'primary.dark'
                      }}
                    >
                      {children}
                    </Typography>
                  ),
                  // Custom component to style and wrap findings sections
                  blockquote: ({ children }) => {
                    // Try to determine if this is a finding block
                    const childText = children?.toString().toLowerCase() || '';
                    
                    // Detect severity level based on content
                    let severityColor = 'rgba(25, 118, 210, 0.15)';
                    let borderColor = 'rgba(25, 118, 210, 0.5)';
                    let icon = null;
                    let severityText = '';
                    
                    if (childText.includes('critical') || childText.includes('error') || childText.includes('high priority')) {
                      severityColor = isDark ? 'rgba(244, 67, 54, 0.15)' : 'rgba(244, 67, 54, 0.08)';
                      borderColor = 'rgba(244, 67, 54, 0.5)';
                      severityText = 'CRITICAL';
                      icon = '🔴';
                    } else if (childText.includes('warning') || childText.includes('moderate') || childText.includes('medium priority')) {
                      severityColor = isDark ? 'rgba(255, 152, 0, 0.15)' : 'rgba(255, 152, 0, 0.08)';
                      borderColor = 'rgba(255, 152, 0, 0.5)';
                      severityText = 'WARNING';
                      icon = '🟠';
                    } else if (childText.includes('info') || childText.includes('note') || childText.includes('low priority')) {
                      severityColor = isDark ? 'rgba(3, 169, 244, 0.15)' : 'rgba(3, 169, 244, 0.08)';
                      borderColor = 'rgba(3, 169, 244, 0.5)';
                      severityText = 'INFO';
                      icon = 'ℹ️';
                    }
                    
                    return (
                      <Box sx={{
                        backgroundColor: severityColor,
                        borderLeft: `4px solid ${borderColor}`,
                        borderRadius: 1,
                        p: 1.5,
                        mb: 2,
                        mt: 2,
                        boxShadow: isDark ? '0 3px 6px rgba(0, 0, 0, 0.3)' : '0 1px 4px rgba(0, 0, 0, 0.1)',
                      }}>
                        {severityText && (
                          <Box sx={{ 
                            display: 'flex', 
                            alignItems: 'center', 
                            mb: 0.75,
                            pb: 0.75,
                            borderBottom: `1px solid ${borderColor}`
                          }}>
                            {icon && (
                              <Typography sx={{ mr: 1, fontSize: '1.2rem' }}>
                                {icon}
                              </Typography>
                            )}
                            <Typography 
                              variant="subtitle1" 
                              sx={{ 
                                fontWeight: 600,
                                letterSpacing: '0.05em',
                                fontSize: '0.875rem'
                              }}
                            >
                              {severityText}
                            </Typography>
                          </Box>
                        )}
                        {children}
                      </Box>
                    );
                  },
                  
                  // Style for findings/recommendations
                  h4: ({ children }) => {
                    const headingText = children?.toString() || '';
                    let iconSymbol = null;
                    let headingColor = 'text.primary';
                    
                    // Apply custom styling based on heading content
                    if (headingText.toLowerCase().includes('finding')) {
                      iconSymbol = '🔍';
                      headingColor = isDark ? '#FF5722' : '#D84315';
                    } else if (headingText.toLowerCase().includes('recommendation')) {
                      iconSymbol = '💡';
                      headingColor = isDark ? '#4CAF50' : '#2E7D32';
                    } else if (headingText.toLowerCase().includes('impact')) {
                      iconSymbol = '⚠️';
                      headingColor = isDark ? '#FF9800' : '#ED6C02';
                    } else if (headingText.toLowerCase().includes('description')) {
                      iconSymbol = '📝';
                      headingColor = isDark ? '#03A9F4' : '#0277BD';
                    }
                    
                    return (
                      <Typography 
                        variant="subtitle1" 
                        component="h4" 
                        sx={{ 
                          fontWeight: 600, 
                          color: headingColor,
                          display: 'flex',
                          alignItems: 'center',
                          mb: 1,
                          mt: 1.5,
                          fontSize: '0.95rem'
                        }}
                      >
                        {iconSymbol && (
                          <Typography component="span" sx={{ mr: 1 }}>
                            {iconSymbol}
                          </Typography>
                        )}
                        {children}
                      </Typography>
                    );
                  },
                  
                  // Highlighted description lists for key-value pairs
                  dl: ({ children }) => (
                    <Box sx={{
                      backgroundColor: isDark ? 'rgba(255, 255, 255, 0.05)' : 'rgba(0, 0, 0, 0.02)',
                      borderRadius: 1,
                      p: 2,
                      mb: 3,
                      border: isDark ? '1px solid rgba(255, 255, 255, 0.1)' : '1px solid rgba(0, 0, 0, 0.05)',
                    }}>
                      {children}
                    </Box>
                  ),
                  
                  dt: ({ children }) => (
                    <Typography 
                      component="dt" 
                      sx={{ 
                        fontWeight: 600, 
                        color: isDark ? 'primary.light' : 'primary.dark',
                        mb: 0.5
                      }}
                    >
                      {children}
                    </Typography>
                  ),
                  
                  dd: ({ children }) => (
                    <Typography 
                      component="dd" 
                      sx={{ 
                        ml: 2, 
                        mb: 1.5,
                        color: 'text.secondary'
                      }}
                    >
                      {children}
                    </Typography>
                  ),
                  
                  // Enhanced table styling
                  table: ({ children }) => (
                    <Box sx={{ 
                      overflowX: 'auto', 
                      mb: 3,
                      mt: 2,
                      '& table': {
                        width: '100%',
                        borderCollapse: 'separate',
                        borderSpacing: 0,
                        borderRadius: 1,
                        overflow: 'hidden',
                        border: isDark ? '1px solid rgba(255, 255, 255, 0.1)' : '1px solid rgba(0, 0, 0, 0.1)',
                        boxShadow: isDark ? '0 4px 8px rgba(0, 0, 0, 0.5)' : '0 2px 8px rgba(0, 0, 0, 0.1)',
                      }
                    }}>
                      <table>{children}</table>
                    </Box>
                  ),
                  thead: ({ children }) => (
                    <thead style={{ 
                      backgroundColor: isDark ? 'rgba(97, 97, 255, 0.15)' : 'rgba(63, 81, 181, 0.08)', 
                      borderBottom: isDark ? '1px solid rgba(255, 255, 255, 0.2)' : '1px solid rgba(0, 0, 0, 0.2)', 
                    }}>
                      {children}
                    </thead>
                  ),
                  tbody: ({ children }) => (
                    <tbody>{children}</tbody>
                  ),
                  tr: ({ children, index }) => {
                    // Determine if this is an odd or even row
                    const isEven = index % 2 === 0;
                    return (
                      <tr style={{ 
                        borderBottom: isDark ? '1px solid rgba(255, 255, 255, 0.05)' : '1px solid rgba(0, 0, 0, 0.05)',
                        backgroundColor: isEven ? 
                          (isDark ? 'rgba(255, 255, 255, 0.02)' : 'rgba(0, 0, 0, 0.01)') : 
                          'transparent'
                      }}>
                        {children}
                      </tr>
                    );
                  },
                  th: ({ children }) => (
                    <th style={{ 
                      padding: '12px 16px', 
                      textAlign: 'left', 
                      fontWeight: 600,
                      fontSize: '0.875rem',
                      color: isDark ? 'rgba(255, 255, 255, 0.95)' : 'rgba(0, 0, 0, 0.95)',
                      whiteSpace: 'nowrap'
                    }}>
                      {children}
                    </th>
                  ),
                  td: ({ children }) => {
                    // Detect if cell contains status icons and apply appropriate styling
                    const content = children?.toString() || '';
                    const hasStatusIcon = content.includes('✅') || content.includes('❌') || content.includes('⚠️');
                    
                    let textColor = isDark ? 'rgba(255, 255, 255, 0.85)' : 'rgba(0, 0, 0, 0.85)';
                    let fontWeight = '400';
                    let fontSize = '0.875rem';
                    
                    if (hasStatusIcon) {
                      fontWeight = '600';
                      fontSize = '1rem';
                      
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
                        padding: '10px 16px',
                        fontSize: fontSize,
                        fontWeight: fontWeight,
                        color: textColor,
                        verticalAlign: 'middle',
                        textAlign: hasStatusIcon ? 'center' : 'left'
                      }}>
                        {children}
                      </td>
                    );
                  },
                  code: JsonCodeBlockRenderer,
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
                        <MetricsTable metricsData={metricsData} />
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
                        <ParametersTable parametersData={parametersData} />
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
