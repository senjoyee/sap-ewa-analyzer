import React, { useState, useRef } from 'react';
import Button from '@mui/material/Button';
import Typography from '@mui/material/Typography';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Paper from '@mui/material/Paper';
import TextField from '@mui/material/TextField';
import FormControl from '@mui/material/FormControl';
import FormHelperText from '@mui/material/FormHelperText';
import LinearProgress from '@mui/material/LinearProgress';
import Chip from '@mui/material/Chip';
import IconButton from '@mui/material/IconButton';
import AddIcon from '@mui/icons-material/Add';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorIcon from '@mui/icons-material/Error';
import CloseIcon from '@mui/icons-material/Close';
import BusinessIcon from '@mui/icons-material/Business';
import { useTheme } from '../contexts/ThemeContext';

const FileUpload = ({ onUploadSuccess }) => {
  const [uploadingFilesInfo, setUploadingFilesInfo] = useState([]); // To track multiple uploads
  const { theme } = useTheme();
  const isDark = theme === 'dark';
  const [overallStatus, setOverallStatus] = useState({ message: '', error: '' });
  const [customerName, setCustomerName] = useState(''); // State for customer name
  const [customerNameError, setCustomerNameError] = useState(''); // State for customer name validation error
  const [selectedFiles, setSelectedFiles] = useState(null); // Store selected files before upload
  const [showCustomerField, setShowCustomerField] = useState(false); // Control visibility of customer field
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

  // Handle customer name input change
  const handleCustomerNameChange = (event) => {
    const value = event.target.value;
    setCustomerName(value);
    
    // Clear error when user starts typing
    if (customerNameError && value.trim()) {
      setCustomerNameError('');
    }
  };

  // Validate customer name before proceeding with upload
  const validateCustomerName = () => {
    if (!customerName.trim()) {
      setCustomerNameError('Customer name is required');
      return false;
    }
    return true;
  };

  // Handle the initial file selection
  const handleAddClick = () => {
    fileInputRef.current.click();
  };
  
  // Handle proceeding with upload after customer name is entered
  const handleProceedWithUpload = () => {
    if (validateCustomerName() && selectedFiles) {
      processFileUpload(selectedFiles);
    }
  };
  
  // Handle canceling the upload and resetting the form
  const handleCancelUpload = () => {
    setSelectedFiles(null);
    setShowCustomerField(false);
    setCustomerName('');
    setCustomerNameError('');
  };

  // Handle when files are selected from the file dialog
  const handleFilesSelected = (event) => {
    const files = event.target.files;
    if (files.length === 0) {
      return;
    }
    
    // Store the selected files and show the customer name field
    setSelectedFiles(files);
    setShowCustomerField(true);
  };
  
  // Process the actual file upload after customer name is provided
  const processFileUpload = async (files) => {
    if (!files || files.length === 0) {
      return;
    }

    setOverallStatus({ message: `Starting upload of ${files.length} file(s) for customer: ${customerName}...`, error: '' });
    
    // Reset individual file tracking for this batch
    const initialFilesInfo = Array.from(files).map(file => ({
      name: file.name,
      progress: 0,
      status: 'pending', // 'pending', 'uploading', 'success', 'error'
      error: null,
      customer: customerName, // Add customer name to file info
    }));
    setUploadingFilesInfo(initialFilesInfo);

    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      setUploadingFilesInfo(prev => prev.map((f, index) => 
        index === i ? { ...f, status: 'uploading', progress: 0 } : f
      ));

      try {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('customer_name', customerName); // Add customer name to form data

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
        
        // After successful upload, reset the form for next upload
        setSelectedFiles(null);
        setShowCustomerField(false);

        setUploadingFilesInfo(prev => prev.map((f, index) => 
          index === i ? { ...f, progress: 100 } : f
        ));

        if (response.ok) {
          const result = await response.json();
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
          ? `Successfully uploaded all ${files.length} file(s).`
          : `Finished processing ${files.length} file(s) with some errors.`;
      const hasErrors = currentUploadingFilesInfo.some(f => f.status === 'error');
      setOverallStatus({ message: finalStatusMsg, error: hasErrors ? 'One or more files failed to upload.' : '' });
      return currentUploadingFilesInfo; // Important for the setter to work correctly
    });
    
    // Clear the file input value to allow selecting the same file(s) again
    if (fileInputRef.current) {
        fileInputRef.current.value = "";
    }
  };

  return (
    <Box sx={{ mb: 2 }}>
      <input
        type="file"
        multiple
        ref={fileInputRef}
        onChange={handleFilesSelected}
        style={{ display: 'none' }}
        accept="*" // Or specify types like ".pdf,.txt,.jpg"
      />
      
      {/* Customer name input field - shown only after file selection */}
      {showCustomerField && selectedFiles && (
        <Paper 
          elevation={0} 
          sx={{ 
            p: 2, 
            mb: 2,
            bgcolor: isDark ? 'rgba(255, 255, 255, 0.05)' : 'rgba(0, 0, 0, 0.02)', 
            borderRadius: 2,
            border: isDark ? '1px solid rgba(255, 255, 255, 0.05)' : '1px solid rgba(0, 0, 0, 0.05)',
          }}
        >
          <Typography variant="subtitle2" gutterBottom>
            Enter Customer Information
          </Typography>
          
          <FormControl fullWidth error={!!customerNameError} sx={{ mb: 2 }}>
            <TextField
              label="Customer Name"
              value={customerName}
              onChange={handleCustomerNameChange}
              variant="outlined"
              size="small"
              required
              autoFocus
              error={!!customerNameError}
              InputProps={{
                startAdornment: <BusinessIcon sx={{ mr: 1, color: 'text.secondary' }} />,
              }}
              sx={{
                '& .MuiOutlinedInput-root': {
                  borderRadius: 1.5,
                  bgcolor: isDark ? 'rgba(255, 255, 255, 0.03)' : 'rgba(0, 0, 0, 0.02)',
                }
              }}
            />
            {customerNameError && (
              <FormHelperText>{customerNameError}</FormHelperText>
            )}
          </FormControl>
          
          <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 1 }}>
            <Button
              variant="outlined"
              size="small"
              onClick={handleCancelUpload}
              startIcon={<CloseIcon />}
            >
              Cancel
            </Button>
            <Button
              variant="contained"
              size="small"
              color="primary"
              onClick={handleProceedWithUpload}
              disabled={!customerName.trim()}
              startIcon={<CloudUploadIcon />}
            >
              Upload Files ({selectedFiles?.length || 0})
            </Button>
          </Box>
          
          <Box sx={{ mt: 2 }}>
            <Typography variant="caption" color="text.secondary">
              Selected {selectedFiles?.length || 0} file(s) ready to upload
            </Typography>
            {Array.from(selectedFiles || []).slice(0, 3).map((file, idx) => (
              <Typography key={idx} variant="caption" display="block" color="text.secondary" noWrap>
                • {file.name}
              </Typography>
            ))}
            {selectedFiles && selectedFiles.length > 3 && (
              <Typography variant="caption" display="block" color="text.secondary">
                • ...and {selectedFiles.length - 3} more
              </Typography>
            )}
          </Box>
        </Paper>
      )}

      {/* File upload area - hidden when customer field is shown */}
      {!showCustomerField && (
        <Paper 
          elevation={0} 
          sx={{ 
            p: 2, 
            bgcolor: isDark ? 'rgba(255, 255, 255, 0.03)' : 'rgba(0, 0, 0, 0.02)', 
            border: isDark ? '1px dashed rgba(255, 255, 255, 0.2)' : '1px dashed rgba(0, 0, 0, 0.2)',
            borderRadius: 2,
            textAlign: 'center',
            transition: 'all 0.2s',
            '&:hover': {
              bgcolor: isDark ? 'rgba(255, 255, 255, 0.05)' : 'rgba(0, 0, 0, 0.04)',
              borderColor: 'primary.main'
            }
          }}
        >
          <Box sx={{ py: 1.5, display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
            <CloudUploadIcon sx={{ fontSize: 40, color: 'primary.main', mb: 1 }} />
            <Typography variant="h6" gutterBottom sx={{ fontSize: '1rem' }}>
              Upload Files
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
              Drag and drop files here or click to browse
            </Typography>
            <Button
              variant="contained"
              startIcon={<AddIcon />}
              onClick={handleAddClick}
              size="small"
            >
              Browse Files
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
    </Box>
  );
};

export default FileUpload;
