import React, { useState, useRef, useEffect } from 'react';
import { Button as FluentButton, Combobox, Option, Tag } from '@fluentui/react-components';
import { Alert as FluentAlert } from '@fluentui/react-alert';
import TextField from '@mui/material/TextField';
import FormControl from '@mui/material/FormControl';
import FormHelperText from '@mui/material/FormHelperText';
import InputLabel from '@mui/material/InputLabel';
import FormLabel from '@mui/material/FormLabel';
import LinearProgress from '@mui/material/LinearProgress';
// Removed MUI Chip in favor of Fluent Tag
import Divider from '@mui/material/Divider';
import Badge from '@mui/material/Badge';
import { 
  Add24Regular, 
  Dismiss24Regular, 
  Dismiss16Regular, 
  CloudArrowUp24Regular,
  CheckmarkCircle16Regular,
  ErrorCircle16Regular,
  Building16Regular,
  DocumentPdf16Regular,
  Image16Regular,
  DocumentText16Regular,
  Document16Regular,
} from '@fluentui/react-icons';
import { useTheme } from '../contexts/ThemeContext';
import { apiUrl } from '../config';
import { makeStyles, shorthands, tokens } from '@fluentui/react-components';

// Helper function to get appropriate icon for file type
const getFileIcon = (filename) => {
  // Extract extension from filename
  const fileExtension = filename && typeof filename === 'string' 
    ? filename.split('.').pop().toLowerCase() 
    : '';
  
  switch(fileExtension) {
    case 'pdf':
      return <DocumentPdf16Regular style={{ width: 16, height: 16, color: tokens.colorPaletteRedForeground1 }} />;
    case 'jpg':
    case 'jpeg':
    case 'png':
    case 'gif':
    case 'bmp':
      return <Image16Regular style={{ width: 16, height: 16, color: tokens.colorPaletteBlueForeground1 }} />;
    case 'doc':
    case 'docx':
      return <DocumentText16Regular style={{ width: 16, height: 16, color: tokens.colorBrandForeground1 }} />;
    case 'txt':
      return <DocumentText16Regular style={{ width: 16, height: 16, color: tokens.colorNeutralForeground3 }} />;
    default:
      return <Document16Regular style={{ width: 16, height: 16, color: tokens.colorNeutralForegroundDisabled }} />;
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
    ...shorthands.padding('24px'),
    ...shorthands.borderRadius('16px'),
    backgroundColor: tokens.colorNeutralBackground1,
    ...shorthands.border('1px', 'solid', tokens.colorNeutralStroke1),
  },
  center: {
    textAlign: 'center',
  },
  sectionCard: {
    ...shorthands.padding('16px'),
    marginBottom: '12px',
    backgroundColor: tokens.colorNeutralBackground1,
    ...shorthands.borderRadius('12px'),
    ...shorthands.border('1px', 'solid', tokens.colorNeutralStroke1),
    boxShadow: tokens.shadow8,
  },
  grid: {
    display: 'grid',
    gap: '20px',
  },
  fileCard: {
    ...shorthands.padding('20px'),
    backgroundColor: tokens.colorNeutralBackground2,
    ...shorthands.borderRadius('8px'),
    ...shorthands.border('1px', 'solid', tokens.colorNeutralStroke2),
    transitionProperty: 'box-shadow, border-color',
    transitionDuration: '200ms',
  },
});

const FileUpload = ({ onUploadSuccess }) => {
  const [uploadingFilesInfo, setUploadingFilesInfo] = useState([]); // To track multiple uploads
  const { theme } = useTheme();
  const isDark = theme === 'dark';
  const [overallStatus, setOverallStatus] = useState({ message: '', error: '' });
  const [filesWithCustomers, setFilesWithCustomers] = useState([]); // Array of {file, customerName, error} objects
  const [showCustomerFields, setShowCustomerFields] = useState(false); // Control visibility of customer fields
  const [customers, setCustomers] = useState([
    'TBS',
    'Eviosys',
    'BSW',
    'Asahi',
    'Corex',
    'Shoosmiths'
  ]); // Predefined customer list
  const fileInputRef = useRef(null);
  
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

  const classes = useStyles();

  return (
    <div className={classes.card}>
      <div style={{ textAlign: 'center' }}>
        <CloudArrowUp24Regular style={{ width: 44, height: 44, color: '#60a5fa', marginBottom: 12, opacity: 0.8 }} />
        <div 
          style={{ 
            marginBottom: 4,
            fontWeight: 400,
            color: '#32363a'
          }}
        >
          Upload Files
        </div>
        <div 
          style={{ 
            color: '#6a6d70',
            marginBottom: 16
          }}
        >
          Drag and drop files here or click to browse
        </div>
        
        <input
          ref={fileInputRef}
          type="file"
          multiple
          onChange={handleFilesSelected}
          style={{ display: 'none' }}
          accept="*"
        />
        
        <FluentButton
          appearance="primary"
          icon={<Add24Regular />}
          onClick={handleAddClick}
        >
          Browse Files
        </FluentButton>
      </div>

      {/* Customer name input fields - shown only after file selection */}
      {showCustomerFields && filesWithCustomers.length > 0 && (
        <div className={classes.sectionCard}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <div style={{ fontWeight: 600, fontSize: '1.1rem', color: '#1976d2' }}>
              📋 Customer Assignment
            </div>
            <Tag size="small" appearance="outline" style={{ fontWeight: 500 }}>
              {`${filesWithCustomers.length} file${filesWithCustomers.length > 1 ? 's' : ''}`}
            </Tag>
          </div>
          
          <div style={{ color: '#666', marginBottom: 24 }}>
            Please select the appropriate customer for each file to ensure proper processing.
          </div>
          
          {/* Compact grid layout for multiple files */}
          <div className={classes.grid} style={{ gridTemplateColumns: filesWithCustomers.length > 2 ? 'repeat(auto-fit, minmax(320px, 1fr))' : '1fr' }}>
            {filesWithCustomers.map((fileData, index) => (
              <div key={index} className={classes.fileCard}>
                <div style={{ display: 'flex', alignItems: 'center', marginBottom: 16 }}>
                  {getFileIcon(fileData.file.name)}
                  <div style={{ marginLeft: 12, flex: 1, minWidth: 0 }}>
                    <div style={{ fontWeight: 600, color: '#333', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {fileData.file.name}
                    </div>
                    <div style={{ color: '#666', fontSize: '0.75rem' }}>
                      {formatFileSize(fileData.file.size)}
                    </div>
                  </div>
                </div>
                
                <div>
                  <Combobox
                    style={{ width: '100%' }}
                    placeholder="Choose a customer..."
                    selectedOptions={fileData.customerName ? [fileData.customerName] : []}
                    onOptionSelect={(e, data) => handleCustomerNameChange(index, data.optionValue ?? '')}
                  >
                    {customers.map((customer) => (
                      <Option key={customer} text={customer} value={customer}>
                        <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <Building16Regular style={{ width: 16, height: 16, color: tokens.colorBrandForeground1 }} />
                          {customer}
                        </span>
                      </Option>
                    ))}
                  </Combobox>
                  {fileData.error && (
                    <FormHelperText error sx={{ mt: 1, fontWeight: 500 }}>
                      {fileData.error}
                    </FormHelperText>
                  )}
                </div>
              </div>
            ))}
          </div>
          
          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 32, paddingTop: 8 }}>
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
          style={{ marginTop: 16, borderRadius: 8 }}
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
        >
          {overallStatus.message}
        </FluentAlert>
      )}
      {overallStatus.error && (
        <FluentAlert 
          intent="error" 
          style={{ marginTop: 16, borderRadius: 8 }}
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
        >
          {overallStatus.error}
        </FluentAlert>
      )}

      {/* File upload progress indicators */}
      {uploadingFilesInfo.length > 0 && (
        <div style={{ marginTop: 16 }}>
          {uploadingFilesInfo.map((fileInfo, index) => (
            <div key={index} style={{ marginTop: 12, marginBottom: 8 }}>
              <div style={{ display: 'flex', alignItems: 'center', marginBottom: 4 }}>
                <div style={{ flexGrow: 1, fontSize: '0.875rem' }}>
                  {fileInfo.name}
                </div>
                <div style={{ display: 'flex', alignItems: 'center' }}>
                  {fileInfo.status === 'success' && (
                    <CheckmarkCircle16Regular style={{ width: 16, height: 16, color: tokens.colorPaletteGreenForeground1, marginRight: 4 }} />
                  )}
                  {fileInfo.status === 'error' && (
                    <ErrorCircle16Regular style={{ width: 16, height: 16, color: tokens.colorPaletteRedForeground1, marginRight: 4 }} />
                  )}
                  <Tag
                    size="small"
                    appearance="outline"
                    dismissible
                    onDismiss={() => dismissFileStatus(index)}
                    style={{ height: 20, fontSize: '0.7rem' }}
                  >
                    {fileInfo.status === 'uploading' ? `${fileInfo.progress}%` : fileInfo.status}
                  </Tag>
                </div>
              </div>
              <LinearProgress 
                variant={fileInfo.status === 'uploading' ? 'determinate' : 'determinate'} 
                value={fileInfo.progress}
                color={
                  fileInfo.status === 'success' ? 'success' : 
                  fileInfo.status === 'error' ? 'error' : 
                  'primary'
                }
                sx={{ height: 4, borderRadius: 2 }}
              />
              {fileInfo.status === 'error' && fileInfo.error && (
                <div style={{ display: 'block', marginTop: 4, color: '#d32f2f', fontSize: '0.75rem' }}>
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
