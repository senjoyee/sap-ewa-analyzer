import React, { useState, useRef } from 'react';
import { Button as FluentButton, Combobox, Option, Field, Tag, ProgressBar } from '@fluentui/react-components';
import { Alert as FluentAlert } from '@fluentui/react-alert';
// Replaced MUI LinearProgress with Fluent ProgressBar
// Removed MUI Chip in favor of Fluent Tag
import { 
  Add24Regular, 
  Dismiss24Regular, 
  CloudArrowUp24Regular,
  CheckmarkCircle16Regular,
  ErrorCircle16Regular,
  Building16Regular,
  DocumentPdf16Regular,
  Image16Regular,
  DocumentText16Regular,
  Document16Regular,
} from '@fluentui/react-icons';
import { apiUrl } from '../config';
import { makeStyles, shorthands, tokens } from '@fluentui/react-components';

// Helper function to get appropriate icon for file type
const getFileIcon = (filename, classes) => {
  // Extract extension from filename
  const fileExtension = filename && typeof filename === 'string' 
    ? filename.split('.').pop().toLowerCase() 
    : '';
  
  switch(fileExtension) {
    case 'pdf':
      return <DocumentPdf16Regular className={`${classes.icon16} ${classes.iconError}`} />;
    case 'jpg':
    case 'jpeg':
    case 'png':
    case 'gif':
    case 'bmp':
      return <Image16Regular className={`${classes.icon16} ${classes.iconInfo}`} />;
    case 'doc':
    case 'docx':
      return <DocumentText16Regular className={`${classes.icon16} ${classes.iconBrand}`} />;
    case 'txt':
      return <DocumentText16Regular className={`${classes.icon16} ${classes.iconNeutral}`} />;
    default:
      return <Document16Regular className={`${classes.icon16} ${classes.iconDisabled}`} />;
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

const useStyles = makeStyles({
  card: {
    ...shorthands.padding(tokens.spacingHorizontalXXL),
    ...shorthands.borderRadius(tokens.borderRadiusXLarge),
    backgroundColor: tokens.colorNeutralBackground1,
    ...shorthands.border('1px', 'solid', tokens.colorNeutralStroke1),
    boxShadow: tokens.shadow16,
    background: `linear-gradient(135deg, ${tokens.colorNeutralBackground1} 0%, ${tokens.colorSubtleBackground} 100%)`,
    transition: 'all 200ms cubic-bezier(0.4, 0, 0.2, 1)',
    selectors: {
      '&:hover': {
        transform: 'translateY(-2px)',
        boxShadow: tokens.shadow28,
      },
    },
  },
  // Icon sizes
  icon16: {
    width: 18,
    height: 18,
    filter: 'drop-shadow(0 1px 1px rgba(0,0,0,0.1))',
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
  iconSuccess: {
    color: tokens.colorPaletteGreenForeground1,
  },
  iconNeutral: {
    color: tokens.colorNeutralForeground3,
  },
  iconDisabled: {
    color: tokens.colorNeutralForegroundDisabled,
  },
  statusIcon: {
    marginRight: tokens.spacingHorizontalXS,
  },
  heroIcon: {
    width: 56,
    height: 56,
    color: tokens.colorBrandForeground1,
    marginBottom: tokens.spacingVerticalL,
    opacity: 1,
    filter: 'drop-shadow(0 4px 8px rgba(0,0,0,0.15))',
    transition: 'transform 200ms ease',
    selectors: {
      '&:hover': {
        transform: 'scale(1.05)',
      },
    },
  },
  center: {
    textAlign: 'center',
  },
  sectionCard: {
    ...shorthands.padding(tokens.spacingHorizontalXL),
    marginTop: tokens.spacingVerticalL,
    marginBottom: tokens.spacingVerticalM,
    backgroundColor: tokens.colorNeutralBackground1,
    ...shorthands.borderRadius(tokens.borderRadiusLarge),
    ...shorthands.border('1px', 'solid', tokens.colorNeutralStroke1),
    boxShadow: tokens.shadow16,
    background: `linear-gradient(135deg, ${tokens.colorNeutralBackground1} 0%, ${tokens.colorSubtleBackground} 100%)`,
    transition: 'all 200ms cubic-bezier(0.4, 0, 0.2, 1)',
    selectors: {
      '&:hover': { 
        backgroundColor: tokens.colorSubtleBackgroundHover,
        transform: 'translateY(-1px)',
        boxShadow: tokens.shadow28,
      },
      '&:focus-within': { 
        outline: `${tokens.strokeWidthThick} solid ${tokens.colorBrandStroke1}`, 
        outlineOffset: 2,
        boxShadow: `0 0 0 2px ${tokens.colorBrandBackground}`,
      },
    },
  },
  grid: {
    display: 'grid',
    gap: tokens.spacingHorizontalXL,
  },
  fileCard: {
    ...shorthands.padding(tokens.spacingHorizontalL),
    backgroundColor: tokens.colorNeutralBackground1,
    ...shorthands.borderRadius(tokens.borderRadiusMedium),
    ...shorthands.border('1px', 'solid', tokens.colorNeutralStroke2),
    boxShadow: tokens.shadow8,
    transition: 'all 200ms cubic-bezier(0.4, 0, 0.2, 1)',
    selectors: {
      '&:hover': { 
        backgroundColor: tokens.colorSubtleBackgroundHover,
        transform: 'translateY(-1px)',
        boxShadow: tokens.shadow16,
        borderColor: tokens.colorNeutralStroke1,
      },
      '&:focus-within': { 
        outline: `${tokens.strokeWidthThick} solid ${tokens.colorBrandStroke1}`, 
        outlineOffset: 2,
        backgroundColor: tokens.colorSubtleBackgroundPressed,
      },
    },
  },
  heroTitle: {
    marginBottom: tokens.spacingVerticalS,
    fontWeight: tokens.fontWeightBold,
    color: tokens.colorNeutralForeground1,
    fontSize: tokens.fontSizeBase600,
    letterSpacing: '-0.02em',
    textShadow: '0 1px 2px rgba(0,0,0,0.1)',
  },
  heroSubtext: {
    color: tokens.colorNeutralForeground2,
    marginBottom: tokens.spacingVerticalXL,
    fontSize: tokens.fontSizeBase400,
    fontWeight: tokens.fontWeightMedium,
    lineHeight: tokens.lineHeightBase400,
  },
  sectionHeader: {
    fontWeight: tokens.fontWeightBold,
    fontSize: tokens.fontSizeBase500,
    color: tokens.colorBrandForeground1,
    letterSpacing: '-0.01em',
  },
  sectionDescription: {
    color: tokens.colorNeutralForeground2,
    marginBottom: tokens.spacingVerticalXL,
    fontSize: tokens.fontSizeBase400,
    lineHeight: tokens.lineHeightBase400,
    fontWeight: tokens.fontWeightMedium,
  },
  fileTitle: {
    fontWeight: tokens.fontWeightBold,
    color: tokens.colorNeutralForeground1,
    whiteSpace: 'nowrap',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    fontSize: tokens.fontSizeBase300,
    letterSpacing: '-0.01em',
  },
  fileMeta: {
    color: tokens.colorNeutralForeground2,
    fontSize: tokens.fontSizeBase300,
    fontWeight: tokens.fontWeightMedium,
  },
  errorText: {
    display: 'block',
    marginTop: tokens.spacingVerticalXS,
    color: tokens.colorPaletteRedForeground1,
    fontSize: tokens.fontSizeBase200,
  },
  controlFullWidth: {
    width: '100%',
  },
});

const FileUpload = ({ onUploadSuccess }) => {
  const [uploadingFilesInfo, setUploadingFilesInfo] = useState([]); // To track multiple uploads
  const [overallStatus, setOverallStatus] = useState({ message: '', error: '' });
  const [filesWithCustomers, setFilesWithCustomers] = useState([]); // Array of {file, customerName, error} objects
  const [showCustomerFields, setShowCustomerFields] = useState(false); // Control visibility of customer fields
  const [customers] = useState([
    'TBS',
    'Eviosys',
    'BSW',
    'Asahi',
    'Corex',
    'Shoosmiths'
  ]); // Predefined customer list
  const fileInputRef = useRef(null);
  const classes = useStyles();
  const instructionsId = 'upload-instructions';
  
  // Function to dismiss overall status message
  const dismissOverallStatus = () => {
    setOverallStatus({ message: '', error: '' });
  };
  
  // Function to dismiss a specific file status
  const dismissFileStatus = (indexToDismiss) => {
    setUploadingFilesInfo(prevFiles => 
      prevFiles.filter((_, index) => index !== indexToDismiss)
    );
  };

  // Handle customer name input change for a specific file
  const handleCustomerNameChange = (index, value) => {
    setFilesWithCustomers(prev => {
      const updated = [...prev];
      updated[index] = {
        ...updated[index],
        customerName: value,
        error: value.trim() ? '' : updated[index].error
      };
      return updated;
    });
  };

  // Validate all customer names before proceeding with upload
  const validateCustomerNames = () => {
    let isValid = true;
    
    setFilesWithCustomers(prev => {
      const updated = [...prev];
      updated.forEach((item, index) => {
        if (!item.customerName.trim()) {
          updated[index] = {
            ...item,
            error: 'Customer name is required'
          };
          isValid = false;
        }
      });
      return updated;
    });
    
    return isValid;
  };

  // Handle the initial file selection
  const handleAddClick = () => {
    fileInputRef.current.click();
  };
  
  // Handle proceeding with upload after customer names are entered
  const handleProceedWithUpload = () => {
    if (validateCustomerNames()) {
      processFileUpload();
    }
  };
  
  // Handle canceling the upload and resetting the form
  const handleCancelUpload = () => {
    setFilesWithCustomers([]);
    setShowCustomerFields(false);
  };

  // Handle when files are selected from the file dialog
  const handleFilesSelected = (event) => {
    const files = event.target.files;
    if (files.length === 0) {
      return;
    }
    
    // Create a file+customer object for each selected file
    const filesWithCustomerData = Array.from(files).map(file => ({
      file,
      customerName: '',
      error: ''
    }));
    
    // Store the selected files with empty customer names and show the customer name fields
    setFilesWithCustomers(filesWithCustomerData);
    setShowCustomerFields(true);
  };
  
  // Process the actual file upload after customer names are provided
  const processFileUpload = async () => {
    const filesToUpload = filesWithCustomers;
    if (!filesToUpload || filesToUpload.length === 0) {
      return;
    }

    setOverallStatus({ message: `Starting upload of ${filesToUpload.length} file(s)...`, error: '' });
    
    // Reset individual file tracking for this batch
    const initialFilesInfo = filesToUpload.map(fileData => ({
      name: fileData.file.name,
      progress: 0,
      status: 'pending', // 'pending', 'uploading', 'success', 'error'
      error: null,
      customer: fileData.customerName, // Add individual customer name to file info
    }));
    setUploadingFilesInfo(initialFilesInfo);

    for (let i = 0; i < filesToUpload.length; i++) {
      const fileData = filesToUpload[i];
      const file = fileData.file;
      const customerName = fileData.customerName;
      
      setUploadingFilesInfo(prev => prev.map((f, index) => 
        index === i ? { ...f, status: 'uploading', progress: 0 } : f
      ));

      try {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('customer_name', customerName); // Add individual customer name to form data

        // Simple progress simulation (actual XHR progress is more complex with fetch)
        // For real progress, XMLHttpRequest or a library like Axios is better.
        // Here, we'll just update before/after.
        setUploadingFilesInfo(prev => prev.map((f, index) => 
          index === i ? { ...f, progress: 50 } : f // Simulate mid-upload
        ));

        const response = await fetch(apiUrl('/api/upload'), {
          method: 'POST',
          body: formData,
        });
        
        // Successfully uploaded this file

        setUploadingFilesInfo(prev => prev.map((f, index) => 
          index === i ? { ...f, progress: 100 } : f
        ));

        if (response.ok) {
          await response.json();
          setUploadingFilesInfo(prev => prev.map((f, index) => 
            index === i ? { ...f, status: 'success' } : f
          ));
          if (onUploadSuccess) {
            onUploadSuccess(); // Refresh file list after each successful upload
          }
        } else {
          const errorResult = await response.json().catch(() => ({ detail: 'Upload failed with no specific error message.' }));
          setUploadingFilesInfo(prev => prev.map((f, index) => 
            index === i ? { ...f, status: 'error', error: errorResult.detail || `HTTP error ${response.status}` } : f
          ));
        }
      } catch (err) {
        setUploadingFilesInfo(prev => prev.map((f, index) => 
          index === i ? { ...f, status: 'error', error: err.message } : f
        ));
      }
    }
    // After all files are processed
    // Re-read state directly here to ensure we have the latest updates before setting overallStatus
    setUploadingFilesInfo(currentUploadingFilesInfo => {
      const finalStatusMsg = currentUploadingFilesInfo.every(f => f.status === 'success') 
          ? `Successfully uploaded all ${filesToUpload.length} file(s).`
          : `Finished processing ${filesToUpload.length} file(s) with some errors.`;
      const hasErrors = currentUploadingFilesInfo.some(f => f.status === 'error');
      setOverallStatus({ message: finalStatusMsg, error: hasErrors ? 'One or more files failed to upload.' : '' });
      return currentUploadingFilesInfo; // Important for the setter to work correctly
    });
    
    // Reset the form for next upload
    setFilesWithCustomers([]);
    setShowCustomerFields(false);
    
    // Clear the file input value to allow selecting the same file(s) again
    if (fileInputRef.current) {
        fileInputRef.current.value = "";
    }
  };

  return (
    <div className={classes.card}>
      <div style={{ textAlign: 'center' }}>
        <CloudArrowUp24Regular className={classes.heroIcon} />
        <div className={classes.heroTitle}>Upload Files</div>
        <div id={instructionsId} className={classes.heroSubtext}>Click to browse</div>
        
        <input
          ref={fileInputRef}
          type="file"
          multiple
          onChange={handleFilesSelected}
          style={{ display: 'none' }}
          accept="*"
          aria-hidden="true"
        />
        
        <FluentButton
          appearance="secondary"
          size="small"
          icon={<Add24Regular />}
          onClick={handleAddClick}
          aria-describedby={instructionsId}
        >
          Browse Files
        </FluentButton>
      </div>

      {/* Customer name input fields - shown only after file selection */}
      {showCustomerFields && filesWithCustomers.length > 0 && (
        <div className={classes.sectionCard}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: tokens.spacingVerticalL }}>
            <h2 className={classes.sectionHeader} style={{ margin: 0 }}>📋 Customer Assignment</h2>
            <Tag size="small" appearance="outline" style={{ fontWeight: 500 }}>
              {`${filesWithCustomers.length} file${filesWithCustomers.length > 1 ? 's' : ''}`}
            </Tag>
          </div>
          
          <div className={classes.sectionDescription}>Please select the appropriate customer for each file to ensure proper processing.</div>
          
          {/* Compact grid layout for multiple files */}
          <div className={classes.grid} style={{ gridTemplateColumns: filesWithCustomers.length > 2 ? 'repeat(auto-fit, minmax(320px, 1fr))' : '1fr' }}>
            {filesWithCustomers.map((fileData, index) => (
              <div key={index} className={classes.fileCard}>
                <div style={{ display: 'flex', alignItems: 'center', marginBottom: tokens.spacingVerticalL }}>
                  {getFileIcon(fileData.file.name, classes)}
                  <div style={{ marginLeft: tokens.spacingHorizontalM, flex: 1, minWidth: 0 }}>
                    <div className={classes.fileTitle}>{fileData.file.name}</div>
                    <div className={classes.fileMeta}>{formatFileSize(fileData.file.size)}</div>
                  </div>
                </div>
                
                <div>
                  <Field
                    label="Customer"
                    hint="Required"
                    validationState={fileData.error ? 'error' : undefined}
                    validationMessage={fileData.error}
                  >
                    <Combobox
                      className={classes.controlFullWidth}
                      placeholder="Choose a customer..."
                      selectedOptions={fileData.customerName ? [fileData.customerName] : []}
                      onOptionSelect={(e, data) => handleCustomerNameChange(index, data.optionValue ?? '')}
                      aria-label={`Customer for ${fileData.file.name}`}
                    >
                      {customers.map((customer) => (
                        <Option key={customer} text={customer} value={customer}>
                          <span style={{ display: 'flex', alignItems: 'center', gap: tokens.spacingHorizontalS }}>
                            <Building16Regular className={`${classes.icon16} ${classes.iconBrand}`} />
                            {customer}
                          </span>
                        </Option>
                      ))}
                    </Combobox>
                  </Field>
                </div>
              </div>
            ))}
          </div>
          
          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: tokens.spacingVerticalXL, paddingTop: tokens.spacingVerticalS }}>
            <FluentButton
              appearance="outline"
              size="small"
              onClick={handleCancelUpload}
              icon={<Dismiss24Regular />}
            >
              Cancel
            </FluentButton>
            <FluentButton
              appearance="primary"
              size="small"
              onClick={handleProceedWithUpload}
              disabled={filesWithCustomers.every(f => !f.customerName.trim())}
              icon={<CloudArrowUp24Regular />}
            >
              Upload Files ({filesWithCustomers.length})
            </FluentButton>
          </div>
        </div>
      )}

      {/* Overall status alerts */}
      {overallStatus.message && !overallStatus.error && (
        <FluentAlert 
          intent="info" 
          style={{ marginTop: tokens.spacingVerticalL, borderRadius: 8 }}
          icon={<CloudArrowUp24Regular />}
          action={
            <FluentButton
              appearance="subtle"
              size="small"
              shape="circular"
              aria-label="close"
              onClick={dismissOverallStatus}
              icon={<Dismiss24Regular />}
            />
          }
          aria-live="polite"
        >
          {overallStatus.message}
        </FluentAlert>
      )}
      {overallStatus.error && (
        <FluentAlert 
          intent="error" 
          style={{ marginTop: tokens.spacingVerticalL, borderRadius: 8 }}
          action={
            <FluentButton
              appearance="subtle"
              size="small"
              shape="circular"
              aria-label="close"
              onClick={dismissOverallStatus}
              icon={<Dismiss24Regular />}
            />
          }
          aria-live="assertive"
        >
          {overallStatus.error}
        </FluentAlert>
      )}

      {/* File upload progress indicators */}
      {uploadingFilesInfo.length > 0 && (
        <div style={{ marginTop: tokens.spacingVerticalL }}>
          {uploadingFilesInfo.map((fileInfo, index) => (
            <div key={index} style={{ marginTop: tokens.spacingVerticalM, marginBottom: tokens.spacingVerticalS }}>
              <div style={{ display: 'flex', alignItems: 'center', marginBottom: tokens.spacingVerticalXS }}>
                <div style={{ flexGrow: 1, fontSize: tokens.fontSizeBase300 }}>
                  {fileInfo.name}
                </div>
                <div style={{ display: 'flex', alignItems: 'center' }}>
                  {fileInfo.status === 'success' && (
                    <CheckmarkCircle16Regular className={`${classes.icon16} ${classes.iconSuccess} ${classes.statusIcon}`} />
                  )}
                  {fileInfo.status === 'error' && (
                    <ErrorCircle16Regular className={`${classes.icon16} ${classes.iconError} ${classes.statusIcon}`} />
                  )}
                  <Tag
                    size="small"
                    appearance="outline"
                    dismissible
                    onDismiss={() => dismissFileStatus(index)}
                    style={{ height: 20, fontSize: tokens.fontSizeBase200 }}
                    aria-label={`Upload status: ${fileInfo.status}${fileInfo.status === 'uploading' ? ` ${fileInfo.progress}%` : ''}`}
                  >
                    {fileInfo.status === 'uploading' ? `${fileInfo.progress}%` : fileInfo.status}
                  </Tag>
                </div>
              </div>
              <ProgressBar 
                value={typeof fileInfo.progress === 'number' ? fileInfo.progress / 100 : undefined}
                style={{ height: 4, borderRadius: 2 }}
                aria-label={`Upload progress for ${fileInfo.name}`}
              />
              {fileInfo.status === 'error' && fileInfo.error && (
                <div className={classes.errorText} role="alert">
                  Error: {fileInfo.error}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default FileUpload;
