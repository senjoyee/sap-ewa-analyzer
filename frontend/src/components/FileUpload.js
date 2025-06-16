import React, { useState, useRef, useEffect } from 'react';
import Button from '@mui/material/Button';
import Typography from '@mui/material/Typography';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Paper from '@mui/material/Paper';
import TextField from '@mui/material/TextField';
import FormControl from '@mui/material/FormControl';
import FormHelperText from '@mui/material/FormHelperText';
import Select from '@mui/material/Select';
import InputLabel from '@mui/material/InputLabel';
import MenuItem from '@mui/material/MenuItem';
import FormLabel from '@mui/material/FormLabel';
import LinearProgress from '@mui/material/LinearProgress';
import Chip from '@mui/material/Chip';
import IconButton from '@mui/material/IconButton';
import AddIcon from '@mui/icons-material/Add';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorIcon from '@mui/icons-material/Error';
import CloseIcon from '@mui/icons-material/Close';
import BusinessIcon from '@mui/icons-material/Business';
import Divider from '@mui/material/Divider';
import Badge from '@mui/material/Badge';
// File type icons for getFileIcon function
import PictureAsPdfIcon from '@mui/icons-material/PictureAsPdf';
import ImageIcon from '@mui/icons-material/Image';
import DescriptionIcon from '@mui/icons-material/Description';
import TextSnippetIcon from '@mui/icons-material/TextSnippet';
import InsertDriveFileIcon from '@mui/icons-material/InsertDriveFile';
import { useTheme } from '../contexts/ThemeContext';

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
    'Corex'
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

        const response = await fetch('http://localhost:8001/api/upload', {
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
    <Paper 
      elevation={0}
      sx={{ 
        p: 2.5,
        background: '#f8f9fa',
        border: '2px dashed #e0e0e0',
        borderRadius: 2,
        transition: 'all 0.3s ease',
        '&:hover': {
          borderColor: '#2193b0',
          background: '#f0f7ff',
        }
      }}
    >
      <Box sx={{ textAlign: 'center' }}>
        <CloudUploadIcon sx={{ 
          fontSize: 48, 
          color: '#2193b0',
          mb: 1,
          opacity: 0.8
        }} />
        <Typography 
          variant="h6" 
          sx={{ 
            mb: 0.5,
            fontWeight: 500,
            color: '#333'
          }}
        >
          Upload Files
        </Typography>
        <Typography 
          variant="body2" 
          sx={{ 
            color: '#666',
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
        
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={handleAddClick}
          sx={{
            background: 'linear-gradient(45deg, #2193b0 30%, #6dd5ed 90%)',
            color: 'white',
            px: 3,
            py: 1,
            borderRadius: 2,
            textTransform: 'none',
            fontWeight: 500,
            boxShadow: '0 3px 5px 2px rgba(33, 147, 176, .3)',
            '&:hover': {
              background: 'linear-gradient(45deg, #1e7e95 30%, #5bc0d8 90%)',
              boxShadow: '0 4px 8px 3px rgba(33, 147, 176, .4)',
            }
          }}
        >
          Browse Files
        </Button>
      </Box>

      {/* Customer name input fields - shown only after file selection */}
      {showCustomerFields && filesWithCustomers.length > 0 && (
        <Paper 
          elevation={0} 
          sx={{ 
            p: 3,
            mb: 3,
            bgcolor: isDark ? 'rgba(255, 255, 255, 0.05)' : 'rgba(0, 0, 0, 0.02)', 
            borderRadius: 2,
            border: isDark ? '1px solid rgba(255, 255, 255, 0.05)' : '1px solid rgba(0, 0, 0, 0.05)',
          }}
        >
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
            <Typography variant="subtitle2" sx={{ fontWeight: 500, fontSize: '1rem' }}>
              Enter Customer Information
            </Typography>
            <Badge badgeContent={filesWithCustomers.length} color="primary" sx={{ mr: 1 }}>
              <CloudUploadIcon color="action" fontSize="small" />
            </Badge>
          </Box>
          
          <Divider sx={{ mb: 3 }} />
          
          {/* Individual file entries with customer name fields */}
          {filesWithCustomers.map((fileData, index) => (
            <Box key={index} sx={{ mb: index < filesWithCustomers.length - 1 ? 4 : 0, py: 1 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                {getFileIcon(fileData.file.name)}
                <Typography variant="body2" sx={{ ml: 1.5, fontWeight: 500 }} noWrap>
                  {fileData.file.name}
                </Typography>
                <Typography variant="caption" sx={{ ml: 1.5, color: 'text.secondary' }}>
                  ({formatFileSize(fileData.file.size)})
                </Typography>
              </Box>
              
              <FormControl fullWidth error={!!fileData.error} sx={{ mb: 2, mt: 1 }} required>
                <InputLabel id={`customer-select-label-${index}`} error={!!fileData.error}>
                  Select Customer for {fileData.file.name.substring(0, 15)}...
                </InputLabel>
                <Select
                  labelId={`customer-select-label-${index}`}
                  value={fileData.customerName}
                  onChange={(e) => handleCustomerNameChange(index, e.target.value)}
                  size="small"
                  error={!!fileData.error}
                  required
                  startAdornment={<BusinessIcon sx={{ mr: 1, color: 'text.secondary' }} />}
                  sx={{
                    borderRadius: 1.5,
                    bgcolor: isDark ? 'rgba(255, 255, 255, 0.03)' : 'rgba(0, 0, 0, 0.02)',
                  }}
                  displayEmpty
                >
                  <MenuItem value="" disabled>
                    <em>Select a customer (required)</em>
                  </MenuItem>
                  {customers.map((customer) => (
                    <MenuItem key={customer} value={customer}>
                      {customer}
                    </MenuItem>
                  ))}
                </Select>
                {fileData.error && (
                  <FormHelperText error>{fileData.error}</FormHelperText>
                )}
              </FormControl>
              
              {index < filesWithCustomers.length - 1 && (
                <Divider sx={{ my: 3 }} />
              )}
            </Box>
          ))}
          
          <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 4, pt: 1 }}>
            <Button
              variant="outlined"
              size="small"
              onClick={handleCancelUpload}
              startIcon={<CloseIcon />}
              sx={{ py: 1 }}
            >
              Cancel
            </Button>
            <Button
              variant="contained"
              size="small"
              color="primary"
              onClick={handleProceedWithUpload}
              disabled={filesWithCustomers.every(f => !f.customerName.trim())}
              startIcon={<CloudUploadIcon />}
              sx={{ py: 1 }}
            >
              Upload Files ({filesWithCustomers.length})
            </Button>
          </Box>
        </Paper>
      )}

      {/* Overall status alerts */}
      {overallStatus.message && !overallStatus.error && (
        <Alert 
          severity="info" 
          sx={{ mt: 2, borderRadius: 1 }}
          icon={<CloudUploadIcon fontSize="inherit" />}
          action={
            <IconButton
              aria-label="close"
              color="inherit"
              size="small"
              onClick={dismissOverallStatus}
            >
              <CloseIcon fontSize="inherit" />
            </IconButton>
          }
        >
          {overallStatus.message}
        </Alert>
      )}
      {overallStatus.error && (
        <Alert 
          severity="error" 
          sx={{ mt: 2, borderRadius: 1 }}
          action={
            <IconButton
              aria-label="close"
              color="inherit"
              size="small"
              onClick={dismissOverallStatus}
            >
              <CloseIcon fontSize="inherit" />
            </IconButton>
          }
        >
          {overallStatus.error}
        </Alert>
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
                    deleteIcon={<CloseIcon style={{ fontSize: 14 }} />}
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
    </Paper>
  );
};

export default FileUpload;
