import React, { useState, useEffect, useCallback } from 'react';
import { Button as FluentButton, Spinner, ProgressBar, Tooltip as FluentTooltip, CounterBadge, Accordion as FluentAccordion, AccordionItem, AccordionHeader, AccordionPanel, Checkbox, tokens } from '@fluentui/react-components';
import { makeStyles, mergeClasses } from '@griffel/react';
import { Alert as FluentAlert } from '@fluentui/react-alert';
import { Toaster, useToastController, Toast, ToastTitle } from '@fluentui/react-toast';
import { Delete24Regular, Play24Regular, Document24Regular, ChevronDown20Regular, Building24Regular, Folder24Regular, Document16Regular, DocumentPdf16Regular, Image16Regular, TextDescription16Regular, Info16Regular, Warning16Regular, ErrorCircle16Regular, CheckmarkCircle16Regular } from '@fluentui/react-icons';
 
 
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
    gap: tokens.spacingHorizontalL,
    minWidth: 0,
    minHeight: 0, // allow flex children to shrink and become scrollable
    padding: tokens.spacingVerticalM,
    background: `linear-gradient(180deg, ${tokens.colorNeutralBackground1} 0%, ${tokens.colorNeutralBackground1Hover} 100%)`,
  },
  skipLink: {
    position: 'absolute',
    left: tokens.spacingHorizontalS,
    top: tokens.spacingVerticalS,
    backgroundColor: tokens.colorNeutralBackground1,
    color: tokens.colorNeutralForeground1,
    padding: tokens.spacingHorizontalS,
    borderRadius: tokens.borderRadiusSmall,
    boxShadow: tokens.shadow4,
    zIndex: 2000,
    clip: 'rect(1px, 1px, 1px, 1px)',
    height: 1,
    width: 1,
    overflow: 'hidden',
    selectors: {
      ':focus': { clip: 'auto', height: 'auto', width: 'auto', overflow: 'visible' },
    },
  },
  // Icon sizes
  icon16: {
    width: 16,
    height: 16,
  },
  icon20: {
    width: 20,
    height: 20,
  },
  icon24: {
    width: 24,
    height: 24,
  },
  // Icon color semantics
  iconBrand: {
    color: tokens.colorBrandForeground1,
  },
  iconInfo: {
    color: tokens.colorPaletteBlueForeground1,
  },
  iconError: {
    color: tokens.colorPaletteRedForeground1,
  },
  iconNeutral: {
    color: tokens.colorNeutralForeground3,
  },
  iconDisabled: {
    color: tokens.colorNeutralForegroundDisabled,
  },
  headerBar: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: tokens.spacingVerticalM,
    flexWrap: 'wrap',
    gap: tokens.spacingHorizontalS,
    padding: tokens.spacingVerticalM,
    backgroundColor: tokens.colorNeutralBackground1,
    borderRadius: tokens.borderRadiusLarge,
    boxShadow: tokens.shadow8,
    border: `1px solid ${tokens.colorNeutralStroke1}`,
    background: `linear-gradient(135deg, ${tokens.colorNeutralBackground1} 0%, ${tokens.colorSubtleBackground} 100%)`,
    '@media (max-width: 600px)': {
      flexDirection: 'column',
      alignItems: 'stretch',
      rowGap: tokens.spacingVerticalS,
      padding: tokens.spacingVerticalS,
    },
  },
  title: {
    fontWeight: tokens.fontWeightBold,
    color: tokens.colorNeutralForeground1,
    fontSize: tokens.fontSizeBase300,
    display: 'flex',
    alignItems: 'center',
    gap: tokens.spacingHorizontalS,
    minWidth: 0,
    overflowWrap: 'anywhere',
    letterSpacing: '-0.02em',
  },
  actionButtons: {
    display: 'flex',
    gap: tokens.spacingHorizontalS,
    flexWrap: 'wrap',
    alignItems: 'center',
  },
  selectionSection: {
    display: 'flex',
    flexDirection: 'column',
    gap: tokens.spacingVerticalS,
    marginBottom: tokens.spacingVerticalM,
    padding: tokens.spacingVerticalM,
    backgroundColor: tokens.colorNeutralBackground1,
    borderRadius: tokens.borderRadiusMedium,
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    boxShadow: tokens.shadow4,
  },
  selectionRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    flexWrap: 'wrap',
    rowGap: tokens.spacingVerticalXS,
  },
  selectionText: {
    color: tokens.colorNeutralForeground2,
    fontSize: tokens.fontSizeBase200,
    fontWeight: tokens.fontWeightMedium,
  },
  batchActions: {
    display: 'flex',
    gap: tokens.spacingHorizontalS,
    justifyContent: 'flex-end',
    alignItems: 'center',
    padding: tokens.spacingVerticalS,
    backgroundColor: tokens.colorSubtleBackground,
    borderRadius: tokens.borderRadiusMedium,
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    marginTop: tokens.spacingVerticalS,
  },
  listContainer: {
    // Let the sidebar (parent) own scrolling to avoid nested scrollbars
    flex: 'initial',
    overflowY: 'visible',
    overflowX: 'visible',
    backgroundColor: tokens.colorNeutralBackground1,
    border: `1px solid ${tokens.colorNeutralStroke1}`,
    borderRadius: tokens.borderRadiusLarge,
    boxShadow: tokens.shadow16,
    minHeight: 'auto',
    height: 'auto',
    background: `linear-gradient(180deg, ${tokens.colorNeutralBackground1} 0%, ${tokens.colorNeutralBackground2} 100%)`,
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
    padding: tokens.spacingVerticalL,
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    paddingTop: tokens.spacingVerticalXXL,
    paddingBottom: tokens.spacingVerticalXXL,
    minHeight: 200,
    background: `linear-gradient(135deg, ${tokens.colorNeutralBackground1} 0%, ${tokens.colorSubtleBackground} 100%)`,
    borderRadius: tokens.borderRadiusLarge,
    border: `2px dashed ${tokens.colorNeutralStroke2}`,
  },
  emptyIcon: {
    width: 48,
    height: 48,
    opacity: 0.7,
    marginBottom: tokens.spacingVerticalM,
    color: tokens.colorNeutralForeground3,
    filter: 'drop-shadow(0 2px 4px rgba(0,0,0,0.1))',
  },
  emptyText: {
    color: tokens.colorNeutralForeground2,
    fontSize: tokens.fontSizeBase300,
    textAlign: 'center',
    fontWeight: tokens.fontWeightMedium,
    lineHeight: tokens.lineHeightBase300,
  },
  headerFolderIcon: {
    width: 22,
    height: 22,
    color: tokens.colorBrandForeground1,
    filter: 'drop-shadow(0 1px 2px rgba(0,0,0,0.1))',
  },
  titleBadgeSpacing: {
    marginLeft: tokens.spacingHorizontalXS,
  },
  accordionHeader: {
    minHeight: 52,
    backgroundColor: tokens.colorNeutralBackground1,
    borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
    borderRadius: `${tokens.borderRadiusMedium} ${tokens.borderRadiusMedium} 0 0`,
    transition: 'all 200ms cubic-bezier(0.4, 0, 0.2, 1)',
    background: `linear-gradient(135deg, ${tokens.colorNeutralBackground1} 0%, ${tokens.colorSubtleBackground} 100%)`,
    boxShadow: `0 1px 3px ${tokens.colorNeutralShadowAmbient}`,
    selectors: {
      '&:hover': { 
        backgroundColor: tokens.colorSubtleBackgroundHover,
        transform: 'translateY(-1px)',
        boxShadow: `0 4px 12px ${tokens.colorNeutralShadowAmbient}`,
      },
      '&:focus-visible': { 
        outline: `${tokens.strokeWidthThick} solid ${tokens.colorBrandStroke1}`, 
        outlineOffset: 2,
        boxShadow: `0 0 0 2px ${tokens.colorBrandBackground}`,
      },
    },
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
    width: 22,
    height: 22,
    color: tokens.colorBrandForeground1,
    filter: 'drop-shadow(0 1px 2px rgba(0,0,0,0.1))',
  },
  customerName: {
    fontWeight: tokens.fontWeightSemibold,
    fontSize: tokens.fontSizeBase300,
    color: tokens.colorNeutralForeground1,
    letterSpacing: '-0.01em',
  },
  headerBadge: {
    marginLeft: 'auto',
    marginRight: tokens.spacingHorizontalS,
  },
  accordionPanel: {
    padding: tokens.spacingHorizontalM,
    backgroundColor: tokens.colorNeutralBackground1,
    borderTop: `1px solid ${tokens.colorNeutralStroke2}`,
    borderRadius: `0 0 ${tokens.borderRadiusMedium} ${tokens.borderRadiusMedium}`,
    boxShadow: `inset 0 1px 3px ${tokens.colorNeutralShadowAmbient}`,
  },
  itemWrapper: {
    position: 'relative',
    marginBottom: tokens.spacingVerticalS,
    borderRadius: tokens.borderRadiusMedium,
    overflow: 'hidden',
    backgroundColor: 'transparent',
    transition: 'all 150ms ease',
    selectors: {
      '&:hover': {
        backgroundColor: tokens.colorSubtleBackgroundHover,
        transform: 'translateX(2px)',
        boxShadow: `0 2px 8px ${tokens.colorNeutralShadowAmbient}`,
      },
      '&:hover [data-checkbox]': { opacity: 1, pointerEvents: 'auto' },
      '&:focus-within [data-checkbox]': { opacity: 1, pointerEvents: 'auto' },
      '&:focus-within': {
        backgroundColor: tokens.colorSubtleBackgroundHover,
        boxShadow: `0 0 0 2px ${tokens.colorBrandStroke1}`,
      },
    },
  },
  itemRow: {
    display: 'flex',
    alignItems: 'center',
    paddingLeft: tokens.spacingHorizontalM,
    paddingRight: tokens.spacingHorizontalM,
    paddingTop: tokens.spacingVerticalS,
    paddingBottom: tokens.spacingVerticalS,
    marginInline: tokens.spacingHorizontalXS,
    borderRadius: tokens.borderRadiusMedium,
    minHeight: 48,
    transition: 'all 200ms cubic-bezier(0.4, 0, 0.2, 1)',
    cursor: 'pointer',
    position: 'relative',
    border: `1px solid transparent`,
    selectors: {
      '&:hover': { 
        backgroundColor: 'transparent',
        borderColor: tokens.colorNeutralStroke2,
      },
      '&:focus-visible': { 
        outline: `${tokens.strokeWidthThick} solid ${tokens.colorBrandStroke1}`, 
        outlineOffset: 2,
        backgroundColor: tokens.colorSubtleBackgroundPressed,
      },
      '&:hover [data-checkbox]': { opacity: 1, pointerEvents: 'auto' },
      '&:focus-within [data-checkbox]': { opacity: 1, pointerEvents: 'auto' },
      '&[data-checked="true"] [data-checkbox]': { opacity: 1, pointerEvents: 'auto' },
      '&[data-checked="true"]': {
        backgroundColor: tokens.colorBrandBackgroundStatic,
        borderColor: tokens.colorBrandStroke1,
        color: tokens.colorNeutralForegroundOnBrand,
      },
    },
  },
  itemRowSelected: {
    backgroundColor: tokens.colorBrandBackgroundStatic,
    borderColor: tokens.colorBrandStroke1,
    boxShadow: `0 0 0 1px ${tokens.colorBrandStroke1}`,
    selectors: {
      '& *': {
        color: `${tokens.colorNeutralForegroundOnBrand} !important`,
      },
    },
  },
  itemDivider: {
    height: 1,
    backgroundColor: tokens.colorNeutralStroke2,
    marginLeft: tokens.spacingHorizontalXS,
    marginRight: tokens.spacingHorizontalXS,
  },
  checkboxCell: {
    minWidth: 32,
    width: 32,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    opacity: 0,
    pointerEvents: 'none',
    transition: 'opacity 120ms ease',
    zIndex: 1,
    selectors: {
      // Make the Fluent Checkbox visual indicator round
      '& :global(.fui-Checkbox__indicator)': {
        borderRadius: '9999px',
        border: `1.5px solid ${tokens.colorNeutralStrokeAccessible}`,
        backgroundColor: 'transparent',
        width: '18px',
        height: '18px',
      },
      '& :global(.fui-Checkbox__input)': { margin: 0 },
    },
    '@media (hover: none)': {
      // On touch devices, always show the checkbox since hover isn't available
      opacity: 1,
      pointerEvents: 'auto',
    },
  },
  checkboxVisible: {
    opacity: 1,
    pointerEvents: 'auto',
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
    fontSize: tokens.fontSizeBase300,
    fontWeight: tokens.fontWeightMedium,
    color: tokens.colorNeutralForeground1,
    whiteSpace: 'nowrap',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    letterSpacing: '-0.01em',
  },
  itemStatus: {
    marginLeft: 'auto',
    display: 'flex',
    alignItems: 'center',
    gap: tokens.spacingHorizontalXS,
  },
  successIcon: {
    color: tokens.colorPaletteGreenForeground2,
    filter: 'drop-shadow(0 1px 1px rgba(0,0,0,0.1))',
  },
  errorIcon: {
    color: tokens.colorPaletteRedForeground2,
    filter: 'drop-shadow(0 1px 1px rgba(0,0,0,0.1))',
  },
  fileTypeIcon: {
    width: 18,
    height: 18,
    filter: 'drop-shadow(0 1px 1px rgba(0,0,0,0.1))',
  },
  // Loading skeletons
  skeletonContainer: {
    marginTop: tokens.spacingVerticalM,
    display: 'flex',
    flexDirection: 'column',
    gap: tokens.spacingVerticalXS,
    width: '100%',
    paddingLeft: tokens.spacingHorizontalS,
    paddingRight: tokens.spacingHorizontalS,
  },
  skeletonRow: {
    display: 'flex',
    alignItems: 'center',
    gap: tokens.spacingHorizontalS,
    padding: tokens.spacingHorizontalS,
    marginInline: tokens.spacingHorizontalXS,
    minHeight: 44,
    borderRadius: tokens.borderRadiusMedium,
    backgroundColor: tokens.colorNeutralBackground3,
  },
  skeletonCheckbox: {
    width: 16,
    height: 16,
    borderRadius: tokens.borderRadiusSmall,
    backgroundColor: tokens.colorNeutralBackground4,
  },
  skeletonIcon: {
    width: 16,
    height: 16,
    borderRadius: tokens.borderRadiusSmall,
    backgroundColor: tokens.colorNeutralBackground4,
  },
  skeletonTextBlock: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    gap: tokens.spacingVerticalXXS,
  },
  skeletonLine: {
    height: 8,
    borderRadius: 4,
    backgroundColor: tokens.colorNeutralBackground4,
  },
  skeletonLineLong: {
    width: '60%',
  },
  skeletonLineShort: {
    width: '35%',
  },
  // Unified empty placeholder pattern
  placeholderTitle: {
    fontWeight: tokens.fontWeightBold,
    color: tokens.colorNeutralForeground1,
    fontSize: tokens.fontSizeBase600,
    marginBottom: tokens.spacingVerticalS,
    letterSpacing: '-0.02em',
  },
  placeholderSubtext: {
    color: tokens.colorNeutralForeground2,
    fontSize: tokens.fontSizeBase400,
    marginBottom: tokens.spacingVerticalL,
    textAlign: 'center',
    lineHeight: tokens.lineHeightBase400,
  },
  placeholderFrame: {
    border: `1px dashed ${tokens.colorNeutralStroke1}`,
    borderRadius: tokens.borderRadiusMedium,
    padding: tokens.spacingHorizontalL,
    minHeight: '120px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    width: '100%',
    maxWidth: 520,
  },
  placeholderMuted: {
    color: tokens.colorNeutralForeground3,
    fontSize: tokens.fontSizeBase200,
  },
});

// Helper function to get appropriate icon for file type
const getFileIcon = (filename, classes) => {
  // Extract extension from filename
  const fileExtension = filename && typeof filename === 'string' 
    ? filename.split('.').pop().toLowerCase() 
    : '';
  
  switch(fileExtension) {
    case 'pdf':
      return <DocumentPdf16Regular className={`${classes.fileTypeIcon} ${classes.iconError}`} />;
    case 'jpg':
    case 'jpeg':
    case 'png':
    case 'gif':
    case 'bmp':
      return <Image16Regular className={`${classes.fileTypeIcon} ${classes.iconInfo}`} />;
    case 'doc':
    case 'docx':
      return <Document16Regular className={`${classes.fileTypeIcon} ${classes.iconBrand}`} />;
    case 'txt':
      return <TextDescription16Regular className={`${classes.fileTypeIcon} ${classes.iconNeutral}`} />;
    default:
      return <Document16Regular className={`${classes.fileTypeIcon} ${classes.iconDisabled}`} />;
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
  const [hoveredId, setHoveredId] = useState(null);
  const classes = useStyles();
  
  // Toast controller (Fluent UI Toast)
  const { dispatchToast } = useToastController('fileListToaster');
  
  // Keep the same API but dispatch a Fluent Toast instead
  const showSnackbar = (message, severity = 'info') => {
    const intent = severity; // 'success' | 'error' | 'warning' | 'info'
    const timeout = (severity === 'warning' || severity === 'error') ? 6000 : 4000;
    const mediaIcon =
      severity === 'success' ? <CheckmarkCircle16Regular /> :
      severity === 'error' ? <ErrorCircle16Regular /> :
      severity === 'warning' ? <Warning16Regular /> :
      <Info16Regular />;

    dispatchToast(
      <Toast intent={intent}>
        <ToastTitle media={mediaIcon}>{message}</ToastTitle>
      </Toast>,
      { timeout }
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
        <ProgressBar aria-label="Loading files" />
        <div className={classes.skeletonContainer} aria-hidden="true">
          <div className={classes.skeletonRow}>
            <div className={classes.skeletonCheckbox} />
            <div className={classes.skeletonIcon} />
            <div className={classes.skeletonTextBlock}>
              <div className={`${classes.skeletonLine} ${classes.skeletonLineLong}`} />
              <div className={`${classes.skeletonLine} ${classes.skeletonLineShort}`} />
            </div>
          </div>
          <div className={classes.skeletonRow}>
            <div className={classes.skeletonCheckbox} />
            <div className={classes.skeletonIcon} />
            <div className={classes.skeletonTextBlock}>
              <div className={`${classes.skeletonLine} ${classes.skeletonLineLong}`} />
              <div className={`${classes.skeletonLine} ${classes.skeletonLineShort}`} />
            </div>
          </div>
          <div className={classes.skeletonRow}>
            <div className={classes.skeletonCheckbox} />
            <div className={classes.skeletonIcon} />
            <div className={classes.skeletonTextBlock}>
              <div className={`${classes.skeletonLine} ${classes.skeletonLineLong}`} />
              <div className={`${classes.skeletonLine} ${classes.skeletonLineShort}`} />
            </div>
          </div>
        </div>
      </div>
    );
  } else if (error) {
    content = (
      <div className={classes.alertWrapper}>
        <FluentAlert 
          intent="error" 
          className={classes.alert}
          aria-live="assertive"
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
        <div className={classes.placeholderTitle}>No files uploaded</div>
        <div className={classes.placeholderSubtext}>Upload files to see them listed here.</div>
        <div className={classes.placeholderFrame}>
          <div className={classes.placeholderMuted}>Your uploaded files will appear here.</div>
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
                expandIcon={<ChevronDown20Regular className={classes.brandIcon} />}
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
                  {filesByCustomer[customer].map((file, idx) => {
                    const isSelected = selectedFile && (selectedFile.id === file.id || selectedFile.name === file.name);
                    const isLast = idx === filesByCustomer[customer].length - 1;
                    return (
                      <div
                        key={file.id || file.name}
                        className={classes.itemWrapper}
                        onMouseEnter={() => setHoveredId(file.id || file.name)}
                        onMouseLeave={() => setHoveredId(null)}
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
                          onMouseEnter={() => setHoveredId(file.id || file.name)}
                          onMouseLeave={() => setHoveredId(null)}
                          onFocus={() => setHoveredId(file.id || file.name)}
                          onBlur={() => setHoveredId(null)}
                          data-checked={isFileSelected(file) ? 'true' : 'false'}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter' || e.key === ' ') {
                              e.preventDefault();
                              handleDisplayAnalysis(file);
                            }
                          }}
                        >
                          <div
                            className={classes.checkboxCell}
                            style={{
                              opacity: (isFileSelected(file) || hoveredId === (file.id || file.name)) ? 1 : 0,
                              pointerEvents: (isFileSelected(file) || hoveredId === (file.id || file.name)) ? 'auto' : 'none',
                            }}
                            data-checkbox
                          >
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
                        {!isLast && <div className={classes.itemDivider} role="separator" aria-hidden="true" />}
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
      <a href="#filelist-main" className={classes.skipLink}>Skip to file list</a>
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
      <div className={classes.listContainer} id="filelist-main" role="main" tabIndex={-1}>
        {content}
      </div>
      
      {/* Toaster for notifications */}
      <Toaster toasterId="fileListToaster" position="bottom-end" />
    </div>
  );
};

export default FileList;
