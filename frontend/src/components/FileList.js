import React, { useState, useEffect, useRef } from 'react';
import { Button as FluentButton, Spinner, Tooltip as FluentTooltip, CounterBadge, Accordion as FluentAccordion, AccordionItem, AccordionHeader, AccordionPanel, Checkbox } from '@fluentui/react-components';
import { makeStyles } from '@griffel/react';
import { Alert as FluentAlert } from '@fluentui/react-alert';
import { Toaster, useToastController, Toast, ToastTitle } from '@fluentui/react-toast';
import { Delete24Regular, Play24Regular, Document24Regular, DocumentPdf24Regular, Image24Regular, TextDescription24Regular, ChevronDown24Regular, Building24Regular, Folder24Regular } from '@fluentui/react-icons';
 
 
// Replaced MUI Button with Fluent UI Button
 
 
import { useTheme } from '../contexts/ThemeContext';
import { apiUrl } from '../config';
import dayjs from 'dayjs';
import weekOfYear from 'dayjs/plugin/weekOfYear';



// File type icons
 

// Action and status icons
 
// Replaced MUI Delete/Play icons with Fluent UI icons

// Initialise weekOfYear plugin after all imports
dayjs.extend(weekOfYear);

// Styles (Griffel)
const useStyles = makeStyles({
  root: {
    display: 'flex',
    flexDirection: 'column',
    height: '100%',
    gap: '16px',
  },
  headerBar: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  title: {
    fontWeight: 600,
    color: '#32363a',
    fontSize: '0.85rem',
    display: 'flex',
    alignItems: 'center',
    gap: 8,
  },
  actionButtons: {
    display: 'flex',
    gap: 4,
  },
  selectionSection: {
    display: 'flex',
    flexDirection: 'column',
    gap: 8,
    marginBottom: 8,
  },
  selectionRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  selectionText: {
    color: '#6a6d70',
  },
  batchActions: {
    display: 'flex',
    gap: 8,
    justifyContent: 'flex-end',
    alignItems: 'center',
  },
  listContainer: {
    flex: 1,
    overflow: 'auto',
    backgroundColor: '#f5f5f5',
    border: '1px solid #e5e5e5',
    borderRadius: '8px',
    selectors: {
      '&::-webkit-scrollbar': { width: '6px' },
      '&::-webkit-scrollbar-track': { background: '#f5f5f5' },
      '&::-webkit-scrollbar-thumb': { background: '#d0d0d0', borderRadius: '3px' },
      '&::-webkit-scrollbar-thumb:hover': { background: '#b0b0b0' },
    },
  },
  loadingCenter: {
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 12,
    minHeight: 120,
  },
  alertWrapper: {
    padding: 8,
  },
  alert: {
    borderRadius: 8,
  },
  emptyState: {
    padding: 8,
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    paddingTop: 16,
    paddingBottom: 16,
    minHeight: 120,
  },
  emptyIcon: {
    width: 40,
    height: 40,
    opacity: 0.6,
    marginBottom: 8,
  },
  emptyText: {
    color: '#6a6d70',
    fontSize: '0.8rem',
    textAlign: 'center',
  },
  headerFolderIcon: {
    width: 18,
    height: 18,
    color: '#60a5fa',
  },
  titleBadgeSpacing: {
    marginLeft: 4,
  },
  accordionHeader: {
    minHeight: 44,
    backgroundColor: '#f8f9fa',
    borderBottom: '1px solid #e5e5e5',
  },
  accordionHeaderContent: {
    display: 'flex',
    alignItems: 'center',
    width: '100%',
  },
  brandIcon: {
    color: '#60a5fa',
  },
  leadingIcon: {
    marginRight: 12,
    width: 18,
    height: 18,
    color: '#60a5fa',
  },
  customerName: {
    fontWeight: 500,
    fontSize: '0.875rem',
    color: '#32363a',
  },
  headerBadge: {
    marginLeft: 'auto',
    marginRight: 8,
  },
  accordionPanel: {
    padding: 4,
    backgroundColor: '#ffffff',
  },
  itemWrapper: {
    position: 'relative',
    marginBottom: 4,
  },
  itemRow: {
    display: 'flex',
    alignItems: 'center',
    paddingRight: 12,
    marginInline: 4,
    borderRadius: 8,
    minHeight: 48,
    transition: 'all 0.2s ease',
    cursor: 'pointer',
    selectors: {
      '&:hover': { backgroundColor: 'rgba(96, 165, 250, 0.08)' },
      '&:focus-visible': { outline: '2px solid #60a5fa', outlineOffset: 2 },
    },
  },
  itemRowSelected: {
    backgroundColor: 'rgba(96, 165, 250, 0.1)',
  },
  checkboxCell: {
    minWidth: 36,
    display: 'flex',
    alignItems: 'center',
  },
  fileIconCell: {
    minWidth: 28,
    color: 'rgba(0, 0, 0, 0.54)',
  },
  itemDetails: {
    flex: 1,
    minWidth: 0,
  },
  itemTitle: {
    fontSize: '0.9rem',
    color: '#32363a',
    whiteSpace: 'nowrap',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
  },
  itemMeta: {
    color: '#6a6d70',
    fontSize: '0.8rem',
  },
  itemStatus: {
    marginLeft: 'auto',
    display: 'flex',
    alignItems: 'center',
    gap: 4,
  },
  successIcon: {
    color: '#10b981',
  },
  errorIcon: {
    color: '#ef4444',
  },
  fileTypeIcon: {
    width: 16,
    height: 16,
  },
  fileTypeIconMuted: {
    width: 16,
    height: 16,
    opacity: 0.6,
  },
});

// Helper function to get appropriate icon for file type
const getFileIcon = (filename, classes) => {
  // Extract extension from filename
  const fileExtension = filename && typeof filename === 'string' 
    ? filename.split('.').pop().toLowerCase() 
    : '';
  
  // Debug the extension extraction
  console.log(`File: ${filename}, Extension detected: ${fileExtension}`);
  
  switch(fileExtension) {
    case 'pdf':
      return <DocumentPdf24Regular className={classes.fileTypeIcon} />;
    case 'jpg':
    case 'jpeg':
    case 'png':
    case 'gif':
    case 'bmp':
      return <Image24Regular className={classes.fileTypeIcon} />;
    case 'doc':
    case 'docx':
      return <Document24Regular className={classes.fileTypeIcon} />;
    case 'txt':
      return <TextDescription24Regular className={classes.fileTypeIcon} />;
    default:
      return <Document24Regular className={classes.fileTypeIconMuted} />;
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

// API base is centralized in src/config.js

 

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
  const classes = useStyles();
  
  // Toast controller (Fluent UI Toast)
  const { dispatchToast } = useToastController('fileListToaster');
  
  // Keep the same API but dispatch a Fluent Toast instead
  const showSnackbar = (message, severity = 'info') => {
    const intent = severity; // maps directly: 'success' | 'error' | 'warning' | 'info'
    dispatchToast(
      <Toast intent={intent}>
        <ToastTitle>{message}</ToastTitle>
      </Toast>,
      { position: 'bottom', timeout: 4000 }
    );
  };
  
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
      showSnackbar('No analyzed files selected for deletion.', 'warning');
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
        
        const response = await fetch(apiUrl('/api/delete-analysis'), {
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
    
    // Refresh the file list to show updated files after deletion
    await fetchFiles();
    
    // Clear selection after operation
    setSelectedFiles([]);
    
    // Show summary of operation
    const severity = errorCount > 0 ? 'warning' : 'success';
    showSnackbar(`Operation completed: ${successCount} analyses deleted, ${errorCount} errors encountered.`, severity);
  };
  
  // Handle batch process of selected files (both new and already processed)
  const handleBatchProcess = async () => {
    if (selectedFiles.length === 0) {
      showSnackbar('No files selected for processing.', 'warning');
      return;
    }

    // Show initiation message IMMEDIATELY
    showSnackbar(`Processing initiated for ${selectedFiles.length} file(s).`, 'info');

    // Mark all selected files as processing in UI
    setCombinedProcessingStatus(prev => {
      const updated = { ...prev };
      selectedFiles.forEach(file => {
        updated[file.id || file.name] = 'processing';
      });
      return updated;
    });
    
    // Process selected files with a concurrency limit (pool of 3)
    const filesToProcess = [...selectedFiles];
    const concurrency = 3;
    let index = 0;
    const worker = async () => {
      while (true) {
        const i = index;
        if (i >= filesToProcess.length) break;
        index = i + 1;
        const file = filesToProcess[i];
        try {
          await handleProcessAndAnalyze(file);
        } catch (error) {
          console.error(`Error processing ${file.name}:`, error);
        }
      }
    };
    const workers = Array.from({ length: Math.min(concurrency, filesToProcess.length) }, () => worker());
    await Promise.all(workers);
    
    // Clear selection after operation
    setSelectedFiles([]);
    
    // Show completion message (optional, can be removed if not needed)
    // const totalFiles = selectedFiles.length;
    // alert(`Processing initiated for ${totalFiles} file(s).`);
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

  

  // Function to handle analyze button click
  const handleAnalyze = async (file) => {
    console.log(`Analyzing file (PDF-first): ${file.name}`);

    // Mark as analyzing in UI, then delegate to combined PDF-first workflow
    setAnalyzingFiles(prev => ({
      ...prev,
      [file.id || file.name]: 'analyzing'
    }));

    await handleProcessAndAnalyze(file);
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
      const response = await fetch(apiUrl('/api/analyze-ai'), {
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
      
      // Show success message with fallback for undefined analysis_file
      const analysisFileName = result.analysis_file || `${file.name.split('.').slice(0, -1).join('.')}_AI.md`;
      showSnackbar(`AI Analysis completed successfully! Analysis saved as: ${analysisFileName}`, 'success');
      
    } catch (error) {
      console.error(`Error in AI analysis for file ${file.name}:`, error);
      // Set status back to ready on error
      setAiAnalyzing(prev => ({
        ...prev,
        [file.id || file.name]: 'error'
      }));
      showSnackbar(`Error in AI analysis: ${error.message}`, 'error');
    }
  };

  // Function to handle displaying AI analysis - replaces Display button logic
  const handleDisplayAnalysis = async (file) => {
    
    try {
      // Only proceed if the file is AI analyzed
      if (!file.ai_analyzed) {
        console.log('File not AI analyzed, selecting normally');
        onFileSelect(file);
        return;
      }

      // Construct the AI analysis file name
      const baseName = file.name.split('.').slice(0, -1).join('.');
      const aiFileName = `${baseName}_AI.md`;
      
      // Fetch the AI analysis content
      const response = await fetch(apiUrl(`/api/download/${aiFileName}`));
      
      if (!response.ok) {
        throw new Error(`Failed to fetch AI analysis: ${response.status}`);
      }
      
      const analysisContent = await response.text();
      console.log(`Loaded analysis content: ${analysisContent.length} characters`);
      
      // Create enriched file object with analysis data
      const enrichedFile = {
        ...file,
        analysisContent: analysisContent,
        displayType: 'analysis' // This tells FilePreview to show analysis view
      };
      
      // Pass enriched file to preview
      onFileSelect(enrichedFile);
      
    } catch (error) {
      console.error(`Error displaying analysis for ${file.name}:`, error);
      // Fallback to basic file selection
      onFileSelect(file);
    }
  };

  // Function to handle reprocessing of AI analysis
  const handleReprocessAI = async (file, showAlert = true) => {
    console.log(`Reprocessing AI analysis for file: ${file.name}`);
    
    // Confirm reprocessing with the user (skip if in batch mode)
    if (showAlert && !window.confirm(`This will delete the existing AI analysis for "${file.name}" and create a new one. Continue?`)) {
      return; // User cancelled
    }
    
    // Set status to reprocessing
    setReprocessingFiles(prev => ({
      ...prev,
      [file.id || file.name]: true
    }));
    
    try {
      // Make API call to reprocess with AI
      const response = await fetch(apiUrl('/api/reprocess-ai'), {
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
      if (showAlert) {
        showSnackbar(`Reprocessing of ${file.name} started successfully.`, 'info');
      }
      
    } catch (error) {
      console.error(`Error in AI reprocessing for file ${file.name}:`, error);
      // Clear reprocessing status on error
      setReprocessingFiles(prev => ({
        ...prev,
        [file.id || file.name]: false
      }));
      
      // Show error message if not in batch mode
      if (showAlert) {
        showSnackbar(`Error in AI reprocessing: ${error.message}`, 'error');
      }
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
      
      // Call the backend to delete all related files from blob storage
      const response = await fetch(apiUrl('/api/delete-analysis'), {
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
      
      // Refresh the file list to show updated files after deletion
      await fetchFiles();
      
      // Show success message (if not in batch mode)
      if (showAlerts) {
        showSnackbar(`Successfully deleted analysis for ${file.name}`, 'success');
      }
      
    } catch (error) {
      console.error(`Error deleting analysis for ${file.name}:`, error);
      if (showAlerts) {
        showSnackbar(`Failed to delete analysis: ${error.message}`, 'error');
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
      const response = await fetch(apiUrl('/api/process-and-analyze'), {
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

      // Show success message with fallback for undefined summary_file
      const summaryFileName = result.summary_file || `${file.name.split('.').slice(0, -1).join('.')}_AI.md`;
      showSnackbar(`Processing and AI Analysis for ${file.name} completed successfully! Analysis saved as: ${summaryFileName}`, 'success');

    } catch (error) {
      console.error(`Error in combined processing and AI analysis for file ${file.name}:`, error);
      setCombinedProcessingStatus(prev => ({
        ...prev,
        [file.id || file.name]: 'error'
      }));
      showSnackbar(`Error in combined processing and AI analysis for ${file.name}: ${error.message}`, 'error');
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
        const response = await fetch(apiUrl(`/api/analysis-status/${encodeURIComponent(fileName)}`));
        
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
          showSnackbar(`Analysis failed: ${statusData.message}`, 'error');
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
      const response = await fetch(apiUrl('/api/files'));
      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || `Failed to fetch files: ${response.status}`);
      }
      const data = await response.json();
      
      // Log the raw data to check what the backend is sending
      console.log('Raw data from backend:', data);
      
      // Handle new API response format: {files: [...], sequential_groups: [...]}
      const filesList = Array.isArray(data) ? data : data.files || [];
      const sequentialGroups = data.sequential_groups || [];
      
      // Log sequential processing opportunities
      if (sequentialGroups.length > 0) {
        console.log('Sequential processing opportunities:', sequentialGroups);
      }
      
      // Files should already be filtered by the backend
      const filesWithIds = filesList.map(file => ({
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
      <div className={classes.loadingCenter}>
        <Spinner />
      </div>
    );
  } else if (error) {
    content = (
      <div className={classes.alertWrapper}>
        <FluentAlert 
          intent="error" 
          className={classes.alert}
          action={
            <FluentButton 
              appearance="subtle"
              size="small" 
              onClick={fetchFiles}
            >
              Retry
            </FluentButton>
          }
        >
          {error}
        </FluentAlert>
      </div>
    );
  } else if (files.length === 0) {
    content = (
      <div className={classes.emptyState}>
        <Document24Regular className={classes.emptyIcon} />
        <div className={classes.emptyText}>
          No files uploaded yet
        </div>
      </div>
    );
  } else {
    // Group files by customer
    const filesByCustomer = groupByCustomer(files);
    const customers = Object.keys(filesByCustomer).sort();
    
    const openItems = Object.keys(expandedCustomers).filter(k => expandedCustomers[k]);
    content = (
      <div>
        <FluentAccordion multiple openItems={openItems} onToggle={(e, data) => {
          const next = {};
          const items = Array.isArray(data.openItems) ? data.openItems : [data.openItems];
          items.forEach(k => { next[k] = true; });
          setExpandedCustomers(next);
        }}>
          {Object.keys(filesByCustomer).map((customer) => (
            <AccordionItem value={customer} key={customer}>
              <AccordionHeader
                className={classes.accordionHeader}
                expandIcon={<ChevronDown24Regular className={classes.brandIcon} />}
              >
                <div className={classes.accordionHeaderContent}>
                  <Building24Regular className={classes.leadingIcon} />
                  <span className={classes.customerName}>
                    {customer}
                  </span>
                  <CounterBadge 
                    count={filesByCustomer[customer].length}
                    size="small"
                    color="brand"
                    className={classes.headerBadge}
                  />
                </div>
              </AccordionHeader>
              <AccordionPanel className={classes.accordionPanel}>
                <div>
                  {filesByCustomer[customer].map((file) => {
                    const isSelected = selectedFile && (selectedFile.id === file.id || selectedFile.name === file.name);
                    return (
                      <div
                        key={file.id || file.name}
                        className={classes.itemWrapper}
                      >
                        <div
                          onClick={() => {
                            // Use the display handler like the original Display button
                            handleDisplayAnalysis(file);
                          }}
                          className={`${classes.itemRow} ${isSelected ? classes.itemRowSelected : ''}`}
                        >
                          <div className={classes.checkboxCell}>
                            <Checkbox
                              checked={isFileSelected(file)}
                              onChange={(e) => {
                                e.stopPropagation();
                                handleFileSelection(file, e);
                              }}
                              size="small"
                            />
                          </div>
                          <div className={classes.fileIconCell}>
                            {getFileIcon(file.name, classes)}
                          </div>
                          <div className={classes.itemDetails}>
                            <div className={classes.itemTitle}>
                              {file.name}
                            </div>
                            <div className={classes.itemMeta}>
                              {file.customer_name || 'Unknown'} • {file.report_date || 'Unknown date'} • {formatFileSize(file.size)}
                            </div>
                          </div>
                          <div className={classes.itemStatus}>
                            {combinedProcessingStatus[file.id || file.name] === 'processing' && (
                              <Spinner size="tiny" />
                            )}
                            {combinedProcessingStatus[file.id || file.name] === 'completed' && (
                              <FluentTooltip content="AI analysis ready">
                                <Play24Regular className={classes.successIcon} />
                              </FluentTooltip>
                            )}
                            {combinedProcessingStatus[file.id || file.name] === 'error' && (
                              <FluentTooltip content="Error in processing">
                                <Delete24Regular className={classes.errorIcon} />
                              </FluentTooltip>
                            )}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </AccordionPanel>
            </AccordionItem>
          ))}
        </FluentAccordion>
      </div>
    );
   }

  return (
    <div className={classes.root}>
      <div className={classes.headerBar}>
        <div className={classes.title}>
          <Folder24Regular className={classes.headerFolderIcon} />
          <span>Uploaded Files</span>
          {files.length > 0 && (
            <CounterBadge 
              count={files.length}
              size="small"
              color="brand"
              className={classes.titleBadgeSpacing}
            />
          )}
        </div>
        <div className={classes.actionButtons}>
          <FluentButton
            size="small"
            onClick={() => {
              const allExpanded = {};
              const filesByCustomer = groupByCustomer(files);
              Object.keys(filesByCustomer).forEach(customer => {
                allExpanded[customer] = true;
              });
              setExpandedCustomers(allExpanded);
            }}
          >
            EXPAND ALL
          </FluentButton>
          <FluentButton
            size="small"
            onClick={() => setExpandedCustomers({})}
          >
            COLLAPSE ALL
          </FluentButton>
        </div>
      </div>
      <div className={classes.selectionSection}>
        {/* Selection info and controls */}
        <div className={classes.selectionRow}>
          <span className={classes.selectionText}>
            {selectedCount} selected ({selectedAnalyzedCount} analyzed)
          </span>
          <div className={classes.actionButtons}>
            <FluentButton
              size="small"
              onClick={() => handleSelectAllFiles()}
            >
              SELECT ALL
            </FluentButton>
            <FluentButton
              size="small"
              onClick={() => handleDeselectAllFiles()}
            >
              DESELECT ALL
            </FluentButton>
          </div>
        </div>
        
        {/* Batch action buttons */}
        {selectedCount > 0 && (
          <div className={classes.batchActions}>
            {selectedAnalyzedCount > 0 && (
              <FluentButton
                appearance="outline"
                size="small"
                icon={<Delete24Regular />}
                onClick={handleBatchDelete}
              >
                Delete ({selectedAnalyzedCount})
              </FluentButton>
            )}
            <FluentButton
              appearance="outline"
              size="small"
              icon={<Play24Regular />}
              onClick={handleBatchProcess}
            >
              Process ({selectedCount})
            </FluentButton>
          </div>
        )}
      </div>
      <div className={classes.listContainer}>
        {content}
      </div>
      
      {/* Toaster for notifications */}
      <Toaster toasterId="fileListToaster" position="bottom" />
    </div>
  );
};

export default FileList;
