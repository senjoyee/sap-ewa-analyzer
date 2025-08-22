import React, { useState, useEffect, useCallback } from 'react';
import { Button as FluentButton, Spinner, Tooltip as FluentTooltip, CounterBadge, Accordion as FluentAccordion, AccordionItem, AccordionHeader, AccordionPanel, Checkbox, tokens } from '@fluentui/react-components';
import { makeStyles } from '@griffel/react';
import { Alert as FluentAlert } from '@fluentui/react-alert';
import { Toaster, useToastController, Toast, ToastTitle } from '@fluentui/react-toast';
import { Delete24Regular, Play24Regular, Document24Regular, DocumentPdf24Regular, Image24Regular, TextDescription24Regular, ChevronDown24Regular, Building24Regular, Folder24Regular } from '@fluentui/react-icons';
 
 
// Replaced MUI Button with Fluent UI Button
 
 
import { apiUrl } from '../config';



// File type icons
 

// Action and status icons
 
// Replaced MUI Delete/Play icons with Fluent UI icons

 

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
    fontWeight: tokens.fontWeightSemibold,
    color: tokens.colorNeutralForeground1,
    fontSize: tokens.fontSizeBase200,
    display: 'flex',
    alignItems: 'center',
    gap: tokens.spacingHorizontalS,
  },
  actionButtons: {
    display: 'flex',
    gap: tokens.spacingHorizontalXS,
  },
  selectionSection: {
    display: 'flex',
    flexDirection: 'column',
    gap: tokens.spacingVerticalS,
    marginBottom: tokens.spacingVerticalS,
  },
  selectionRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  selectionText: {
    color: tokens.colorNeutralForeground3,
  },
  batchActions: {
    display: 'flex',
    gap: tokens.spacingHorizontalS,
    justifyContent: 'flex-end',
    alignItems: 'center',
  },
  listContainer: {
    flex: 1,
    overflow: 'auto',
    backgroundColor: tokens.colorNeutralBackground2,
    border: `1px solid ${tokens.colorNeutralStroke1}`,
    borderRadius: tokens.borderRadiusMedium,
    selectors: {
      '&::-webkit-scrollbar': { width: '6px' },
      '&::-webkit-scrollbar-track': { background: tokens.colorNeutralBackground2 },
      '&::-webkit-scrollbar-thumb': { background: tokens.colorNeutralStroke1, borderRadius: '3px' },
      '&::-webkit-scrollbar-thumb:hover': { background: tokens.colorNeutralStroke1Hover },
    },
  },
  loadingCenter: {
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    padding: tokens.spacingVerticalM,
    minHeight: 120,
  },
  alertWrapper: {
    padding: tokens.spacingVerticalS,
  },
  alert: {
    borderRadius: tokens.borderRadiusMedium,
  },
  emptyState: {
    padding: tokens.spacingVerticalS,
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    paddingTop: tokens.spacingVerticalL,
    paddingBottom: tokens.spacingVerticalL,
    minHeight: 120,
  },
  emptyIcon: {
    width: 40,
    height: 40,
    opacity: 0.6,
    marginBottom: tokens.spacingVerticalS,
  },
  emptyText: {
    color: tokens.colorNeutralForeground3,
    fontSize: tokens.fontSizeBase100,
    textAlign: 'center',
  },
  headerFolderIcon: {
    width: 18,
    height: 18,
    color: tokens.colorBrandForeground1,
  },
  titleBadgeSpacing: {
    marginLeft: tokens.spacingHorizontalXS,
  },
  accordionHeader: {
    minHeight: 44,
    backgroundColor: tokens.colorNeutralBackground2,
    borderBottom: `1px solid ${tokens.colorNeutralStroke1}`,
  },
  accordionHeaderContent: {
    display: 'flex',
    alignItems: 'center',
    width: '100%',
  },
  brandIcon: {
    color: tokens.colorBrandForeground1,
  },
  leadingIcon: {
    marginRight: tokens.spacingHorizontalM,
    width: 18,
    height: 18,
    color: tokens.colorBrandForeground1,
  },
  customerName: {
    fontWeight: tokens.fontWeightMedium,
    fontSize: tokens.fontSizeBase200,
    color: tokens.colorNeutralForeground1,
  },
  headerBadge: {
    marginLeft: 'auto',
    marginRight: tokens.spacingHorizontalS,
  },
  accordionPanel: {
    padding: tokens.spacingHorizontalXS,
    backgroundColor: tokens.colorNeutralBackground1,
  },
  itemWrapper: {
    position: 'relative',
    marginBottom: tokens.spacingVerticalXS,
  },
  itemRow: {
    display: 'flex',
    alignItems: 'center',
    paddingRight: tokens.spacingHorizontalM,
    marginInline: tokens.spacingHorizontalXS,
    borderRadius: 8,
    minHeight: 48,
    transition: 'all 0.2s ease',
    cursor: 'pointer',
    selectors: {
      '&:hover': { backgroundColor: tokens.colorSubtleBackgroundHover },
      '&:focus-visible': { outline: `${tokens.strokeWidthThick} solid ${tokens.colorStrokeFocus2}`, outlineOffset: 2 },
    },
  },
  itemRowSelected: {
    backgroundColor: tokens.colorSubtleBackgroundSelected,
  },
  checkboxCell: {
    minWidth: 36,
    display: 'flex',
    alignItems: 'center',
  },
  fileIconCell: {
    minWidth: 28,
    color: tokens.colorNeutralForeground3,
  },
  itemDetails: {
    flex: 1,
    minWidth: 0,
  },
  itemTitle: {
    fontSize: tokens.fontSizeBase200,
    color: tokens.colorNeutralForeground1,
    whiteSpace: 'nowrap',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
  },
  itemMeta: {
    color: tokens.colorNeutralForeground3,
    fontSize: tokens.fontSizeBase100,
  },
  itemStatus: {
    marginLeft: 'auto',
    display: 'flex',
    alignItems: 'center',
    gap: 4,
  },
  successIcon: {
    color: tokens.colorPaletteGreenForeground3,
  },
  errorIcon: {
    color: tokens.colorPaletteRedForeground3,
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
  
  const [expandedCustomers, setExpandedCustomers] = useState({});
  const [combinedProcessingStatus, setCombinedProcessingStatus] = useState({}); // Track combined processing & AI analysis status
  const [selectedFiles, setSelectedFiles] = useState([]);
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

  // PDF export functionality moved to FilePreview component

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
      
      // Individual status trackers removed; using combinedProcessingStatus for UI

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
  const fetchFiles = useCallback(async () => {
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
      const grouped = {};
      filesWithIds.forEach(f => {
        const customer = f.customer_name || 'Unknown';
        if (!grouped[customer]) grouped[customer] = [];
        grouped[customer].push(f);
      });
      setExpandedCustomers(prev => {
        const next = { ...prev };
        const totalCustomers = Object.keys(grouped).length;
        Object.keys(grouped).forEach(customer => {
          if (grouped[customer].length === 1 || totalCustomers <= 3) {
            next[customer] = true;
          }
        });
        return next;
      });
    } catch (err) {
      console.error("Error fetching files:", err);
      setError(err.message);
      setFiles([]); 
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchFiles();
  }, [fetchFiles, refreshTrigger]);

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
                aria-label={`${customer} files`}
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
                          role="button"
                          tabIndex={0}
                          aria-label={`Open analysis for ${file.name}`}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter' || e.key === ' ') {
                              e.preventDefault();
                              handleDisplayAnalysis(file);
                            }
                          }}
                        >
                          <div className={classes.checkboxCell}>
                            <Checkbox
                              checked={isFileSelected(file)}
                              onChange={(e) => {
                                e.stopPropagation();
                                handleFileSelection(file, e);
                              }}
                              size="small"
                              aria-label={`Select ${file.name}`}
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
