import React from 'react';
import Paper from '@mui/material/Paper';
import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import InsertDriveFileOutlinedIcon from '@mui/icons-material/InsertDriveFileOutlined';
import PictureAsPdfIcon from '@mui/icons-material/PictureAsPdf';
import ImageIcon from '@mui/icons-material/Image';
import DescriptionIcon from '@mui/icons-material/Description';
import TextSnippetIcon from '@mui/icons-material/TextSnippet';
import { useTheme } from '../contexts/ThemeContext';

// Helper function to get appropriate file type label and icon
const getFileTypeInfo = (fileName) => {
  if (!fileName || typeof fileName !== 'string') {
    return { icon: <InsertDriveFileOutlinedIcon />, label: 'UNKNOWN', color: 'default' };
  }
  
  // Extract extension safely
  let extension = '';
  if (fileName.includes('.')) {
    extension = fileName.split('.').pop().toLowerCase();
  }
  
  // Debug the extension extraction
  console.log(`Preview - File: ${fileName}, Extension detected: ${extension}`);
  
  switch(extension) {
    case 'pdf':
      return { 
        icon: <PictureAsPdfIcon sx={{ color: '#F44336' }} />, 
        label: 'PDF',
        color: 'error' 
      };
    case 'jpg':
    case 'jpeg':
    case 'png':
    case 'gif':
    case 'bmp':
      return { 
        icon: <ImageIcon sx={{ color: '#29B6F6' }} />, 
        label: 'IMAGE',
        color: 'info' 
      };
    case 'doc':
    case 'docx':
      return { 
        icon: <DescriptionIcon sx={{ color: '#90CAF9' }} />, 
        label: 'DOCUMENT',
        color: 'primary' 
      };
    case 'txt':
      return { 
        icon: <TextSnippetIcon sx={{ color: '#CE93D8' }} />, 
        label: 'TEXT',
        color: 'secondary' 
      };
    default:
      return { 
        icon: <InsertDriveFileOutlinedIcon sx={{ color: '#9E9E9E' }} />, 
        label: extension ? extension.toUpperCase() : 'FILE',
        color: 'default' 
      };
  }
};

const FilePreview = ({ selectedFile }) => {
  const fileTypeInfo = selectedFile ? getFileTypeInfo(selectedFile.name) : null;
  const { theme } = useTheme();
  const isDark = theme === 'dark';
  
  return (
    <Paper
      elevation={3}
      sx={{
        padding: 0,
        background: isDark 
          ? 'linear-gradient(145deg, #161616, #1E1E1E)'
          : 'linear-gradient(145deg, #f8f9fa, #ffffff)',
        borderRadius: 3,
        height: '100%',
        width: '100%',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        border: isDark 
          ? '1px solid rgba(255, 255, 255, 0.05)'
          : '1px solid rgba(0, 0, 0, 0.05)',
      }}
    >
      <Box sx={{ 
        px: 2, 
        py: 1.5, 
        borderBottom: isDark
          ? '1px solid rgba(255, 255, 255, 0.05)'
          : '1px solid rgba(0, 0, 0, 0.05)',
        display: 'flex',
        alignItems: 'center',
      }}>
        <Typography variant="h6" component="div" sx={{ flexGrow: 1, fontWeight: 500 }}>
          File Preview
        </Typography>
        {selectedFile && fileTypeInfo && (
          <Chip
            icon={fileTypeInfo.icon}
            label={fileTypeInfo.label}
            size="small"
            color={fileTypeInfo.color}
            variant="outlined"
            sx={{ borderRadius: 1 }}
          />
        )}
      </Box>
      
      <Box sx={{
        flexGrow: 1,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        p: 3,
        background: 'rgba(0, 0, 0, 0.2)'
      }}>
        {selectedFile ? (
          <Box sx={{ 
            width: '100%', 
            height: '100%',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            textAlign: 'center',
            px: 4,
          }}> 
            {fileTypeInfo && fileTypeInfo.icon && React.cloneElement(fileTypeInfo.icon, { 
              sx: { fontSize: 48, mb: 2, opacity: 0.7 } 
            })}
            <Typography variant="subtitle1" sx={{ fontWeight: 500, mb: 1 }}>
              {selectedFile.name}
            </Typography>
            <Typography variant="body2" sx={{ color: 'text.secondary', mb: 3, maxWidth: '80%' }}>
              Preview functionality will be added in a future update
            </Typography>
            <Box sx={{ 
              p: 2, 
              borderRadius: 2, 
              bgcolor: 'rgba(255, 255, 255, 0.03)', 
              border: '1px dashed rgba(255, 255, 255, 0.1)',
              maxWidth: '100%',
              width: '100%',
              height: '60%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}>
              <Typography variant="body2" color="text.disabled">
                Content preview placeholder
              </Typography>
            </Box>
          </Box>
        ) : (
          <Box sx={{ textAlign: 'center', maxWidth: 400 }}>
            <InsertDriveFileOutlinedIcon sx={{ fontSize: 64, color: 'text.disabled', mb: 2 }} />
            <Typography variant="h6" color="text.secondary" gutterBottom>
              No File Selected
            </Typography>
            <Typography variant="body2" color="text.disabled">
              Select a file from the list to preview its contents
            </Typography>
          </Box>
        )}
      </Box>
    </Paper>
  );
};

export default FilePreview;
