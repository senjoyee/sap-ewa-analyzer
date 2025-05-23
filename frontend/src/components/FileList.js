import React, { useState, useEffect, useRef } from 'react';
import Paper from '@mui/material/Paper';
import Typography from '@mui/material/Typography';
import List from '@mui/material/List';
import ListItem from '@mui/material/ListItem';
import ListItemButton from '@mui/material/ListItemButton';
import ListItemText from '@mui/material/ListItemText';
import ListItemIcon from '@mui/material/ListItemIcon';
import ListItemSecondaryAction from '@mui/material/ListItemSecondaryAction';
import CircularProgress from '@mui/material/CircularProgress';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Divider from '@mui/material/Divider';
import Chip from '@mui/material/Chip';
import Button from '@mui/material/Button';
import IconButton from '@mui/material/IconButton';
import Tooltip from '@mui/material/Tooltip';
import Accordion from '@mui/material/Accordion';
import AccordionSummary from '@mui/material/AccordionSummary';
import AccordionDetails from '@mui/material/AccordionDetails';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import FolderIcon from '@mui/icons-material/Folder';
import BusinessIcon from '@mui/icons-material/Business';
import { useTheme } from '../contexts/ThemeContext';

// File type icons
import PictureAsPdfIcon from '@mui/icons-material/PictureAsPdf';
import ImageIcon from '@mui/icons-material/Image';
import DescriptionIcon from '@mui/icons-material/Description';
import TextSnippetIcon from '@mui/icons-material/TextSnippet';
import InsertDriveFileIcon from '@mui/icons-material/InsertDriveFile';

// Action and status icons
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import AiAnalysisIcon from './AiAnalysisIcon';
import AutorenewIcon from '@mui/icons-material/Autorenew';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import PendingIcon from '@mui/icons-material/Pending';

// Helper function to get appropriate icon for file type
const getFileIcon = (filename) => {
  // Extract extension from filename
  const fileExtension = filename && typeof filename === 'string' 
    ? filename.split('.').pop().toLowerCase() 
    : '';
  
  // Debug the extension extraction
  console.log(`File: ${filename}, Extension detected: ${fileExtension}`);
  
  switch(fileExtension) {
    case 'pdf':
      return <PictureAsPdfIcon color="error" fontSize="small" />;
    case 'jpg':
    case 'jpeg':
    case 'png':
    case 'gif':
    case 'bmp':
      return <ImageIcon color="info" fontSize="small" />;
    case 'doc':
    case 'docx':
      return <DescriptionIcon color="primary" fontSize="small" />;
    case 'txt':
      return <TextSnippetIcon color="secondary" fontSize="small" />;
    default:
      return <InsertDriveFileIcon color="disabled" fontSize="small" />;
  }
};

// Helper function to format file size
const formatFileSize = (sizeInBytes) => {
  if (sizeInBytes === undefined) return '';
  
  if (sizeInBytes < 1024) {
    return `${sizeInBytes} B`;
  } else if (sizeInBytes < 1024 * 1024) {
    return `${(sizeInBytes / 1024).toFixed(1)} KB`;
  } else {
    return `${(sizeInBytes / (1024 * 1024)).toFixed(1)} MB`;
  }
};

const FileList = ({ onFileSelect, refreshTrigger, selectedFile }) => {
  const [files, setFiles] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [analyzingFiles, setAnalyzingFiles] = useState({}); // Track analysis status for each file
  const [analysisProgress, setAnalysisProgress] = useState({}); // Track progress for each file
  const [expandedCustomers, setExpandedCustomers] = useState({});
  const [aiAnalyzing, setAiAnalyzing] = useState({}); // Track AI analysis status for each file
  const pollingIntervalsRef = useRef({});
  const { theme } = useTheme();
  const isDark = theme === 'dark';
  
  // Group files by customer
  const groupByCustomer = (files) => {
    const grouped = {};
    files.forEach(file => {
      const customer = file.customer_name || 'Unknown';
      if (!grouped[customer]) {
        grouped[customer] = [];
      }
      grouped[customer].push(file);
    });
    return grouped;
  };

  // Function to handle analyze button click
  const handleAnalyze = async (file) => {
    console.log(`Analyzing file: ${file.name}`);
    
    // Set initial status to analyzing
    setAnalyzingFiles(prev => ({
      ...prev,
      [file.id || file.name]: 'analyzing'
    }));
    
    try {
      // Make API call to start analysis
      const response = await fetch('http://localhost:8001/api/analyze', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ blob_name: file.name }),
      });
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || `Analysis failed: ${response.status}`);
      }
      
      // Start polling for status updates
      startStatusPolling(file.name);
      
    } catch (error) {
      console.error(`Error analyzing file ${file.name}:`, error);
      // Set status back to pending on error
      setAnalyzingFiles(prev => ({
        ...prev,
        [file.id || file.name]: 'error'
      }));
      alert(`Error analyzing file: ${error.message}`);
    }
  };

  // Function to handle AI analysis button click
  const handleAnalyzeAI = async (file) => {
    console.log(`Starting AI analysis for file: ${file.name}`);
    
    // Set initial status to analyzing
    setAiAnalyzing(prev => ({
      ...prev,
      [file.id || file.name]: 'analyzing'
    }));
    
    try {
      // Make API call to start AI analysis
      const response = await fetch('http://localhost:8001/api/analyze-ai', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ blob_name: file.name }),
      });
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || `AI Analysis failed: ${response.status}`);
      }
      
      const result = await response.json();
      console.log('AI Analysis result:', result);
      
      // Set status to completed
      setAiAnalyzing(prev => ({
        ...prev,
        [file.id || file.name]: 'completed'
      }));
      
      // Show success message
      alert(`AI Analysis completed successfully! Analysis saved as: ${result.analysis_file}`);
      
    } catch (error) {
      console.error(`Error in AI analysis for file ${file.name}:`, error);
      // Set status back to ready on error
      setAiAnalyzing(prev => ({
        ...prev,
        [file.id || file.name]: 'error'
      }));
      alert(`Error in AI analysis: ${error.message}`);
    }
  };

  // Handle expanding/collapsing a single customer accordion
  const handleCustomerAccordionChange = (customer, isExpanded) => {
    setExpandedCustomers(prev => ({
      ...prev,
      [customer]: isExpanded
    }));
  };

  // Handle expanding all customer accordions
  const handleExpandAll = () => {
    const allCustomers = {};
    files.forEach(file => {
      const customer = file.customer_name || 'Unknown';
      allCustomers[customer] = true;
    });
    setExpandedCustomers(allCustomers);
  };

  // Handle collapsing all customer accordions
  const handleCollapseAll = () => {
    setExpandedCustomers({});
  };

  // Start polling for status updates
  const startStatusPolling = (fileName) => {
    // Clear any existing polling interval for this file
    if (pollingIntervalsRef.current[fileName]) {
      clearInterval(pollingIntervalsRef.current[fileName]);
    }
    
    // Set initial progress
    setAnalysisProgress(prev => ({
      ...prev,
      [fileName]: 0
    }));
    
    // Create a new polling interval
    pollingIntervalsRef.current[fileName] = setInterval(async () => {
      try {
        // Make API call to check status
        const response = await fetch(`http://localhost:8001/api/analysis-status/${encodeURIComponent(fileName)}`);
        
        if (!response.ok) {
          if (response.status === 404) {
            // No status found, keep showing as analyzing
            console.log(`No status found for ${fileName}, continuing to poll...`);
            return;
          }
          const errorData = await response.json();
          throw new Error(errorData.detail || `Status check failed: ${response.status}`);
        }
        
        const statusData = await response.json();
        console.log(`Status update for ${fileName}:`, statusData);
        
        // Update progress percentage
        setAnalysisProgress(prev => ({
          ...prev,
          [fileName]: statusData.progress || 0
        }));
        
        // Update status based on the response
        if (statusData.status === 'completed') {
          // Analysis completed successfully
          setAnalyzingFiles(prev => ({
            ...prev,
            [fileName]: 'analyzed'
          }));
          
          // Stop polling
          clearInterval(pollingIntervalsRef.current[fileName]);
          delete pollingIntervalsRef.current[fileName];
          
          console.log(`Analysis completed for ${fileName}:`, statusData.result);
          
          // Refresh the file list to show updated processed status
          fetchFiles();
        } else if (statusData.status === 'failed') {
          // Analysis failed
          setAnalyzingFiles(prev => ({
            ...prev,
            [fileName]: 'error'
          }));
          
          // Stop polling
          clearInterval(pollingIntervalsRef.current[fileName]);
          delete pollingIntervalsRef.current[fileName];
          
          console.error(`Analysis failed for ${fileName}:`, statusData.message);
          alert(`Analysis failed: ${statusData.message}`);
        }
        // If status is 'pending' or 'processing', we continue polling
        
      } catch (error) {
        console.error(`Error checking status for ${fileName}:`, error);
      }
    }, 2000); // Poll every 2 seconds
  };

  const fetchFiles = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await fetch('http://localhost:8001/api/files');
      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || `Failed to fetch files: ${response.status}`);
      }
      const data = await response.json();
      
      // Log the raw data to check what the backend is sending
      console.log('Raw data from backend:', data);
      
      // Files should already be filtered by the backend
      const filesWithIds = data.map(file => ({
        ...file,
        id: file.name
      }));
      
      setFiles(filesWithIds);
      
      // Initialize analysis status for each file
      const statusMap = {};
      filesWithIds.forEach(file => {
        // Use the 'processed' flag directly from the backend
        // Set status to 'analyzed' if processed is true, otherwise 'pending'
        console.log(`File ${file.name} processed status:`, file.processed);
        statusMap[file.id || file.name] = file.processed ? 'analyzed' : 'pending';
      });
      setAnalyzingFiles(statusMap);
      
      // Auto-expand any customer with only one file or if few total customers
      const grouped = groupByCustomer(filesWithIds);
      const newExpandedState = { ...expandedCustomers };
      Object.keys(grouped).forEach(customer => {
        // If customer has only one file or if there are few total customers, auto-expand
        if (grouped[customer].length === 1 || Object.keys(grouped).length <= 3) {
          newExpandedState[customer] = true;
        }
      });
      setExpandedCustomers(newExpandedState);
    } catch (err) {
      console.error("Error fetching files:", err);
      setError(err.message);
      setFiles([]); 
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchFiles();
  }, [refreshTrigger]);
  
  // Cleanup function to clear all polling intervals when component unmounts
  useEffect(() => {
    return () => {
      // Clear all polling intervals
      Object.values(pollingIntervalsRef.current).forEach(intervalId => {
        clearInterval(intervalId);
      });
      pollingIntervalsRef.current = {};
    };
  }, []);

  let content;

  if (isLoading) {
    content = (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', p: 3, minHeight: 120 }}>
        <CircularProgress size={30} thickness={4} />
      </Box>
    );
  } else if (error) {
    content = (
      <Box sx={{ p: 1 }}>
        <Alert 
          severity="error" 
          variant="outlined"
          sx={{ borderRadius: 2 }}
          action={
            <Button 
              size="small" 
              color="error" 
              variant="text" 
              onClick={fetchFiles}
            >
              Retry
            </Button>
          }
        >
          {error}
        </Alert>
      </Box>
    );
  } else if (files.length === 0) {
    content = (
      <Box sx={{ p: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', py: 4, minHeight: 120 }}>
        <InsertDriveFileIcon sx={{ fontSize: 40, color: 'text.disabled', mb: 2 }} />
        <Typography variant="body2" color="text.secondary" align="center">
          No files uploaded yet
        </Typography>
      </Box>
    );
  } else {
    // Group files by customer
    const filesByCustomer = groupByCustomer(files);
    const customers = Object.keys(filesByCustomer).sort();
    
    content = (
      <Box>
        {/* Expand/Collapse All controls */}
        {customers.length > 1 && (
          <Box sx={{ mb: 1.5, px: 1, display: 'flex', justifyContent: 'flex-end' }}>
            <Box sx={{ display: 'flex', gap: 1 }}>
              <Button 
                size="small" 
                variant="text" 
                onClick={handleExpandAll}
                sx={{ fontSize: '0.75rem', minWidth: 0, py: 0.5 }}
              >
                Expand All
              </Button>
              <Button 
                size="small" 
                variant="text" 
                onClick={handleCollapseAll}
                sx={{ fontSize: '0.75rem', minWidth: 0, py: 0.5 }}
              >
                Collapse All
              </Button>
            </Box>
          </Box>
        )}
        
        {/* Customer accordions */}
        {customers.map(customer => (
          <Accordion 
            key={customer}
            disableGutters 
            elevation={0}
            expanded={!!expandedCustomers[customer]}
            onChange={(e, isExpanded) => handleCustomerAccordionChange(customer, isExpanded)}
            sx={{ 
              mb: 1,
              bgcolor: isDark ? 'rgba(255, 255, 255, 0.03)' : 'rgba(0, 0, 0, 0.02)',
              overflow: 'hidden',
              '&:before': { display: 'none' }, // Remove the default divider
              borderRadius: 2,
              border: isDark ? '1px solid rgba(255, 255, 255, 0.05)' : '1px solid rgba(0, 0, 0, 0.08)'
            }}
          >
            <AccordionSummary 
              expandIcon={<ExpandMoreIcon />}
              sx={{ 
                minHeight: 48,
                '& .MuiAccordionSummary-content': { margin: '12px 0' },
              }}
            >
              <Box sx={{ display: 'flex', alignItems: 'center' }}>
                <BusinessIcon sx={{ mr: 1, fontSize: 20, color: 'primary.main' }} />
                <Typography variant="subtitle2">{customer}</Typography>
                <Chip 
                  label={filesByCustomer[customer].length} 
                  size="small" 
                  color="primary"
                  variant="outlined"
                  sx={{ ml: 1, height: 20, minWidth: 20, fontSize: '0.7rem' }}
                />
              </Box>
            </AccordionSummary>
            <AccordionDetails sx={{ p: 0 }}>
              <List 
                sx={{ 
                  py: 0,
                  '& .MuiListItemButton-root': {
                    borderRadius: 1,
                    mx: 0.5,
                    my: 0.5,
                    transition: 'all 0.2s',
                    '&:hover': {
                      bgcolor: isDark ? 'rgba(255, 255, 255, 0.08)' : 'rgba(0, 0, 0, 0.05)',
                    },
                    '&.Mui-selected': {
                      bgcolor: isDark ? 'primary.dark' : 'primary.light',
                      color: isDark ? 'white' : 'primary.dark',
                      '&:hover': {
                        bgcolor: isDark ? 'primary.dark' : 'primary.light',
                      },
                    },
                  }
                }}
              >
                {filesByCustomer[customer].map((file) => {
          const isSelected = selectedFile && (selectedFile.id === file.id || selectedFile.name === file.name);
          
          return (
            <ListItem 
              key={file.id || file.name} 
              disablePadding 
              sx={{ position: 'relative', mb: 0.5 }}
            >
              <ListItemButton 
                onClick={() => onFileSelect(file)}
                selected={isSelected}
                sx={{ pr: 9 }} // Make room for the analyze button and status
              >
                <ListItemIcon sx={{ minWidth: 36 }}>
                  {getFileIcon(file.name)}
                </ListItemIcon>
                <Tooltip title={file.name} placement="top-start">
                  <ListItemText 
                    primary={file.name} 
                    secondary={
                      <Box sx={{ display: 'flex', flexDirection: 'column' }}>
                        <Box sx={{ display: 'flex', alignItems: 'center' }}>
                          <Box component="span" sx={{ mr: 1 }}>{formatFileSize(file.size)}</Box>
                          {file.customer_name && (
                            <Chip 
                              label={`Customer: ${file.customer_name}`}
                              size="small"
                              color="secondary"
                              variant="outlined"
                              sx={{ height: 20, fontSize: '0.6rem', mr: 1 }}
                            />
                          )}
                        </Box>
                        <Box sx={{ display: 'flex', alignItems: 'center', mt: 0.5 }}>
                          {analyzingFiles[file.id || file.name] === 'pending' && (
                            <Chip 
                              icon={<PendingIcon />} 
                              label="Pending" 
                              size="small" 
                              color="default" 
                              variant="outlined"
                              sx={{ height: 20, fontSize: '0.6rem' }}
                            />
                          )}
                          {analyzingFiles[file.id || file.name] === 'analyzing' && (
                            <Box sx={{ display: 'flex', alignItems: 'center' }}>
                              <Chip 
                                icon={
                                  <AutorenewIcon 
                                    sx={{ 
                                      animation: 'spin 2s linear infinite',
                                      '@keyframes spin': {
                                        '0%': { transform: 'rotate(0deg)' },
                                        '100%': { transform: 'rotate(360deg)' }
                                      }
                                    }} 
                                  />
                                } 
                                label={`Processing ${analysisProgress[file.name] || 0}%`} 
                                size="small" 
                                color="warning" 
                                variant="outlined"
                                sx={{ height: 20, fontSize: '0.6rem', mr: 1 }}
                              />
                              {analysisProgress[file.name] > 0 && (
                                <Box sx={{ position: 'relative', width: 40, height: 4, borderRadius: 2, bgcolor: 'background.paper', overflow: 'hidden' }}>
                                  <Box 
                                    sx={{ 
                                      position: 'absolute',
                                      left: 0,
                                      top: 0,
                                      height: '100%',
                                      width: `${analysisProgress[file.name]}%`,
                                      bgcolor: 'warning.main',
                                      transition: 'width 0.3s ease'
                                    }}
                                  />
                                </Box>
                              )}
                            </Box>
                          )}
                          {analyzingFiles[file.id || file.name] === 'analyzed' && (
                            <Chip 
                              icon={<CheckCircleIcon />} 
                              label="Processed" 
                              size="small" 
                              color="success" 
                              variant="outlined"
                              sx={{ height: 20, fontSize: '0.6rem' }}
                            />
                          )}
                          {aiAnalyzing[file.id || file.name] === 'analyzing' && (
                            <Chip 
                              icon={
                                <AutorenewIcon 
                                  sx={{ 
                                    animation: 'spin 2s linear infinite',
                                    '@keyframes spin': {
                                      '0%': { transform: 'rotate(0deg)' },
                                      '100%': { transform: 'rotate(360deg)' }
                                    }
                                  }} 
                                />
                              } 
                              label="AI Analyzing" 
                              size="small" 
                              color="warning" 
                              variant="outlined"
                              sx={{ height: 20, fontSize: '0.6rem', mr: 1 }}
                            />
                          )}
                          {aiAnalyzing[file.id || file.name] === 'completed' && (
                            <Chip 
                              icon={<CheckCircleIcon />} 
                              label="AI Analyzed" 
                              size="small" 
                              color="success" 
                              variant="outlined"
                              sx={{ height: 20, fontSize: '0.6rem' }}
                            />
                          )}
                        </Box>
                      </Box>
                    }
                    primaryTypographyProps={{
                      noWrap: true,
                      fontSize: '0.875rem',
                      fontWeight: isSelected ? 500 : 400
                    }}
                    secondaryTypographyProps={{
                      component: 'div',
                      noWrap: true,
                      fontSize: '0.75rem'
                    }}
                  />
                </Tooltip>
              </ListItemButton>
              <ListItemSecondaryAction>
                {analyzingFiles[file.id || file.name] === 'analyzed' ? (
                  <Tooltip title={aiAnalyzing[file.id || file.name] === 'analyzing' ? "AI Analysis in progress..." : aiAnalyzing[file.id || file.name] === 'completed' ? "AI Analysis completed" : "Analyze with AI"}>
                    <IconButton 
                      edge="end" 
                      size="small" 
                      color="secondary"
                      disabled={aiAnalyzing[file.id || file.name] === 'analyzing'}
                      onClick={(e) => {
                        e.stopPropagation();
                        handleAnalyzeAI(file);
                      }}
                      sx={{ 
                        bgcolor: aiAnalyzing[file.id || file.name] === 'completed' ? 'rgba(76, 175, 80, 0.08)' : 'rgba(156, 39, 176, 0.08)',
                        '&:hover': {
                          bgcolor: aiAnalyzing[file.id || file.name] === 'completed' ? 'rgba(76, 175, 80, 0.2)' : 'rgba(156, 39, 176, 0.2)',
                        },
                        '&:disabled': {
                          bgcolor: 'rgba(156, 39, 176, 0.04)',
                        }
                      }}
                    >
                      {aiAnalyzing[file.id || file.name] === 'analyzing' ? (
                        <AutorenewIcon 
                          fontSize="small" 
                          sx={{ 
                            animation: 'spin 2s linear infinite',
                            '@keyframes spin': {
                              '0%': { transform: 'rotate(0deg)' },
                              '100%': { transform: 'rotate(360deg)' }
                            }
                          }} 
                        />
                      ) : aiAnalyzing[file.id || file.name] === 'completed' ? (
                        <CheckCircleIcon fontSize="small" />
                      ) : (
                        <AiAnalysisIcon fontSize="small" />
                      )}
                    </IconButton>
                  </Tooltip>
                ) : (
                  <Tooltip title="Process file">
                    <IconButton 
                      edge="end" 
                      size="small" 
                      color="primary"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleAnalyze(file);
                      }}
                      sx={{ 
                        bgcolor: 'rgba(144, 202, 249, 0.08)',
                        '&:hover': {
                          bgcolor: 'rgba(144, 202, 249, 0.2)',
                        }
                      }}
                    >
                      <PlayArrowIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                )}
              </ListItemSecondaryAction>
            </ListItem>
          );
        })}
              </List>
            </AccordionDetails>
          </Accordion>
        ))}
      </Box>
    );
  }

  return (
    <Paper elevation={0} sx={{ 
      padding: 2, 
      backgroundColor: 'transparent', 
      borderRadius: 3,
      height: '100%',
    }}>
      <Typography 
        variant="h6" 
        gutterBottom 
        component="div"
        sx={{ px: 1, mb: 1.5, fontWeight: 500, display: 'flex', alignItems: 'center' }}
      >
        <InsertDriveFileIcon sx={{ mr: 1, fontSize: 18 }} />
        Uploaded Files
        {files.length > 0 && (
          <Chip 
            label={files.length} 
            size="small" 
            color="primary" 
            sx={{ ml: 1, height: 20, minWidth: 20, fontSize: '0.7rem' }}
          />
        )}
      </Typography>
      {content}
    </Paper>
  );
};

export default FileList;
