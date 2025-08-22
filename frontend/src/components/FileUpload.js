import React, { useState, useRef, useEffect } from 'react';
import { Button as FluentButton } from '@fluentui/react-components';
import { Alert as FluentAlert } from '@fluentui/react-alert';
import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';
import TextField from '@mui/material/TextField';
import FormControl from '@mui/material/FormControl';
import FormHelperText from '@mui/material/FormHelperText';
import Select from '@mui/material/Select';
import InputLabel from '@mui/material/InputLabel';
import MenuItem from '@mui/material/MenuItem';
import FormLabel from '@mui/material/FormLabel';
import LinearProgress from '@mui/material/LinearProgress';
import Chip from '@mui/material/Chip';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorIcon from '@mui/icons-material/Error';
import BusinessIcon from '@mui/icons-material/Business';
import Divider from '@mui/material/Divider';
import Badge from '@mui/material/Badge';
import { Add24Regular, Dismiss24Regular, Dismiss16Regular, CloudArrowUp24Regular } from '@fluentui/react-icons';
// File type icons for getFileIcon function
import PictureAsPdfIcon from '@mui/icons-material/PictureAsPdf';
import ImageIcon from '@mui/icons-material/Image';
import DescriptionIcon from '@mui/icons-material/Description';
import TextSnippetIcon from '@mui/icons-material/TextSnippet';
import InsertDriveFileIcon from '@mui/icons-material/InsertDriveFile';
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
      <Box sx={{ textAlign: 'center' }}>
        <CloudArrowUp24Regular style={{ width: 44, height: 44, color: '#60a5fa', marginBottom: 12, opacity: 0.8 }} />
        <Typography 
          variant="h6" 
          sx={{ 
            mb: 0.5,
            fontWeight: 400,
            color: '#32363a'
          }}
        >
          Upload Files
        </Typography>
        <Typography 
          variant="body2" 
          sx={{ 
            color: '#6a6d70',
            mb: 2
          }}
        >
          Drag and drop files here or click to browse
        </Typography>
        
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
      </Box>

      {/* Customer name input fields - shown only after file selection */}
      {showCustomerFields && filesWithCustomers.length > 0 && (
        <div className={classes.sectionCard}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
            <Typography variant="h6" sx={{ fontWeight: 600, fontSize: '1.1rem', color: '#1976d2' }}>
              📋 Customer Assignment
            </Typography>
            <Chip 
              label={`${filesWithCustomers.length} file${filesWithCustomers.length > 1 ? 's' : ''}`} 
              size="small" 
              color="primary" 
              variant="outlined"
              sx={{ fontWeight: 500 }}
            />
          </Box>
          
          <Typography variant="body2" sx={{ color: '#666', mb: 3 }}>
            Please select the appropriate customer for each file to ensure proper processing.
          </Typography>
          
          {/* Compact grid layout for multiple files */}
          <div className={classes.grid} style={{ gridTemplateColumns: filesWithCustomers.length > 2 ? 'repeat(auto-fit, minmax(320px, 1fr))' : '1fr' }}>
            {filesWithCustomers.map((fileData, index) => (
              <div key={index} className={classes.fileCard}>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                  {getFileIcon(fileData.file.name)}
                  <Box sx={{ ml: 1.5, flex: 1, minWidth: 0 }}>
                    <Typography variant="body2" sx={{ fontWeight: 600, color: '#333' }} noWrap>
                      {fileData.file.name}
                    </Typography>
                    <Typography variant="caption" sx={{ color: '#666' }}>
                      {formatFileSize(fileData.file.size)}
                    </Typography>
                  </Box>
                </Box>
                
                <Box>
                  <Select
                    fullWidth
                    value={fileData.customerName}
                    onChange={(e) => handleCustomerNameChange(index, e.target.value)}
                    size="small"
                    error={!!fileData.error}
                    MenuProps={{
                      PaperProps: {
                        sx: {
                          bgcolor: '#ffffff',
                          borderRadius: 2,
                          border: '1px solid #e0e0e0',
                          boxShadow: '0 8px 24px rgba(0, 0, 0, 0.12)',
                          mt: 1,
                          '& .MuiMenuItem-root': {
                            fontSize: '0.875rem',
                            fontWeight: 500,
                            color: '#333',
                            py: 1.5,
                            px: 2,
                            margin: '2px 4px',
                            borderRadius: 1,
                            '&:hover': {
                              bgcolor: '#f0f7ff',
                              color: '#1976d2'
                            },
                            '&.Mui-selected': {
                              bgcolor: '#e3f2fd',
                              color: '#1976d2',
                              fontWeight: 600,
                              '&:hover': {
                                bgcolor: '#e3f2fd'
                              }
                            }
                          }
                        }
                      }
                    }}
                    sx={{
                      borderRadius: 2,
                      bgcolor: '#ffffff',
                      fontFamily: "'Inter', 'Roboto', 'Arial', sans-serif",
                      fontSize: '0.875rem',
                      fontWeight: 500,
                      '& .MuiSelect-select': {
                        fontFamily: "'Inter', 'Roboto', 'Arial', sans-serif",
                        fontSize: '0.875rem',
                        fontWeight: 500,
                        py: 1.5,
                        px: 2,
                        display: 'flex',
                        alignItems: 'center',
                        gap: 1
                      },
                      '& .MuiOutlinedInput-notchedOutline': {
                        borderColor: '#d0d0d0',
                        borderWidth: '1.5px'
                      },
                      '&:hover .MuiOutlinedInput-notchedOutline': {
                        borderColor: '#60a5fa',
                        borderWidth: '2px'
                      },
                      '&.Mui-focused .MuiOutlinedInput-notchedOutline': {
                        borderColor: '#1976d2',
                        borderWidth: '2px'
                      },
                      '&.Mui-error .MuiOutlinedInput-notchedOutline': {
                        borderColor: '#d32f2f'
                      }
                    }}
                    displayEmpty
                  >
                    <MenuItem value="" disabled sx={{ fontStyle: 'italic', opacity: 0.7 }}>
                      <BusinessIcon sx={{ mr: 1, fontSize: '1rem', color: '#999' }} />
                      Choose a customer...
                    </MenuItem>
                    {customers.map((customer) => (
                      <MenuItem key={customer} value={customer}>
                        <BusinessIcon sx={{ mr: 1, fontSize: '1rem', color: '#1976d2' }} />
                        {customer}
                      </MenuItem>
                    ))}
                  </Select>
                  {fileData.error && (
                    <FormHelperText error sx={{ mt: 1, fontWeight: 500 }}>
                      {fileData.error}
                    </FormHelperText>
                  )}
                </Box>
              </div>
            ))}
          </div>
          
          <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 4, pt: 1 }}>
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
          </Box>
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
        <Box sx={{ mt: 2 }}>
          {uploadingFilesInfo.map((fileInfo, index) => (
            <Box key={index} sx={{ mt: 1.5, mb: 1 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 0.5 }}>
                <Typography variant="body2" sx={{ flexGrow: 1, fontSize: '0.875rem' }}>
                  {fileInfo.name}
                </Typography>
                <Box sx={{ display: 'flex', alignItems: 'center' }}>
                  {fileInfo.status === 'success' && <CheckCircleIcon sx={{ fontSize: 16, color: 'success.main', mr: 0.5 }} />}
                  {fileInfo.status === 'error' && <ErrorIcon sx={{ fontSize: 16, color: 'error.main', mr: 0.5 }} />}
                  <Chip
                    label={fileInfo.status === 'uploading' ? `${fileInfo.progress}%` : fileInfo.status}
                    size="small"
                    color={
                      fileInfo.status === 'success' ? 'success' : 
                      fileInfo.status === 'error' ? 'error' : 
                      'primary'
                    }
                    variant="outlined"
                    sx={{ height: 20, fontSize: '0.7rem' }}
                    deleteIcon={<Dismiss16Regular style={{ width: 14, height: 14 }} />}
                    onDelete={() => dismissFileStatus(index)}
                  />
                </Box>
              </Box>
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
                <Typography variant="caption" color="error" sx={{ display: 'block', mt: 0.5 }}>
                  Error: {fileInfo.error}
                </Typography>
              )}
            </Box>
          ))}
        </Box>
      )}
    </div>
  );
};

export default FileUpload;
