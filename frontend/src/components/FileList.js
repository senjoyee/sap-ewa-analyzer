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
import Checkbox from '@mui/material/Checkbox';
import Accordion from '@mui/material/Accordion';
import AccordionSummary from '@mui/material/AccordionSummary';
import AccordionDetails from '@mui/material/AccordionDetails';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import FolderIcon from '@mui/icons-material/Folder';
import BusinessIcon from '@mui/icons-material/Business';
import { useTheme } from '../contexts/ThemeContext';
import dayjs from 'dayjs';
import weekOfYear from 'dayjs/plugin/weekOfYear';
import ListSubheader from '@mui/material/ListSubheader';



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
import VisibilityIcon from '@mui/icons-material/Visibility';
import RefreshIcon from '@mui/icons-material/Refresh';
import DeleteIcon from '@mui/icons-material/Delete';

// Initialise weekOfYear plugin after all imports
dayjs.extend(weekOfYear);

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

const API_BASE = 'https://sap-ewa-analyzer-backend.azurewebsites.net/';

const FileList = ({ onFileSelect, refreshTrigger, selectedFile }) => {
  const [files, setFiles] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [analyzingFiles, setAnalyzingFiles] = useState({}); // Track analysis status for each file
  const [analysisProgress, setAnalysisProgress] = useState({}); // Track progress for each file
  const [expandedCustomers, setExpandedCustomers] = useState({});
  const [aiAnalyzing, setAiAnalyzing] = useState({}); // Track AI analysis status for each file
  const [combinedProcessingStatus, setCombinedProcessingStatus] = useState({}); // Track combined processing & AI analysis status
  const [reprocessingFiles, setReprocessingFiles] = useState({}); // Track reprocessing status for each file
  const [selectedFiles, setSelectedFiles] = useState([]);
  const pollingIntervalsRef = useRef({});
  const { theme } = useTheme();
  const isDark = theme === 'dark';
  
  // Function to handle file selection with checkbox
  const handleFileSelection = (file, event) => {
    // Stop event propagation to prevent triggering row click
    if (event) {
      event.stopPropagation();
    }
    
    setSelectedFiles(prev => {
      const fileId = file.id || file.name;
      if (prev.some(f => (f.id || f.name) === fileId)) {
        // If file is already selected, remove it
        return prev.filter(f => (f.id || f.name) !== fileId);
      } else {
        // Otherwise add it to selection
        return [...prev, file];
      }
    });
  };
  
  // Check if a file is selected
  const isFileSelected = (file) => {
    const fileId = file.id || file.name;
    return selectedFiles.some(f => (f.id || f.name) === fileId);
  };
  
  // Handle select all files
  const handleSelectAllFiles = () => {
    setSelectedFiles([...files]);
  };
  
  // Handle deselect all files
  const handleDeselectAllFiles = () => {
    setSelectedFiles([]);
  };
  
  // Calculate if any files are selected and how many are analyzed
  const selectedCount = selectedFiles.length;
  const selectedAnalyzedCount = selectedFiles.filter(file => file.ai_analyzed).length;
  
  // Handle batch delete of selected analyzed files
  const handleBatchDelete = async () => {
    const analyzedFiles = selectedFiles.filter(file => file.ai_analyzed);
    
    if (analyzedFiles.length === 0) {
      alert('No analyzed files selected for deletion.');
      return;
    }
    
    const confirmDelete = window.confirm(
      `Are you sure you want to delete analysis for ${analyzedFiles.length} file(s)? This action cannot be undone.`
    );
    
    if (!confirmDelete) {
      return;
    }
    
    let successCount = 0;
    let errorCount = 0;
    
    // Process each file sequentially
    for (const file of analyzedFiles) {
      try {
        const baseName = file.name.split('.').slice(0, -1).join('.');
        
        const response = await fetch(`${API_BASE}/api/delete-analysis`, {
          method: 'DELETE',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            fileName: file.name,
            baseName: baseName
          })
        });
        
        if (!response.ok) {
          throw new Error(`Server responded with ${response.status}`);
        }
        
        successCount++;
      } catch (error) {
        console.error(`Error deleting analysis for ${file.name}:`, error);
        errorCount++;
      }
    }
    
    // Update UI after all deletions are processed
    setFiles(prevFiles => prevFiles.map(f => {
      if (selectedFiles.some(selected => (selected.id || selected.name) === (f.id || f.name)) && f.ai_analyzed) {
        // Reset the AI analysis flag for selected files
        return { ...f, ai_analyzed: false };
      }
      return f;
    }));
    
    // Clear selection after operation
    setSelectedFiles([]);
    
    // Show summary of operation
    alert(`Operation completed: ${successCount} analyses deleted, ${errorCount} errors encountered.`);
  };
  
  // Handle batch reprocess of selected files
  const handleBatchReprocess = async () => {
    const filesToReprocess = selectedFiles.filter(file => file.ai_analyzed);
    
    if (filesToReprocess.length === 0) {
      alert('No analyzed files selected for reprocessing.');
      return;
    }
    
    const confirmReprocess = window.confirm(
      `Are you sure you want to reprocess ${filesToReprocess.length} file(s)?`
    );
    
    if (!confirmReprocess) {
      return;
    }
    
    // Update UI to show reprocessing state
    const newReprocessingState = {};
    filesToReprocess.forEach(file => {
      newReprocessingState[file.id || file.name] = true;
    });
    
    setReprocessingFiles(prev => ({
      ...prev,
      ...newReprocessingState
    }));
    
    // Process each file sequentially
    for (const file of filesToReprocess) {
      try {
        await handleReprocessAI(file, false); // Pass false to prevent alerts for each file
      } catch (error) {
        console.error(`Error reprocessing file ${file.name}:`, error);
      }
    }
    
    // Clear selection after operation
    setSelectedFiles([]);
    
    // Show completion message
    alert(`Reprocessing initiated for ${filesToReprocess.length} file(s).`);
  };
  
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

  // ---- Time-based grouping helpers ----
  const getWeekKey = (file) => {
    if (!file.report_date) return 'Unknown';
    const d = dayjs(file.report_date);
    if (!d.isValid()) return 'Unknown';
    return `${d.year()}-W${String(d.week()).padStart(2, '0')}`;
  };

  const groupByWeek = (files) => {
    const grouped = {};
    files.forEach(f => {
      const key = getWeekKey(f);
      if (!grouped[key]) grouped[key] = [];
      grouped[key].push(f);
    });
    return grouped;
  };

  // Month grouping helpers
  const getMonthKey = (file) => {
    if (!file.report_date) return 'Unknown';
    const d = dayjs(file.report_date);
    return d.isValid() ? d.format('YYYY-MM') : 'Unknown';
  };

  const groupByMonth = (files) => {
    const grouped = {};
    files.forEach(f => {
      const key = getMonthKey(f);
      if (!grouped[key]) grouped[key] = [];
      grouped[key].push(f);
    });
    return grouped;
  };

  // Function to handle accordion expand/collapse
  const handleAccordionChange = (customer) => (event, isExpanded) => {
    setExpandedCustomers(prev => ({
      ...prev,
      [customer]: isExpanded
    }));
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
      const response = await fetch(`${API_BASE}/api/analyze`, {
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
      const response = await fetch(`${API_BASE}/api/analyze-ai`, {
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

  // Function to handle reprocessing of AI analysis
  const handleReprocessAI = async (file, showAlerts = true) => {
    console.log(`Reprocessing AI analysis for file: ${file.name}`);
    
    // Confirm reprocessing with the user (skip if in batch mode)
    if (showAlerts && !window.confirm(`This will delete the existing AI analysis for "${file.name}" and create a new one. Continue?`)) {
      return; // User cancelled
    }
    
    // Set status to reprocessing
    setReprocessingFiles(prev => ({
      ...prev,
      [file.id || file.name]: true
    }));
    
    try {
      // Make API call to reprocess with AI
      const response = await fetch(`${API_BASE}/api/reprocess-ai`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ blob_name: file.name }),
      });
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || `AI Reprocessing failed: ${response.status}`);
      }
      
      const result = await response.json();
      console.log('AI Reprocessing result:', result);
      
      // Clear reprocessing status
      setReprocessingFiles(prev => ({
        ...prev,
        [file.id || file.name]: false
      }));
      
      // Show success message (if not in batch mode)
      if (showAlerts) {
        alert(`Reprocessing of ${file.name} started successfully.`);
      }
      
    } catch (error) {
      console.error(`Error in AI reprocessing for file ${file.name}:`, error);
      // Clear reprocessing status on error
      setReprocessingFiles(prev => ({
        ...prev,
        [file.id || file.name]: false
      }));
      
      // Show error message if not in batch mode
      if (showAlerts) {
        alert(`Error in AI reprocessing: ${error.message}`);
      }
    }
  };

  // Function to handle displaying AI analysis
  const handleDisplayAnalysis = async (file) => {
    console.log(`Displaying AI analysis for file: ${file.name}`);
    
    try {
      // Construct the AI analysis file name
      const baseName = file.name.split('.').slice(0, -1).join('.');
      const aiFileName = `${baseName}_AI.md`;
      
      // Make API call to fetch the AI analysis content
      const response = await fetch(`${API_BASE}/api/download/${aiFileName}`, {
        method: 'GET',
      });
      
      if (!response.ok) {
        throw new Error(`Failed to fetch AI analysis: ${response.status}`);
      }
      
      const analysisContent = await response.text();
      
      // Call onFileSelect with just the analysis content and type
      // No longer fetching metrics or parameters as these are no longer generated
      onFileSelect({
        ...file,
        analysisContent,
        displayType: 'analysis'
      });
      
    } catch (error) {
      console.error(`Error fetching AI analysis for file ${file.name}:`, error);
      alert(`Error fetching AI analysis: ${error.message}`);
    }
  };

  // PDF export functionality moved to FilePreview component

  // Function to handle deletion of an analysis and all related files
  const handleDeleteAnalysis = async (file, showAlerts = true) => {
    // Confirm before deletion (skip if in batch mode)
    if (showAlerts) {
      const confirmDelete = window.confirm(`Are you sure you want to delete the analysis for ${file.name}? This action cannot be undone.`);
      
      if (!confirmDelete) {
        return; // User cancelled the deletion
      }
    }
    
    try {
      const baseName = file.name.split('.').slice(0, -1).join('.');
      
      // Determine API base URL
      const API_BASE = (process.env.REACT_APP_API_BASE || window.__ENV__?.REACT_APP_API_BASE || 'http://localhost:8001').replace(/\/$/, '');
      
      // Call the backend to delete all related files from blob storage
      const response = await fetch(`${API_BASE}/api/delete-analysis`, {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          fileName: file.name,
          baseName: baseName
        })
      });
      
      if (!response.ok) {
        throw new Error(`Server responded with ${response.status}: ${await response.text()}`);
      }
      
      // Update the UI after successful deletion
      setFiles(prevFiles => prevFiles.map(f => {
        if (f.id === file.id || f.name === file.name) {
          // Reset the AI analysis flag
          return { ...f, ai_analyzed: false };
        }
        return f;
      }));
      
      // Show success message (if not in batch mode)
      if (showAlerts) {
        alert(`Successfully deleted analysis for ${file.name}`);
      }
      
    } catch (error) {
      console.error(`Error deleting analysis for ${file.name}:`, error);
      if (showAlerts) {
        alert(`Failed to delete analysis: ${error.message}`);
      }
    }
  };

  // Function to handle combined processing and AI analysis
  const handleProcessAndAnalyze = async (file) => {
    console.log(`Starting combined processing and AI analysis for file: ${file.name}`);
    setCombinedProcessingStatus(prev => ({
      ...prev,
      [file.id || file.name]: 'processing'
    }));

    try {
      const response = await fetch(`${API_BASE}/api/process-and-analyze`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ blob_name: file.name }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        // Try to get a specific message from the backend, otherwise use a generic one
        const message = errorData.detail || (errorData.message || `Combined processing and analysis failed: ${response.status}`);
        throw new Error(message);
      }

      const result = await response.json();
      console.log('Combined Processing and AI Analysis result:', result);

      setCombinedProcessingStatus(prev => ({
        ...prev,
        [file.id || file.name]: 'completed'
      }));

      // Update the file in the main 'files' state to reflect new status and analysis file name
      setFiles(currentFiles =>
        currentFiles.map(f =>
          (f.id || f.name) === (file.id || file.name)
            ? { ...f, processed: true, ai_analyzed: true, analysis_file: result.summary_file, /* any other fields from result if needed */ } 
            : f
        )
      );
      
      // Also update the individual status trackers if they are still used elsewhere or for consistency
      setAnalyzingFiles(prev => ({ ...prev, [file.id || file.name]: 'analyzed' }));
      setAiAnalyzing(prev => ({ ...prev, [file.id || file.name]: 'completed' }));

      alert(`Processing and AI Analysis for ${file.name} completed successfully! Analysis saved as: ${result.summary_file}`);

    } catch (error) {
      console.error(`Error in combined processing and AI analysis for file ${file.name}:`, error);
      setCombinedProcessingStatus(prev => ({
        ...prev,
        [file.id || file.name]: 'error'
      }));
      alert(`Error in combined processing and AI analysis for ${file.name}: ${error.message}`);
    }
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
        const response = await fetch(`${API_BASE}/api/analysis-status/${encodeURIComponent(fileName)}`);
        
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
      const response = await fetch(`${API_BASE}/api/files`);
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
      const aiStatusMap = {};
      
      filesWithIds.forEach(file => {
        // Use the 'processed' flag directly from the backend
        // Set status to 'analyzed' if processed is true, otherwise 'pending'
        console.log(`File ${file.name} processed status:`, file.processed, "AI analyzed:", file.ai_analyzed);
        statusMap[file.id || file.name] = file.processed ? 'analyzed' : 'pending';
        
        // Set AI analysis status based on backend data
        if (file.ai_analyzed) {
          aiStatusMap[file.id || file.name] = 'completed';
        }
      });
      
      setAnalyzingFiles(statusMap);
      setAiAnalyzing(prev => ({
        ...prev,
        ...aiStatusMap
      }));

      const newCombinedStatus = {};
      filesWithIds.forEach(file => {
        if (file.ai_analyzed) {
          newCombinedStatus[file.id || file.name] = 'completed';
        } else {
          newCombinedStatus[file.id || file.name] = 'idle';
        }
      });
      setCombinedProcessingStatus(newCombinedStatus);
      
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
        
        {/* Customer accordions */}
        {Object.keys(filesByCustomer).map((customer) => (
          <Accordion 
            key={customer}
            expanded={expandedCustomers[customer] === true}
            onChange={handleAccordionChange(customer)}
            elevation={0}
            sx={{ 
              mb: 1,
              backgroundColor: '#ffffff',
              border: '1px solid #e5e5e5',
              borderRadius: '8px !important',
              overflow: 'hidden',
              '&:before': {
                display: 'none',
              },
              '&.Mui-expanded': {
                margin: '0 0 8px 0',
              }
            }}
          >
            <AccordionSummary 
              expandIcon={<ExpandMoreIcon sx={{ color: '#0070b1' }} />}
              sx={{ 
                minHeight: 48,
                backgroundColor: '#f7f7f7',
                borderBottom: '1px solid #e5e5e5',
                '&.Mui-expanded': {
                  minHeight: 48,
                },
                '& .MuiAccordionSummary-content': {
                  margin: '12px 0',
                  '&.Mui-expanded': {
                    margin: '12px 0',
                  }
                }
              }}
            >
              <Box sx={{ display: 'flex', alignItems: 'center', width: '100%' }}>
                <BusinessIcon sx={{ 
                  mr: 1.5, 
                  fontSize: 20,
                  color: '#0070b1'
                }} />
                <Typography sx={{ 
                  fontWeight: 500,
                  fontSize: '0.9rem',
                  color: '#32363a'
                }}>
                  {customer}
                </Typography>
                <Chip 
                  label={filesByCustomer[customer].length} 
                  size="small" 
                  sx={{ 
                    ml: 'auto',
                    mr: 1,
                    height: 20,
                    minWidth: 20,
                    fontSize: '0.7rem',
                    fontWeight: 600,
                    backgroundColor: '#f0f8ff',
                    color: '#0070b1',
                    border: '1px solid #0070b1',
                  }}
                />
              </Box>
            </AccordionSummary>
            <AccordionDetails sx={{ p: 1, backgroundColor: '#ffffff' }}>
              <List sx={{ py: 0 }}>
                {Object.entries(groupByMonth(filesByCustomer[customer]))
                  .sort(([aKey],[bKey]) => {
                    if (aKey === 'Unknown') return 1;
                    if (bKey === 'Unknown') return -1;
                    return dayjs(aKey + '-01').isBefore(dayjs(bKey + '-01')) ? -1 : 1;
                  })
                  .map(([monthKey, monthFiles]) => {
                    return (
                      <React.Fragment key={monthKey}>
                      <ListSubheader component="div" sx={{ backgroundColor: '#f7f7f7', color: '#0070b1', borderTop: '1px solid #e5e5e5', borderBottom: '1px solid #e5e5e5' }}>
                        {monthKey === 'Unknown' ? 'Unknown' : dayjs(monthKey + '-01').format('MMMM YYYY')}
                      </ListSubheader>
                      {monthFiles.map((file) => {
                        const isSelected = selectedFile && (selectedFile.id === file.id || selectedFile.name === file.name);
                        return (
                          <ListItem 
                            key={file.id || file.name} 
                            disablePadding 
                            sx={{ 
                              position: 'relative', 
                              mb: 0.5,
                              '&:last-child': { mb: 0 }
                            }}
                          >
                            <ListItemButton 
                              onClick={(e) => {
                                // Don't select if clicking checkbox
                                if (e.target.tagName !== 'INPUT' && !e.target.closest('.MuiCheckbox-root')) {
                                  onFileSelect(file);
                                }
                              }}
                              selected={isSelected}
                              sx={{
                                pr: 16, // Standard padding for secondary action
                                mx: 0.5,
                                borderRadius: 1,
                                minHeight: 64,
                                transition: 'all 0.2s',
                                backgroundColor: '#ffffff',
                                border: '1px solid #e5e5e5',
                                '&.Mui-selected': {
                                  backgroundColor: '#eaf3fa',
                                  borderColor: '#0070b1',
                                  '&:hover': {
                                    backgroundColor: '#d8e9f5',
                                  }
                                },
                                '&:hover': {
                                  backgroundColor: '#f7f7f7',
                                  borderColor: '#d0d0d0',
                                }
                              }}
                            >
                              <ListItemIcon sx={{ minWidth: 40, display: 'flex', alignItems: 'center' }}>
                                <Checkbox 
                                  checked={isFileSelected(file)}
                                  onChange={(e) => {
                                    e.stopPropagation();
                                    handleFileSelection(file, e);
                                  }}
                                  size="small"
                                  sx={{ 
                                    p: 0.5,
                                    color: '#0070b1',
                                    mr: 1
                                  }}
                                />
                                {getFileIcon(file.name)}
                              </ListItemIcon>
                              <Tooltip title={file.name} placement="top-start">
                                <ListItemText 
                                  primary={
                                    <Typography sx={{ 
                                      fontSize: '0.875rem',
                                      fontWeight: 500,
                                      color: '#32363a',
                                      overflow: 'hidden',
                                      textOverflow: 'ellipsis',
                                      whiteSpace: 'nowrap'
                                    }}>
                                      {file.name}
                                    </Typography>
                                  }
                                  secondary={
                                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mt: 0.5 }}>
                                      <Typography variant="caption" sx={{ color: '#6a6d70' }}>
                                        {formatFileSize(file.size)}
                                      </Typography>
                                      {file.customer_name && (
                                        <Typography variant="caption" sx={{ color: '#6a6d70' }}>
                                          • {file.customer_name}
                                        </Typography>
                                      )}
                                    </Box>
                                  }
                                />
                              </Tooltip>
                            </ListItemButton>
                            <ListItemSecondaryAction sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                              {combinedProcessingStatus[file.id || file.name] === 'processing' ? (
                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, minWidth: 100, justifyContent: 'center' }}>
                                  <CircularProgress size={20} thickness={4} color="primary" />
                                  <Typography variant="caption" color="text.secondary">Processing...</Typography>
                                </Box>
                              ) : (combinedProcessingStatus[file.id || file.name] === 'completed' || file.ai_analyzed) ? (
                                <Box sx={{ display: 'flex', gap: 0.5 }}>
                                  {reprocessingFiles[file.id || file.name] ? (
                                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                      <CircularProgress size={16} thickness={4} color="primary" />
                                      <Typography variant="caption" color="text.secondary">Reprocessing...</Typography>
                                    </Box>
                                  ) : (
                                    <>
                                      <Tooltip title="Display AI Analysis">
                                        <Button
                                          variant="contained"
                                          size="small"
                                          color="success"
                                          onClick={(e) => {
                                            e.stopPropagation();
                                            handleDisplayAnalysis(file);
                                          }}
                                          sx={{ textTransform: 'none', minWidth: '32px', width: '32px', height: '32px', p: 0 }}
                                        >
                                          <VisibilityIcon fontSize="small" />
                                        </Button>
                                      </Tooltip>
                                    </>
                                  )}
                                </Box>
                              ) : (
                                /* Covers 'idle', 'error', or undefined states for combinedProcessingStatus and file not ai_analyzed */
                                <Tooltip title={combinedProcessingStatus[file.id || file.name] === 'error' ? "Retry Processing and Analysis" : "Process and Analyze Document"}>
                                  <Button
                                    variant="contained"
                                    size="small"
                                    color={combinedProcessingStatus[file.id || file.name] === 'error' ? "error" : "primary"}
                                    startIcon={<PlayArrowIcon fontSize="small" />}
                                    onClick={() => handleProcessAndAnalyze(file)}
                                    sx={{ textTransform: 'none', fontSize: '0.75rem', py: 0.5, px:1, minWidth: 'auto' }}
                                  >
                                    {combinedProcessingStatus[file.id || file.name] === 'error' ? "Retry" : "Process"}
                                  </Button>
                                </Tooltip>
                              )}
                            </ListItemSecondaryAction>
                          </ListItem>
                        );
                      })}
                    </React.Fragment>
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
    <Box sx={{ 
      display: 'flex',
      flexDirection: 'column',
      height: '100%',
      gap: 2
    }}>
      <Box sx={{ 
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        mb: 1
      }}>
        <Typography 
          variant="subtitle1" 
          sx={{ 
            fontWeight: 600,
            color: '#32363a',
            fontSize: '0.95rem',
            display: 'flex',
            alignItems: 'center',
            gap: 1
          }}
        >
          <FolderIcon sx={{ fontSize: 20, color: '#0070b1' }} />
          Uploaded Files
          {files.length > 0 && (
            <Chip 
              label={files.length} 
              size="small" 
              sx={{ 
                ml: 0.5,
                height: 20,
                minWidth: 20,
                fontSize: '0.7rem',
                fontWeight: 600,
                backgroundColor: '#f0f8ff',
                color: '#0070b1',
                border: '1px solid #0070b1',
              }}
            />
          )}
        </Typography>
        <Box sx={{ display: 'flex', gap: 0.5 }}>
          <Button
            size="small"
            onClick={() => {
              const allExpanded = {};
              const filesByCustomer = groupByCustomer(files);
              Object.keys(filesByCustomer).forEach(customer => {
                allExpanded[customer] = true;
              });
              setExpandedCustomers(allExpanded);
            }}
            sx={{ 
              fontSize: '0.75rem',
              textTransform: 'none',
              color: '#666',
              minWidth: 'auto',
              px: 1,
              '&:hover': {
                backgroundColor: 'rgba(0,0,0,0.04)',
              }
            }}
          >
            EXPAND ALL
          </Button>
          <Button
            size="small"
            onClick={() => setExpandedCustomers({})}
            sx={{ 
              fontSize: '0.75rem',
              textTransform: 'none',
              color: '#666',
              minWidth: 'auto',
              px: 1,
              '&:hover': {
                backgroundColor: 'rgba(0,0,0,0.04)',
              }
            }}
          >
            COLLAPSE ALL
          </Button>
        </Box>
      </Box>
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1, mb: 1 }}>
        {/* Selection info and controls */}
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Typography variant="body2" sx={{ color: '#6a6d70' }}>
            {selectedCount} selected ({selectedAnalyzedCount} analyzed)
          </Typography>
          <Box sx={{ display: 'flex', gap: 0.5 }}>
            <Button
              size="small"
              onClick={() => handleSelectAllFiles()}
              sx={{ 
                fontSize: '0.75rem',
                textTransform: 'none',
                color: '#666',
                minWidth: 'auto',
                px: 1,
                '&:hover': {
                  backgroundColor: 'rgba(0,0,0,0.04)',
                }
              }}
            >
              SELECT ALL
            </Button>
            <Button
              size="small"
              onClick={() => handleDeselectAllFiles()}
              sx={{ 
                fontSize: '0.75rem',
                textTransform: 'none',
                color: '#666',
                minWidth: 'auto',
                px: 1,
                '&:hover': {
                  backgroundColor: 'rgba(0,0,0,0.04)',
                }
              }}
            >
              DESELECT ALL
            </Button>
          </Box>
        </Box>
        
        {/* Batch action buttons */}
        {selectedCount > 0 && (
          <Box sx={{ display: 'flex', gap: 1, justifyContent: 'flex-end' }}>
            {selectedAnalyzedCount > 0 && (
              <Button
                variant="contained"
                color="error"
                size="small"
                startIcon={<DeleteIcon fontSize="small" />}
                onClick={handleBatchDelete}
                sx={{ 
                  textTransform: 'none',
                  fontSize: '0.8125rem',
                  py: 0.6,
                  px: 1.5,
                  borderRadius: 1.5,
                  boxShadow: '0 2px 8px rgba(220, 38, 38, 0.25)',
                  background: 'linear-gradient(to right bottom, #ef4444, #dc2626)',
                  '&:hover': {
                    boxShadow: '0 4px 12px rgba(220, 38, 38, 0.4)',
                    background: 'linear-gradient(to right bottom, #dc2626, #b91c1c)',
                  },
                  transition: 'all 0.2s ease-in-out',
                }}
              >
                Delete Selected
              </Button>
            )}
            <Button
              variant="contained"
              color="primary"
              size="small"
              startIcon={<RefreshIcon fontSize="small" />}
              onClick={handleBatchReprocess}
              sx={{ 
                textTransform: 'none',
                fontSize: '0.8125rem',
                py: 0.6,
                px: 1.5,
                borderRadius: 1.5,
                boxShadow: '0 2px 8px rgba(37, 99, 235, 0.25)',
                background: 'linear-gradient(to right bottom, #3b82f6, #2563eb)',
                '&:hover': {
                  boxShadow: '0 4px 12px rgba(37, 99, 235, 0.4)',
                  background: 'linear-gradient(to right bottom, #2563eb, #1d4ed8)',
                },
                transition: 'all 0.2s ease-in-out',
              }}
            >
              Reprocess Selected
            </Button>
          </Box>
        )}
      </Box>
      <Paper 
        elevation={0} 
        sx={{ 
          flex: 1,
          overflow: 'auto',
          backgroundColor: '#1a1a1a',
          border: '1px solid #333333',
          borderRadius: 2,
          '&::-webkit-scrollbar': {
            width: '6px',
          },
          '&::-webkit-scrollbar-track': {
            background: '#1a1a1a',
          },
          '&::-webkit-scrollbar-thumb': {
            background: '#333333',
            borderRadius: '3px',
            '&:hover': {
              background: '#444444',
            },
          },
        }}
      >
        {content}
      </Paper>
    </Box>
  );
};

export default FileList;
