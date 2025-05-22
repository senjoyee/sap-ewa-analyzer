import React from 'react';
import { SvgIcon } from '@mui/material';

/**
 * Custom icon component that shows a magnifying glass with AI/neural network nodes
 */
const AiAnalysisIcon = (props) => {
  return (
    <SvgIcon {...props} viewBox="0 0 24 24">
      {/* Magnifying glass handle */}
      <path d="M15.5 14h-.79l-.28-.27C15.41 12.59 16 11.11 16 9.5 16 5.91 13.09 3 9.5 3S3 5.91 3 9.5 5.91 16 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5z" />
      
      {/* AI network nodes inside the magnifying glass */}
      <circle cx="7.5" cy="8" r="1" />
      <circle cx="10.5" cy="11" r="1" />
      <circle cx="8.5" cy="11" r="1" />
      <circle cx="11.5" cy="8" r="1" />
      <circle cx="9.5" cy="6.5" r="1" />
      
      {/* Connection lines */}
      <path d="M7.5 8L8.5 11" strokeWidth="0.5" />
      <path d="M7.5 8L9.5 6.5" strokeWidth="0.5" />
      <path d="M9.5 6.5L11.5 8" strokeWidth="0.5" />
      <path d="M11.5 8L10.5 11" strokeWidth="0.5" />
      <path d="M8.5 11L10.5 11" strokeWidth="0.5" />
    </SvgIcon>
  );
};

export default AiAnalysisIcon;
