import React, { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import rehypeRaw from 'rehype-raw';
import remarkGfm from 'remark-gfm';
import { makeStyles } from '@griffel/react';
import { tokens, Button, Tooltip, Accordion as FluentAccordion, AccordionItem, AccordionHeader, AccordionPanel, ProgressBar } from '@fluentui/react-components';
import { DocumentPdf24Regular, ChevronDown24Regular, DataBarVertical24Regular, Settings24Regular } from '@fluentui/react-icons';
 
 
import { Image24Regular, Document24Regular, TextDescription24Regular } from '@fluentui/react-icons';
 
 
import { useTypographyStyles } from '../styles/typography';

// Import our custom table components
// import MetricsTable from './MetricsTable';
// import ParametersTable from './ParametersTable';
import DocumentChat from './DocumentChat';

// Import the SAP logo
import sapLogo from '../logo/sap-3.svg';

// Formatting utilities (dates/numbers)
import { formatDisplay } from '../utils/format';

// Import additional icons for status indicators
// Icons removed for status/risk to match PDF styling (text-only for status, filled chips for risk)

// Helper function to detect and style status/severity values
const getStatusStyle = (value, classes) => {
  if (!value || typeof value !== 'string') return null;
  const lowerValue = value.toLowerCase().trim();
  
  // Status mappings with enhanced visual styles
  const statusMap = {
    // Health statuses
    'good': { class: classes.statusGood, icon: null, label: 'GOOD', color: tokens.colorPaletteGreenForeground1 },
    'excellent': { class: classes.statusGood, icon: null, label: 'EXCELLENT', color: tokens.colorPaletteGreenForeground1 },
    'fair': { class: classes.statusFair, icon: null, label: 'FAIR', color: tokens.colorPaletteYellowForeground1 },
    'warning': { class: classes.statusFair, icon: null, label: 'WARNING', color: tokens.colorPaletteYellowForeground1 },
    'poor': { class: classes.statusPoor, icon: null, label: 'POOR', color: tokens.colorPaletteRedForeground1 },
    // Risk levels use distinct outlined chip styles
    'critical': { class: `${classes.riskBase} ${classes.riskCritical}`, icon: null, label: 'CRITICAL', color: tokens.colorPaletteRedForeground1 },
    'error': { class: classes.statusPoor, icon: null, label: 'ERROR', color: tokens.colorPaletteRedForeground1 },

    // Risk levels (map to closest visual chips used in PDF)
    'high': { class: `${classes.riskBase} ${classes.riskHigh}`, icon: null, label: 'HIGH', color: tokens.colorPaletteYellowForeground1 },
    'medium': { class: `${classes.riskBase} ${classes.riskMedium}`, icon: null, label: 'MEDIUM', color: tokens.colorBrandForeground1 },
    'low': { class: `${classes.riskBase} ${classes.riskLow}`, icon: null, label: 'LOW', color: tokens.colorPaletteGreenForeground1 },
  };
  
  return statusMap[lowerValue] || null;
};

// Helper function to get appropriate file type label and icon
const API_BASE = 'http://localhost:8001';
const getFileTypeInfo = (fileName, classes) => {
  if (!fileName || typeof fileName !== 'string') {
    return { icon: <Document24Regular className={`${classes.icon20} ${classes.iconNeutral}`} />, label: 'UNKNOWN', color: 'default' };
  }
  
  // Extract extension safely
  let extension = '';
  if (fileName.includes('.')) {
    extension = fileName.split('.').pop().toLowerCase();
  }
  
  switch(extension) {
    case 'pdf':
      return { icon: <DocumentPdf24Regular className={`${classes.icon20} ${classes.iconError}`} />, label: 'PDF', color: 'error' };
    case 'jpg':
    case 'jpeg':
    case 'png':
    case 'gif':
    case 'bmp':
      return { icon: <Image24Regular className={`${classes.icon20} ${classes.iconInfo}`} />, label: 'IMAGE', color: 'info' };
    case 'doc':
    case 'docx':
      return { icon: <Document24Regular className={`${classes.icon20} ${classes.iconBrand}`} />, label: 'DOCUMENT', color: 'primary' };
    case 'txt':
      return { icon: <TextDescription24Regular className={`${classes.icon20} ${classes.iconNeutral}`} />, label: 'TEXT', color: 'secondary' };
    default:
      return { icon: <Document24Regular className={`${classes.icon20} ${classes.iconNeutral}`} />, label: extension ? extension.toUpperCase() : 'FILE', color: 'default' };
  }
};

// Enhanced styles for visual appeal
const useStyles = makeStyles({
  container: {
    padding: '0px',
    backgroundColor: '#F9FAFB',
    borderRadius: tokens.borderRadiusLarge,
    height: '100%',
    width: '100%',
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden',
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    boxShadow: `0 8px 32px rgba(0, 0, 0, 0.08), 0 4px 16px rgba(0, 0, 0, 0.04)`,
    minWidth: 0,
    position: 'relative',
    '::before': {
      content: 'none',
    },
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
  headerBar: {
    paddingLeft: tokens.spacingHorizontalL,
    paddingRight: tokens.spacingHorizontalL,
    paddingTop: tokens.spacingVerticalM,
    paddingBottom: tokens.spacingVerticalM,
    borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
    display: 'flex',
    alignItems: 'center',
    background: 'transparent',
    gap: tokens.spacingHorizontalS,
    flexWrap: 'wrap',
    rowGap: tokens.spacingVerticalXS,
    position: 'relative',
    backdropFilter: 'none',
    '::after': { content: 'none' },
    '@media (max-width: 600px)': {
      flexDirection: 'column',
      alignItems: 'stretch',
      gap: tokens.spacingVerticalXS,
    },
  },
  title: {
    fontWeight: tokens.fontWeightBold,
    background: `linear-gradient(135deg, ${tokens.colorBrandForeground1} 0%, ${tokens.colorCompoundBrandForeground1} 70%, ${tokens.colorBrandForeground2} 100%)`,
    backgroundClip: 'text',
    WebkitBackgroundClip: 'text',
    WebkitTextFillColor: 'transparent',
    fontSize: tokens.fontSizeBase600,
    lineHeight: '28px',
    flexGrow: 1,
    minWidth: 0,
    overflowWrap: 'anywhere',
    letterSpacing: '-0.01em',
    fontFeatureSettings: '"ss01", "ss02"',
    textRendering: 'optimizeLegibility',
  },
  actionBar: {
    display: 'flex',
    alignItems: 'center',
    gap: tokens.spacingHorizontalXS,
    flexWrap: 'wrap',
    '@media (max-width: 600px)': {
      width: '100%',
      justifyContent: 'flex-start',
      rowGap: tokens.spacingVerticalXXS,
    },
  },
  // Icon sizing and colors
  icon16: { width: 16, height: 16 },
  icon20: { width: 20, height: 20 },
  icon24: { width: 24, height: 24 },
  iconBrand: { color: tokens.colorBrandForeground1 },
  iconInfo: { color: tokens.colorPaletteBlueForeground2 },
  iconError: { color: tokens.colorPaletteRedForeground2 },
  iconNeutral: { color: tokens.colorNeutralForeground3 },
  headerIcon: { marginRight: tokens.spacingHorizontalS, color: tokens.colorBrandForeground1 },
  headerTextBrand: { fontWeight: tokens.fontWeightSemibold, color: tokens.colorBrandForeground1 },
  accordionSection: {
    marginTop: tokens.spacingVerticalL,
    marginBottom: tokens.spacingVerticalL,
  },
  accordionHeader: {
    background: `linear-gradient(135deg, ${tokens.colorNeutralBackground2} 0%, ${tokens.colorSubtleBackground} 100%)`,
    borderRadius: tokens.borderRadiusMedium,
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    boxShadow: `0 2px 4px rgba(0, 0, 0, 0.04)`,
    transition: 'all 300ms cubic-bezier(0.4, 0, 0.2, 1)',
    position: 'relative',
    overflow: 'hidden',
    selectors: {
      '&:hover': { 
        backgroundColor: tokens.colorSubtleBackgroundHover,
        transform: 'translateY(-1px)',
        boxShadow: `0 4px 12px rgba(0, 0, 0, 0.08)`,
      },
      '&:focus-visible': { 
        outline: `${tokens.strokeWidthThick} solid ${tokens.colorBrandStroke1}`, 
        outlineOffset: 2,
        boxShadow: `0 0 0 4px ${tokens.colorBrandBackground2}`,
      },
      '::before': {
        content: '""',
        position: 'absolute',
        top: 0,
        left: 0,
        right: 0,
        height: '2px',
        background: `linear-gradient(90deg, ${tokens.colorBrandForeground1}, ${tokens.colorBrandForeground2})`,
        opacity: 0,
        transition: 'opacity 300ms ease',
      },
      '&:hover::before': {
        opacity: 1,
      },
    },
  },
  accordionPanel: {
    padding: tokens.spacingHorizontalXL,
    background: `linear-gradient(135deg, ${tokens.colorNeutralBackground1} 0%, ${tokens.colorSubtleBackground} 100%)`,
    borderRadius: `0 0 ${tokens.borderRadiusMedium} ${tokens.borderRadiusMedium}`,
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    borderTop: 'none',
    boxShadow: `inset 0 2px 4px rgba(0, 0, 0, 0.04)`,
  },
  fileBadge: {
    display: 'inline-flex',
    alignItems: 'center',
    borderRadius: tokens.borderRadiusMedium,
    padding: `${tokens.spacingVerticalXS} ${tokens.spacingHorizontalS}`,
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    background: `linear-gradient(135deg, ${tokens.colorNeutralBackground1} 0%, ${tokens.colorNeutralBackground2} 100%)`,
    boxShadow: `0 2px 8px rgba(0, 0, 0, 0.06), inset 0 1px 0 rgba(255, 255, 255, 0.1)`,
    transition: 'all 200ms cubic-bezier(0.34, 1.56, 0.64, 1)',
    position: 'relative',
    overflow: 'hidden',
    '::before': {
      content: '""',
      position: 'absolute',
      top: 0,
      left: '-100%',
      width: '100%',
      height: '100%',
      background: `linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.2), transparent)`,
      transition: 'left 600ms ease',
    },
    ':hover::before': {
      left: '100%',
    },
    ':hover': {
      transform: 'translateY(-1px)',
      boxShadow: `0 4px 16px rgba(0, 0, 0, 0.12), inset 0 1px 0 rgba(255, 255, 255, 0.2)`,
    },
  },
  badgeIcon: {
    display: 'inline-flex',
    alignItems: 'center',
    marginRight: tokens.spacingHorizontalXS,
  },
  badgeLabel: {
    fontSize: tokens.fontSizeBase200,
    color: tokens.colorNeutralForeground2,
  },
  noFileSelected: {
    textAlign: 'center',
    maxWidth: '400px',
    marginLeft: 'auto',
    marginRight: 'auto',
  },
  noFileTitle: {
    fontWeight: tokens.fontWeightSemibold,
    color: tokens.colorNeutralForeground2,
    marginBottom: tokens.spacingVerticalXS,
    fontSize: tokens.fontSizeBase500,
  },
  noFileText: {
    color: tokens.colorNeutralForeground3,
    fontSize: tokens.fontSizeBase300,
  },
  mdH1: {
    marginTop: tokens.spacingVerticalXXL,
    marginBottom: tokens.spacingVerticalL,
    fontWeight: tokens.fontWeightBold,
    fontSize: tokens.fontSizeBase600,
    letterSpacing: '-0.02em',
    color: tokens.colorNeutralForeground1,
    position: 'relative',
    paddingBottom: 0,
    '::after': {
      content: 'none',
    },
  },
  mdH2: {
    marginTop: tokens.spacingVerticalXL,
    marginBottom: tokens.spacingVerticalM,
    fontWeight: tokens.fontWeightBold,
    fontSize: tokens.fontSizeBase500,
    letterSpacing: '-0.01em',
    color: tokens.colorNeutralForeground1,
    position: 'relative',
    paddingLeft: tokens.spacingHorizontalM,
    '::before': {
      content: '""',
      position: 'absolute',
      left: 0,
      top: '50%',
      transform: 'translateY(-50%)',
      width: '4px',
      height: '24px',
      background: `linear-gradient(180deg, ${tokens.colorBrandForeground1}, ${tokens.colorBrandForeground2})`,
      borderRadius: tokens.borderRadiusSmall,
    },
  },
  mdH3: {
    marginTop: tokens.spacingVerticalL,
    marginBottom: tokens.spacingVerticalS,
    fontWeight: tokens.fontWeightSemibold,
    fontSize: tokens.fontSizeBase200,
    color: tokens.colorBrandForeground1,
    letterSpacing: '0.01em',
    textTransform: 'uppercase',
  },
  mdP: {
    marginBottom: tokens.spacingVerticalM,
    fontSize: tokens.fontSizeBase300,
    lineHeight: '1.6',
    color: tokens.colorNeutralForeground1,
    fontWeight: tokens.fontWeightRegular,
  },
  mdUl: {
    marginBottom: tokens.spacingVerticalM,
    paddingLeft: tokens.spacingHorizontalXL,
    fontSize: tokens.fontSizeBase300,
    lineHeight: '1.6',
  },
  mdOl: {
    marginBottom: tokens.spacingVerticalM,
    paddingLeft: tokens.spacingHorizontalXL,
    fontSize: tokens.fontSizeBase300,
    lineHeight: '1.6',
  },
  mdLi: {
    marginBottom: tokens.spacingVerticalS,
    fontSize: tokens.fontSizeBase300,
    color: tokens.colorNeutralForeground1,
    fontWeight: tokens.fontWeightRegular,
    lineHeight: '1.6',
    position: 'relative',
    '::marker': {
      color: tokens.colorBrandForeground1,
      fontWeight: tokens.fontWeightBold,
    },
  },
  mdStrong: {
    fontWeight: tokens.fontWeightSemibold,
    color: tokens.colorNeutralForeground1,
  },
  mdEm: {
    fontStyle: 'normal',
    fontWeight: 400,
  },
  mdBlockquote: {
    borderLeft: `4px solid ${tokens.colorBrandStroke1}`,
    paddingLeft: tokens.spacingHorizontalM,
    marginLeft: 0,
    marginTop: tokens.spacingVerticalM,
    marginBottom: tokens.spacingVerticalM,
    fontStyle: 'italic',
    color: tokens.colorNeutralForeground3,
    fontSize: tokens.fontSizeBase200,
  },
  mdLink: {
    color: tokens.colorBrandForeground1,
    textDecoration: 'underline',
    fontWeight: tokens.fontWeightMedium,
  },
  mdPre: {
    padding: tokens.spacingHorizontalS,
    marginTop: tokens.spacingVerticalXS,
    marginBottom: tokens.spacingVerticalXS,
    backgroundColor: tokens.colorNeutralBackground3,
    borderRadius: tokens.borderRadiusMedium,
    overflowX: 'auto',
    fontSize: tokens.fontSizeBase200,
  },
  tableCard: {
    marginTop: tokens.spacingVerticalL,
    marginBottom: tokens.spacingVerticalL,
    borderRadius: tokens.borderRadiusLarge,
    overflow: 'hidden',
    background: `linear-gradient(135deg, ${tokens.colorNeutralBackground1} 0%, ${tokens.colorSubtleBackground} 100%)`,
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    boxShadow: `0 8px 24px rgba(0, 0, 0, 0.06), 0 2px 8px rgba(0, 0, 0, 0.04)`,
    position: 'relative',
    transition: 'all 300ms cubic-bezier(0.4, 0, 0.2, 1)',
    ':hover': {
      transform: 'translateY(-2px)',
      boxShadow: `0 12px 32px rgba(0, 0, 0, 0.08), 0 4px 16px rgba(0, 0, 0, 0.06)`,
    },
    '::before': {
      content: '""',
      position: 'absolute',
      top: 0,
      left: 0,
      right: 0,
      height: '3px',
      background: `linear-gradient(90deg, ${tokens.colorBrandForeground1}, ${tokens.colorCompoundBrandForeground1}, ${tokens.colorBrandForeground2})`,
      borderRadius: `${tokens.borderRadiusLarge} ${tokens.borderRadiusLarge} 0 0`,
    },
  },
  tableTitle: {
    padding: `${tokens.spacingVerticalM} ${tokens.spacingHorizontalL}`,
    background: `linear-gradient(135deg, ${tokens.colorSubtleBackground} 0%, ${tokens.colorNeutralBackground2} 100%)`,
    color: tokens.colorNeutralForeground1,
    fontWeight: tokens.fontWeightBold,
    fontSize: tokens.fontSizeBase400,
    letterSpacing: '-0.01em',
    borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
    position: 'relative',
    '::after': {
      content: '""',
      position: 'absolute',
      bottom: 0,
      left: tokens.spacingHorizontalL,
      right: tokens.spacingHorizontalL,
      height: '2px',
      background: `linear-gradient(90deg, ${tokens.colorBrandForeground2}, transparent)`,
      opacity: 0.6,
    },
  },
  tableScroll: {
    overflowX: 'auto',
    transition: 'outline-color 150ms ease, box-shadow 150ms ease',
    ':focus-visible': {
      outline: `2px solid ${tokens.colorBrandStroke1}`,
      outlineOffset: '2px',
    },
  },
  mdTable: {
    width: '100%',
    borderCollapse: 'collapse',
    tableLayout: 'auto',
    fontSize: tokens.fontSizeBase300,
    selectors: {
      'tbody tr': {
        transition: 'all 200ms ease',
        position: 'relative',
      },
      'tbody tr:nth-child(even)': {
        backgroundColor: tokens.colorSubtleBackground,
      },
      'tbody tr:hover': {
        backgroundColor: tokens.colorSubtleBackgroundHover,
        transform: 'scale(1.005)',
        boxShadow: `0 2px 8px rgba(0, 0, 0, 0.08)`,
        zIndex: 1,
      },
      'tbody tr:hover td': {
        borderColor: tokens.colorBrandStroke2,
      },
    },
  },
  mdTh: {
    textAlign: 'left',
    padding: `${tokens.spacingVerticalM} ${tokens.spacingHorizontalM}`,
    fontWeight: tokens.fontWeightBold,
    fontSize: tokens.fontSizeBase300,
    color: tokens.colorNeutralForeground1,
    borderBottom: `2px solid ${tokens.colorNeutralStroke2}`,
    background: `linear-gradient(135deg, ${tokens.colorNeutralBackground2} 0%, ${tokens.colorSubtleBackground} 100%)`,
    letterSpacing: '0.02em',
    textTransform: 'uppercase',
    position: 'sticky',
    top: 0,
    zIndex: 2,
    '::after': {
      content: '""',
      position: 'absolute',
      bottom: 0,
      left: 0,
      right: 0,
      height: '1px',
      background: `linear-gradient(90deg, transparent, ${tokens.colorBrandForeground2}, transparent)`,
      opacity: 0.5,
    },
  },
  mdTd: {
    padding: `${tokens.spacingVerticalM} ${tokens.spacingHorizontalM}`,
    fontSize: tokens.fontSizeBase300,
    color: tokens.colorNeutralForeground1,
    fontWeight: tokens.fontWeightRegular,
    borderBottom: `1px solid ${tokens.colorNeutralStroke1}`,
    verticalAlign: 'top',
    lineHeight: '1.6',
    transition: 'all 200ms ease',
    position: 'relative',
  },
  contentArea: {
    flex: 1,
    padding: tokens.spacingHorizontalXL,
    backgroundColor: '#FFFFFF',
    overflowY: 'auto',
    display: 'flex',
    alignItems: 'stretch',
    justifyContent: 'flex-start',
    position: 'relative',
    // Enhanced custom scrollbar
    scrollbarWidth: 'thin',
    scrollbarColor: `${tokens.colorBrandStroke1} transparent`,
    msOverflowStyle: 'auto',
    selectors: {
      '&::-webkit-scrollbar': { width: '8px' },
      '&::-webkit-scrollbar-track': { 
        background: 'transparent',
        borderRadius: '4px',
      },
      '&::-webkit-scrollbar-thumb': { 
        background: `linear-gradient(180deg, ${tokens.colorBrandForeground1}, ${tokens.colorBrandForeground2})`,
        borderRadius: '4px',
        border: '1px solid transparent',
        backgroundClip: 'padding-box',
      },
      '&::-webkit-scrollbar-thumb:hover': { 
        background: `linear-gradient(180deg, ${tokens.colorCompoundBrandForeground1}, ${tokens.colorBrandForeground1})`,
        boxShadow: '0 2px 8px rgba(0, 0, 0, 0.2)',
      },
    },
    '@media (max-width: 600px)': {
      padding: tokens.spacingHorizontalM,
    },
  },
  // High-quality text rendering to match PDF appearance
  previewTextRoot: {
    fontFamily: '"Inter", system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
    fontKerning: 'normal',
    fontVariantLigatures: 'common-ligatures contextual',
    fontFeatureSettings: '"liga" 1, "calt" 1, "kern" 1',
    fontOpticalSizing: 'auto',
    textRendering: 'optimizeLegibility',
    WebkitFontSmoothing: 'antialiased',
    MozOsxFontSmoothing: 'grayscale',
    // Prevent synthetic styles that can blur glyph edges
    fontSynthesis: 'none',
    color: tokens.colorNeutralForeground1,
    selectors: {
      '& code, & pre': {
        fontFamily: '"JetBrains Mono", Consolas, "Courier New", monospace',
      },
      '& h1, & h2': {
        letterSpacing: '-0.01em',
      },
    },
  },
  noFileIcon: {
    fontSize: 64,
    color: tokens.colorNeutralForeground3,
    marginBottom: 8,
  },
  analysisArea: {
    alignItems: 'stretch',
    justifyContent: 'flex-start',
  },
  centerArea: {
    alignItems: 'center',
    justifyContent: 'center',
    flexDirection: 'column',
  },
  analysisInner: {
    width: '100%',
    maxWidth: '100%',
    margin: '0 auto',
  },
  panelInner: {
    backgroundColor: tokens.colorNeutralBackground1,
    border: `1px solid ${tokens.colorNeutralStroke1}`,
    borderRadius: tokens.borderRadiusMedium,
    padding: tokens.spacingHorizontalM,
  },
  placeholderContainer: {
    textAlign: 'center',
    color: tokens.colorNeutralForeground3,
    maxWidth: '560px',
    margin: '0 auto',
  },
  placeholderTitle: {
    fontWeight: tokens.fontWeightSemibold,
    color: tokens.colorNeutralForeground2,
    fontSize: tokens.fontSizeBase600,
    marginBottom: tokens.spacingVerticalXS,
  },
  placeholderText: {
    color: tokens.colorNeutralForeground3,
    fontSize: tokens.fontSizeBase400,
    marginBottom: tokens.spacingVerticalS,
  },
  placeholderFrame: {
    border: `1px dashed ${tokens.colorNeutralStroke1}`,
    borderRadius: tokens.borderRadiusMedium,
    padding: tokens.spacingHorizontalL,
    minHeight: '160px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  },
  placeholderMuted: {
    color: tokens.colorNeutralForeground3,
    fontSize: tokens.fontSizeBase100,
  },
  // Enhanced status chip styles
  statusChip: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: tokens.spacingHorizontalXXS,
    fontSize: 'inherit',
    fontWeight: tokens.fontWeightSemibold,
    letterSpacing: '0.02em',
    textTransform: 'uppercase',
    position: 'relative',
    overflow: 'visible',
    transition: 'none',
  },
  statusGood: {
    backgroundColor: 'transparent',
    color: '#38a169', // match PDF status-good color
    border: 'none',
  },
  statusFair: {
    backgroundColor: 'transparent',
    color: '#d69e2e', // match PDF status-fair color
    border: 'none',
  },
  statusPoor: {
    backgroundColor: 'transparent',
    color: '#e53e3e', // match PDF status-poor color
    border: 'none',
  },
  // Risk chip variants (match PDF gradient-filled style)
  riskBase: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: tokens.spacingHorizontalXXS,
    padding: `${tokens.spacingVerticalXXS} ${tokens.spacingHorizontalXS}`,
    borderRadius: tokens.borderRadiusSmall,
    fontSize: 'inherit',
    fontWeight: tokens.fontWeightSemibold,
    letterSpacing: '0.02em',
    textTransform: 'uppercase',
    border: 'none',
    boxShadow: 'none',
  },
  riskCritical: {
    background: 'linear-gradient(135deg, #fed7d7, #feb2b2)',
    color: '#742a2a',
  },
  riskHigh: {
    background: 'linear-gradient(135deg, #feebc8, #fbd38d)',
    color: '#7b341e',
  },
  riskMedium: {
    background: 'linear-gradient(135deg, #fefcbf, #faf089)',
    color: '#744210',
  },
  riskLow: {
    background: 'linear-gradient(135deg, #c6f6d5, #9ae6b4)',
    color: '#22543d',
  },
  // Enhanced skeleton styles with shimmer animation
  skeletonContainer: {
    display: 'flex',
    flexDirection: 'column',
    rowGap: tokens.spacingVerticalS,
  },
  skeletonLine: {
    width: '100%',
    height: '12px',
    borderRadius: tokens.borderRadiusSmall,
    background: `linear-gradient(90deg, ${tokens.colorNeutralBackground3} 25%, ${tokens.colorNeutralBackground2} 50%, ${tokens.colorNeutralBackground3} 75%)`,
    backgroundSize: '200% 100%',
    animation: 'shimmer 1.5s infinite',
    position: 'relative',
    overflow: 'hidden',
  },
  skeletonBlock: {
    width: '100%',
    height: '120px',
    borderRadius: tokens.borderRadiusMedium,
    background: `linear-gradient(90deg, ${tokens.colorNeutralBackground3} 25%, ${tokens.colorNeutralBackground2} 50%, ${tokens.colorNeutralBackground3} 75%)`,
    backgroundSize: '200% 100%',
    animation: 'shimmer 1.5s infinite',
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    position: 'relative',
    overflow: 'hidden',
  },
  // Animation keyframes
  '@keyframes shimmer': {
    '0%': { backgroundPosition: '200% 0' },
    '100%': { backgroundPosition: '-200% 0' },
  },
});

const JsonCodeBlockRenderer = ({ node, inline, className, children, ...props }) => {
  const classes = useStyles();
  const typography = useTypographyStyles();
  const match = /language-(\w+)/.exec(className || '');
  const lang = match && match[1];

  if (lang === 'json' && !inline) {
    try {
      const jsonString = String(children).replace(/\n$/, ''); // Remove trailing newline
      const jsonData = JSON.parse(jsonString);

      // Case 1: Check if it's the Key System Information format with items (parameter/value pairs)
      if (jsonData && jsonData.tableTitle && Array.isArray(jsonData.items)) {
        return (
          <div className={classes.tableCard}>
            <div className={`${classes.tableTitle} ${typography.headingM}`}>{jsonData.tableTitle}</div>
            <div className={classes.tableScroll} tabIndex={0} role="group" aria-label={`${jsonData.tableTitle} table`}>
              <table className={classes.mdTable} aria-label={`${jsonData.tableTitle} data`}>
                <thead>
                  <tr>
                    <th className={classes.mdTh} style={{ width: '40%' }} scope="col">Parameter</th>
                    <th className={classes.mdTh} style={{ width: '60%' }} scope="col">Value</th>
                  </tr>
                </thead>
                <tbody>
                  {jsonData.items.map((item, index) => (
                    <tr key={index}>
                      <td className={classes.mdTd} style={{ fontWeight: 500 }}>{item.parameter}</td>
                      <td className={classes.mdTd} style={{ textAlign: 'left' }}>
                        {(() => {
                          const statusStyle = getStatusStyle(item.value, classes);
                          return statusStyle ? (
                            <span className={`${classes.statusChip} ${statusStyle.class}`}>
                              {statusStyle.icon}
                              {statusStyle.label}
                            </span>
                          ) : (
                            formatDisplay(item.value)
                          );
                        })()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        );
      }
      
      // Case 2: Check if it's our table structure with headers and rows
      else if (jsonData && jsonData.tableTitle && Array.isArray(jsonData.headers) && Array.isArray(jsonData.rows)) {
        const wrapStyle = { whiteSpace: 'normal', overflow: 'visible', textOverflow: 'clip', wordBreak: 'break-word', overflowWrap: 'anywhere' };
        return (
          <div className={classes.tableCard}>
            <div className={`${classes.tableTitle} ${typography.headingM}`}>{jsonData.tableTitle}</div>
            <div className={classes.tableScroll} tabIndex={0} role="group" aria-label={`${jsonData.tableTitle} table`}>
              <table className={classes.mdTable} aria-label={`${jsonData.tableTitle} data`}>
                <thead>
                  <tr>
                    {jsonData.headers.map((header, index) => (
                      <th key={index} className={classes.mdTh} style={{ textAlign: 'left' }} scope="col">
                        {header.charAt(0).toUpperCase() + header.slice(1).replace(/_/g, ' ')}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {jsonData.rows.map((row, rowIndex) => (
                    <tr key={rowIndex}>
                      {jsonData.headers.map((header, cellIndex) => {
                        const rawCell = row[header] === undefined || row[header] === null ? '' : row[header];
                        const cellValue = String(rawCell);
                        const isLong = cellValue.length > 50;
                        const statusStyle = getStatusStyle(cellValue, classes);
                        
                        return (
                          <td key={cellIndex} className={classes.mdTd} style={{ textAlign: 'left', ...(isLong ? wrapStyle : {}) }}>
                            {statusStyle ? (
                              <span className={`${classes.statusChip} ${statusStyle.class}`}>
                                {statusStyle.icon}
                                {statusStyle.label}
                              </span>
                            ) : (
                              formatDisplay(rawCell)
                            )}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        );
      }
      
      // Case 3: Special handling for Performance Indicators and other tables
      // This is for sections like 4.1 Performance Indicators shown in the screenshot
      else if (jsonData && typeof jsonData === 'object') {
        // Extract the first key as the title, assuming it's a proper table
        const tableTitle = Object.keys(jsonData)[0];
        const tableData = jsonData[tableTitle];

        // If we have an array of objects, render as a table
        if (Array.isArray(tableData)) {
          const firstItem = tableData[0] || {};
          const headers = Object.keys(firstItem);
          if (headers.length > 0) {
            const wrapStyle = { whiteSpace: 'normal', overflow: 'visible', textOverflow: 'clip', wordBreak: 'break-word', overflowWrap: 'anywhere' };
            return (
              <div className={classes.tableCard}>
                <div className={`${classes.tableTitle} ${typography.headingM}`}>{tableTitle}</div>
                <div className={classes.tableScroll} tabIndex={0} role="group" aria-label={`${tableTitle} table`}>
                  <table className={classes.mdTable} aria-label={`${tableTitle} data`}>
                    <thead>
                      <tr>
                        {headers.map((header, idx) => (
                          <th key={idx} className={classes.mdTh} style={{ textAlign: 'left' }} scope="col">
                            {header}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {tableData.map((row, rowIndex) => (
                        <tr key={rowIndex}>
                          {headers.map((header, cellIndex) => {
                            const rawCell = row[header] === undefined || row[header] === null ? '' : row[header];
                            const cellValue = String(rawCell);
                            const isLong = cellValue.length > 50;
                            const statusStyle = getStatusStyle(cellValue, classes);
                            
                            return (
                              <td key={cellIndex} className={classes.mdTd} style={{ textAlign: 'left', ...(isLong ? wrapStyle : {}) }}>
                                {statusStyle ? (
                                  <span className={`${classes.statusChip} ${statusStyle.class}`}>
                                    {statusStyle.icon}
                                    {statusStyle.label}
                                  </span>
                                ) : (
                                  formatDisplay(rawCell)
                                )}
                              </td>
                            );
                          })}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            );
          }
        }
      }
    } catch (error) {
      // Not a valid JSON or not our table structure, render as normal code block
      console.warn('Failed to parse JSON for table or invalid table structure:', error);
    }

    // Fallback to default code rendering or use a syntax highlighter if available
    // For simplicity, rendering as a preformatted code block here.
    return (
      <pre className={classes.mdPre}>
        <code className={className} {...props}>
          {children}
        </code>
      </pre>
    );
  }
};

const FilePreview = ({ selectedFile }) => {
  const classes = useStyles();
  const typography = useTypographyStyles();
  const fileTypeInfo = selectedFile ? getFileTypeInfo(selectedFile.name, classes) : null;
  const [originalContent, setOriginalContent] = useState('');

  // ... (rest of the code remains the same)
  useEffect(() => {
    // For processed files, use analysisContent; otherwise use content field
    if (selectedFile) {
      if (typeof selectedFile.analysisContent === 'string' && selectedFile.analysisContent.length > 0) {
        setOriginalContent(selectedFile.analysisContent);
      } else if (typeof selectedFile.content === 'string') {
        setOriginalContent(selectedFile.content);
      } else {
        setOriginalContent('');
      }
    } else {
      setOriginalContent('');
    }
  }, [selectedFile]);

  const isAnalysisView = !!selectedFile?.analysisContent;
  const hasMetrics = Array.isArray(selectedFile?.metricsData) && selectedFile.metricsData.length > 0;
  const hasParameters = Array.isArray(selectedFile?.parametersData) && selectedFile.parametersData.length > 0;

  const handleExportPDF = (file) => {
    if (!file?.name) return;
    // Determine the correct markdown blob name the backend expects
    // Priority: explicit analysis_file -> derived <base>_AI.md for non-MD -> original .md
    let mdName;
    if (file.analysis_file && typeof file.analysis_file === 'string') {
      mdName = file.analysis_file;
    } else if (!file.name.toLowerCase().endsWith('.md')) {
      // Preserve folder prefixes while switching extension and adding _AI
      mdName = file.name.replace(/\.[^.]+$/, '_AI.md');
    } else {
      mdName = file.name;
    }
    // Use the enhanced export endpoint under /api with the expected query param
    const url = `${API_BASE}/api/export-pdf-enhanced?blob_name=${encodeURIComponent(mdName)}`;
    window.open(url, '_blank', 'noopener,noreferrer');
  };

  return (
    <div className={classes.container}>
      <a href="#filepreview-content" className={classes.skipLink}>Skip to content</a>
      <div className={classes.headerBar}>
        <div className={`${classes.title} ${typography.headingL}`}>
          {isAnalysisView ? 'AI Analysis' : 'File Preview'}
        </div>
        {selectedFile && (
          <div className={classes.actionBar}>
            {selectedFile && selectedFile.name && (
              <Tooltip content="Export to PDF" relationship="label">
                <Button
                  appearance="subtle"
                  size="small"
                  icon={<DocumentPdf24Regular />}
                  aria-label="Export to PDF"
                  onClick={() => handleExportPDF(selectedFile)}
                />
              </Tooltip>
            )}
            <div className={classes.fileBadge} aria-label={isAnalysisView ? 'SAP Analysis' : `File type ${fileTypeInfo?.label || ''}`}>
              <span className={classes.badgeIcon}>
                {isAnalysisView ? (
                  <img src={sapLogo} alt="SAP Logo" style={{ height: 24, width: 24, objectFit: 'contain' }} />
                ) : (
                  fileTypeInfo?.icon || null
                )}
              </span>
              {!isAnalysisView && (
                <span className={`${classes.badgeLabel} ${typography.bodyS}`}>{fileTypeInfo?.label}</span>
              )}
            </div>
          </div>
        )}
      </div>

      <div
        className={`${classes.contentArea} ${isAnalysisView ? classes.analysisArea : classes.centerArea}`}
        id="filepreview-content"
        role="region"
        aria-label="File preview content"
        tabIndex={-1}
      >
        {selectedFile ? (
          isAnalysisView ? (
            <div className={`${classes.analysisInner} ${classes.previewTextRoot}`}>
              {selectedFile.analysisLoading ? (
                <div className={classes.skeletonContainer} role="status" aria-live="polite" aria-busy="true">
                  <ProgressBar thickness="small" />
                  <div className={classes.skeletonLine} style={{ width: '40%', height: 20 }} />
                  <div className={classes.skeletonLine} style={{ width: '95%' }} />
                  <div className={classes.skeletonLine} style={{ width: '85%' }} />
                  <div className={classes.skeletonBlock} />
                  <div className={classes.skeletonLine} style={{ width: '60%', height: 16 }} />
                  <div className={classes.skeletonBlock} style={{ height: 160 }} />
                </div>
              ) : (
                <>
                  {/* Analysis Content Section */}
                  <ReactMarkdown
                    key={selectedFile ? selectedFile.name : 'default-key'}
                    remarkPlugins={[remarkGfm]}
                    rehypePlugins={[rehypeRaw]}
                    components={{
                      ...(function () {
                        let currentHeaders = [];
                        let currentColIndex = 0;
                        const middleHeaders = new Set([
                          'issue id',
                          'area',
                          'severity',
                          // Recommendations table columns
                          'recommendation id',
                          'estimated effort',
                          'responsible area',
                          'linked issue id',
                        ]);
                        return {
                          table: ({ children }) => (
                            <div className={classes.tableScroll} tabIndex={0} role="group" aria-label="Markdown table">
                              <table className={classes.mdTable} aria-label="Markdown data table">{children}</table>
                            </div>
                          ),
                          thead: ({ children }) => {
                            currentHeaders = [];
                            return <thead>{children}</thead>;
                          },
                          th: ({ children }) => {
                            const text = String(children).replace(/\s+/g, ' ').trim();
                            currentHeaders.push(text);
                            return <th className={classes.mdTh} scope="col">{children}</th>;
                          },
                          tr: ({ children }) => {
                            currentColIndex = 0;
                            return <tr>{children}</tr>;
                          },
                          td: ({ children, ...props }) => {
                            const plain = String(children).replace(/\s+/g, ' ').trim();
                            const isLong = plain.length > 50;
                            const wrapStyle = isLong ? { whiteSpace: 'normal', overflow: 'visible', textOverflow: 'clip', wordBreak: 'break-word', overflowWrap: 'anywhere' } : {};
                            const statusStyle = getStatusStyle(plain, classes);
                            const headerName = (currentHeaders[currentColIndex] || '').toLowerCase().trim();
                            const shouldMiddle = middleHeaders.has(headerName);
                            const cell = (
                              <td
                                className={classes.mdTd}
                                title={plain}
                                style={{ ...(shouldMiddle ? { verticalAlign: 'middle' } : {}), ...wrapStyle }}
                                {...props}
                              >
                                {statusStyle ? (
                                  <span className={`${classes.statusChip} ${statusStyle.class}`}>
                                    {statusStyle.icon}
                                    {statusStyle.label}
                                  </span>
                                ) : (
                                  children
                                )}
                              </td>
                            );
                            currentColIndex += 1;
                            return cell;
                          },
                          tbody: ({ children }) => <tbody>{children}</tbody>,
                        };
                      })(),
                      code: JsonCodeBlockRenderer,
                      inlineCode: ({ children }) => {
                        // Special handling for risk assessment values that appear in backticks
                        const value = String(children).trim();
                        console.log('Found inline code value:', value);
                        
                        // Force match for well-known risk levels regardless of case
                        let forcedStyle = null;
                        const lowerValue = value.toLowerCase();
                        if (lowerValue === 'high') {
                          forcedStyle = `${classes.riskBase} ${classes.riskHigh}`;
                          return (
                            <span className={`${classes.statusChip} ${forcedStyle}`}>HIGH</span>
                          );
                        } else if (lowerValue === 'medium') {
                          forcedStyle = `${classes.riskBase} ${classes.riskMedium}`;
                          return (
                            <span className={`${classes.statusChip} ${forcedStyle}`}>MEDIUM</span>
                          );
                        } else if (lowerValue === 'low') {
                          forcedStyle = `${classes.riskBase} ${classes.riskLow}`;
                          return (
                            <span className={`${classes.statusChip} ${forcedStyle}`}>LOW</span>
                          );
                        }
                        
                        // Regular processing for other values
                        const statusStyle = getStatusStyle(value, classes);
                        if (statusStyle) {
                          return (
                            <span className={`${classes.statusChip} ${statusStyle.class}`}>
                              {statusStyle.icon}
                              {statusStyle.label}
                            </span>
                          );
                        }
                        
                        // Default rendering for other inline code
                        return <code>{children}</code>;
                      },
                      h1: ({ children }) => {
                        // Inject Analysis Period immediately after the title
                        let periodNode = null;
                        try {
                          const periodMatch = (selectedFile?.analysisContent || '').match(/\*\*Analysis Period:\*\*\s+([^\n]+)/i);
                          if (periodMatch && periodMatch[1]) {
                            const periodValue = periodMatch[1].trim();
                            periodNode = (
                              <p className={classes.mdP} style={{ marginTop: tokens.spacingVerticalS }}>
                                <strong>Analysis Period: </strong>
                                <span>{periodValue}</span>
                              </p>
                            );
                          }
                        } catch (e) {
                          // noop
                        }
                        return (
                          <>
                            <h1 className={classes.mdH1}>{children}</h1>
                            {periodNode}
                          </>
                        );
                      },
                      h2: ({ children }) => (
                        <h2 className={classes.mdH2}>{children}</h2>
                      ),
                      h3: ({ children }) => (
                        <h3 className={classes.mdH3}>{children}</h3>
                      ),
                      p: ({ children }) => {
                        // Check if this paragraph contains the Overall Risk Assessment text
                        const childStr = String(React.Children.toArray(children).map(c => 
                          typeof c === 'string' ? c : (c?.props?.children || '')).join(''));
                        // Suppress the original Analysis Period paragraph since we render it after H1
                        if (/\bAnalysis Period:\b/i.test(childStr)) {
                          return null;
                        }
                        
                        if (childStr.includes('Overall Risk Assessment:')) {
                          // Extract the risk value - it's likely after the colon and might be wrapped in backticks
                          const riskMatch = childStr.match(/Overall Risk Assessment:.*?([a-zA-Z]+)[`\s]*$/i);
                          if (riskMatch && riskMatch[1]) {
                            const riskValue = riskMatch[1].toLowerCase().trim();
                            let riskClass = '';
                            
                            // Apply styling based on risk level
                            if (riskValue === 'high') {
                              riskClass = classes.riskHigh;
                            } else if (riskValue === 'medium') {
                              riskClass = classes.riskMedium;
                            } else if (riskValue === 'low') {
                              riskClass = classes.riskLow;
                            }
                            
                            // Return paragraph with styled risk chip
                            if (riskClass) {
                              return (
                                <p className={classes.mdP}>
                                  <strong>Overall Risk Assessment: </strong>
                                  <span className={`${classes.riskBase} ${riskClass}`}>
                                    {riskValue.toUpperCase()}
                                  </span>
                                </p>
                              );
                            }
                          }
                        }
                        
                        // Default paragraph rendering
                        return <p className={classes.mdP}>{children}</p>;
                      },
                      ul: ({ children }) => (
                        <ul className={classes.mdUl}>{children}</ul>
                      ),
                      ol: ({ children }) => (
                        <ol className={classes.mdOl}>{children}</ol>
                      ),
                      li: ({ children }) => (
                        <li className={classes.mdLi}>{children}</li>
                      ),
                      strong: ({ children }) => (
                        <strong className={classes.mdStrong}>{children}</strong>
                      ),
                      em: ({ children }) => (
                        <em className={classes.mdEm}>{children}</em>
                      ),
                      blockquote: ({ children }) => (
                        <blockquote className={classes.mdBlockquote}>{children}</blockquote>
                      ),
                    }}
                  >
                    {selectedFile.analysisContent}
                  </ReactMarkdown>

                  {hasMetrics && (
                    <div className={classes.accordionSection}>
                      <FluentAccordion>
                        <AccordionItem value="metrics">
                          <AccordionHeader expandIcon={<ChevronDown24Regular />} className={classes.accordionHeader} aria-label="Key Metrics Summary">
                            <div style={{ display: 'flex', alignItems: 'center' }}>
                              <DataBarVertical24Regular style={{ marginRight: 12, color: '#1976d2' }} />
                              <span style={{ fontWeight: 500, color: '#1976d2' }}>Key Metrics Summary</span>
                            </div>
                          </AccordionHeader>
                          <AccordionPanel className={classes.accordionPanel}>
                            <div className={classes.panelInner}>
                              {/* <MetricsTable metricsData={metricsData} /> */}
                            </div>
                          </AccordionPanel>
                        </AccordionItem>
                      </FluentAccordion>
                    </div>
                  )}
                  
                  {/* Collapsible Parameters Section after metrics */}
                  {hasParameters && (
                    <div className={classes.accordionSection}>
                      <FluentAccordion>
                        <AccordionItem value="parameters">
                          <AccordionHeader expandIcon={<ChevronDown24Regular />} className={classes.accordionHeader} aria-label="Recommended Parameters">
                            <div style={{ display: 'flex', alignItems: 'center' }}>
                              <Settings24Regular style={{ marginRight: 12, color: '#2e7d32' }} />
                              <span style={{ fontWeight: 500, color: '#2e7d32' }}>Recommended Parameters</span>
                            </div>
                          </AccordionHeader>
                          <AccordionPanel className={classes.accordionPanel}>
                            <div className={classes.panelInner}>
                              {/* <ParametersTable parametersData={parametersData} /> */}
                            </div>
                          </AccordionPanel>
                        </AccordionItem>
                      </FluentAccordion>
                    </div>
                  )}
                </>
              )}
            </div>
          ) : (
            <div className={classes.placeholderContainer}> 
              {fileTypeInfo && fileTypeInfo.icon && React.cloneElement(fileTypeInfo.icon, { 
                style: { fontSize: 64, marginBottom: 8, opacity: 0.7 } 
              })}
              <div className={`${classes.placeholderTitle} ${typography.headingL}`} style={{ fontSize: tokens.fontSizeBase600 }}>
                {selectedFile.name}
              </div>
              <div className={`${classes.placeholderText} ${typography.bodyM}`} style={{ fontSize: tokens.fontSizeBase400 }}>
                Preview functionality will be added in a future update
              </div>
              <div className={classes.placeholderFrame}>
                <div className={`${classes.placeholderMuted} ${typography.bodyS}`}>
                  Content preview placeholder
                </div>
              </div>
            </div>
          )
        ) : (
          <div className={classes.placeholderContainer} role="status" aria-live="polite">
            <Document24Regular style={{ fontSize: 64, marginBottom: 8, opacity: 0.7 }} />
            <div className={`${classes.placeholderTitle} ${typography.headingL}`} style={{ fontSize: tokens.fontSizeBase600 }}>No File Selected</div>
            <div className={`${classes.placeholderText} ${typography.bodyM}`} style={{ fontSize: tokens.fontSizeBase400 }}>Select a file from the list to preview its contents</div>
          </div>
        )}
      </div>
      
      {/* Document Chat Component */}
      {selectedFile && (
        <DocumentChat 
          fileName={selectedFile.name}
          documentContent={originalContent}
        />
      )}
    </div>
  );
};

export default FilePreview;
