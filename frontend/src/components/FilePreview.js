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

// Formatting utilities (dates/numbers + truncation tooltip)
import { TruncatedText, formatDisplay } from '../utils/format';

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

// Styles for Fluent migration
const useStyles = makeStyles({
  container: {
    padding: '0px',
    backgroundColor: tokens.colorNeutralBackground1,
    borderRadius: tokens.borderRadiusMedium,
    height: '100%',
    width: '100%',
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden',
    border: `1px solid ${tokens.colorNeutralStroke1}`,
    minWidth: 0,
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
    paddingLeft: tokens.spacingHorizontalM,
    paddingRight: tokens.spacingHorizontalM,
    paddingTop: tokens.spacingVerticalS,
    paddingBottom: tokens.spacingVerticalS,
    borderBottom: `1px solid ${tokens.colorNeutralStroke1}`,
    display: 'flex',
    alignItems: 'center',
    backgroundColor: tokens.colorNeutralBackground2,
    gap: tokens.spacingHorizontalS,
    flexWrap: 'wrap',
    rowGap: tokens.spacingVerticalXS,
    '@media (max-width: 600px)': {
      flexDirection: 'column',
      alignItems: 'stretch',
      gap: tokens.spacingVerticalXS,
    },
  },
  title: {
    fontWeight: tokens.fontWeightSemibold,
    color: tokens.colorNeutralForeground1,
    fontSize: tokens.fontSizeBase500,
    lineHeight: '24px',
    flexGrow: 1,
    minWidth: 0,
    overflowWrap: 'anywhere',
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
    backgroundColor: tokens.colorNeutralBackground2,
    transition: 'background-color 150ms ease, border-color 150ms ease',
    selectors: {
      '&:hover': { backgroundColor: tokens.colorSubtleBackgroundHover },
      '&:focus-visible': { outline: `${tokens.strokeWidthThick} solid ${tokens.colorBrandStroke1}`, outlineOffset: 2 },
    },
  },
  accordionPanel: {
    padding: tokens.spacingHorizontalL,
  },
  fileBadge: {
    display: 'inline-flex',
    alignItems: 'center',
    borderRadius: '6px',
    padding: `${tokens.spacingVerticalXXS} ${tokens.spacingHorizontalS}`,
    border: `1px solid ${tokens.colorNeutralStroke1}`,
    backgroundColor: tokens.colorNeutralBackground1,
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
    marginTop: tokens.spacingVerticalXL,
    marginBottom: tokens.spacingVerticalM,
    fontWeight: tokens.fontWeightSemibold,
    fontSize: tokens.fontSizeBase700,
    letterSpacing: '-0.02em',
    color: tokens.colorNeutralForeground1,
  },
  mdH2: {
    marginTop: tokens.spacingVerticalL,
    marginBottom: tokens.spacingVerticalS,
    fontWeight: tokens.fontWeightSemibold,
    fontSize: tokens.fontSizeBase600,
    letterSpacing: '-0.01em',
    color: tokens.colorNeutralForeground1,
  },
  mdH3: {
    marginTop: tokens.spacingVerticalM,
    marginBottom: tokens.spacingVerticalXS,
    fontWeight: tokens.fontWeightSemibold,
    fontSize: tokens.fontSizeBase500,
    color: tokens.colorNeutralForeground1,
  },
  mdP: {
    marginBottom: tokens.spacingVerticalS,
    fontSize: tokens.fontSizeBase200,
    lineHeight: '1.7',
    color: tokens.colorNeutralForeground2,
  },
  mdUl: {
    marginBottom: tokens.spacingVerticalM,
    paddingLeft: tokens.spacingHorizontalXL,
  },
  mdOl: {
    marginBottom: tokens.spacingVerticalM,
    paddingLeft: tokens.spacingHorizontalXL,
  },
  mdLi: {
    marginBottom: tokens.spacingVerticalXXS,
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
    marginTop: tokens.spacingVerticalM,
    marginBottom: tokens.spacingVerticalM,
    borderRadius: tokens.borderRadiusMedium,
    overflow: 'hidden',
    backgroundColor: tokens.colorNeutralBackground1,
    border: `1px solid ${tokens.colorNeutralStroke1}`,
  },
  tableTitle: {
    padding: tokens.spacingHorizontalM,
    backgroundColor: tokens.colorNeutralBackground2,
    color: tokens.colorNeutralForeground1,
    fontWeight: tokens.fontWeightSemibold,
    fontSize: tokens.fontSizeBase500,
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
    selectors: {
      'tbody tr:nth-child(even)': {
        backgroundColor: tokens.colorNeutralBackground2,
      },
    },
  },
  mdTh: {
    textAlign: 'left',
    padding: tokens.spacingHorizontalM,
    fontWeight: tokens.fontWeightSemibold,
    fontSize: tokens.fontSizeBase200,
    color: tokens.colorNeutralForeground1,
    borderBottom: `1px solid ${tokens.colorNeutralStroke1}`,
    backgroundColor: tokens.colorNeutralBackground2,
  },
  mdTd: {
    padding: `${tokens.spacingVerticalS} ${tokens.spacingHorizontalM}`,
    fontSize: tokens.fontSizeBase200,
    color: tokens.colorNeutralForeground2,
    borderBottom: `1px solid ${tokens.colorNeutralStroke1}`,
    verticalAlign: 'top',
  },
  contentArea: {
    flex: 1,
    padding: tokens.spacingHorizontalL,
    backgroundColor: tokens.colorNeutralBackground1,
    overflowY: 'auto',
    display: 'flex',
    alignItems: 'stretch',
    justifyContent: 'flex-start',
    // Subtle custom scrollbar (Firefox + WebKit)
    scrollbarWidth: 'thin',
    scrollbarColor: `${tokens.colorNeutralStroke1} ${tokens.colorNeutralBackground1}`,
    msOverflowStyle: 'auto',
    selectors: {
      '&::-webkit-scrollbar': { width: '6px' },
      '&::-webkit-scrollbar-track': { background: tokens.colorNeutralBackground1 },
      '&::-webkit-scrollbar-thumb': { background: tokens.colorNeutralStroke1, borderRadius: '3px' },
      '&::-webkit-scrollbar-thumb:hover': { background: tokens.colorNeutralStroke1Hover },
    },
    '@media (max-width: 600px)': {
      padding: tokens.spacingHorizontalM,
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
  },
  placeholderTitle: {
    fontWeight: tokens.fontWeightSemibold,
    color: tokens.colorNeutralForeground2,
    fontSize: tokens.fontSizeBase500,
    marginBottom: tokens.spacingVerticalXS,
  },
  placeholderText: {
    color: tokens.colorNeutralForeground3,
    fontSize: tokens.fontSizeBase300,
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
    fontSize: tokens.fontSizeBase200,
  },
  // Lightweight skeleton styles (no animation for simplicity)
  skeletonContainer: {
    display: 'flex',
    flexDirection: 'column',
    rowGap: tokens.spacingVerticalS,
  },
  skeletonLine: {
    width: '100%',
    height: '12px',
    borderRadius: tokens.borderRadiusSmall,
    backgroundColor: tokens.colorNeutralBackground3,
  },
  skeletonBlock: {
    width: '100%',
    height: '120px',
    borderRadius: tokens.borderRadiusMedium,
    backgroundColor: tokens.colorNeutralBackground3,
    border: `1px solid ${tokens.colorNeutralStroke2}`,
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
            <div className={`${classes.tableTitle} ${typography.headingL}`}>{jsonData.tableTitle}</div>
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
                      <td className={classes.mdTd} style={{ textAlign: 'left' }}>{formatDisplay(item.value)}</td>
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
        return (
          <div className={classes.tableCard}>
            <div className={`${classes.tableTitle} ${typography.headingL}`}>{jsonData.tableTitle}</div>
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
                        const extraStyle = cellValue.length > 50 ? { maxWidth: '300px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' } : {};
                        return (
                          <td key={cellIndex} className={classes.mdTd} style={{ textAlign: 'left', ...extraStyle }}>
                            {cellValue.length > 50 ? (
                              <TruncatedText text={formatDisplay(rawCell)} maxWidth="300px" />
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
            return (
              <div className={classes.tableCard}>
                <div className={`${classes.tableTitle} ${typography.headingL}`}>{tableTitle}</div>
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
                            const extraStyle = cellValue.length > 50 ? { maxWidth: '300px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' } : {};
                            return (
                              <td key={cellIndex} className={classes.mdTd} style={{ textAlign: 'left', ...extraStyle }}>
                                {cellValue.length > 50 ? (
                                  <TruncatedText text={formatDisplay(rawCell)} maxWidth="300px" />
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
    // Minimal content wiring; backend fetch can be added later
    if (selectedFile && typeof selectedFile.content === 'string') {
      setOriginalContent(selectedFile.content);
    } else if (!selectedFile) {
      setOriginalContent('');
    }
  }, [selectedFile]);

  const isAnalysisView = !!selectedFile?.analysisContent;
  const hasMetrics = Array.isArray(selectedFile?.metricsData) && selectedFile.metricsData.length > 0;
  const hasParameters = Array.isArray(selectedFile?.parametersData) && selectedFile.parametersData.length > 0;

  const handleExportPDF = (file) => {
    if (!file?.name) return;
    const url = `${API_BASE}/export/pdf?file=${encodeURIComponent(file.name)}`;
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
            <div className={classes.analysisInner}>
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
                      table: ({ children }) => (
                        <div className={classes.tableScroll} tabIndex={0} role="group" aria-label="Markdown table">
                          <table className={classes.mdTable} aria-label="Markdown data table">{children}</table>
                        </div>
                      ),
                      thead: ({ children }) => <thead>{children}</thead>,
                      th: ({ children }) => <th className={classes.mdTh} scope="col">{children}</th>,
                      td: ({ children, ...props }) => {
                        const plain = String(children).replace(/\s+/g, ' ').trim();
                        return (
                          <td
                            className={classes.mdTd}
                            title={plain}
                            {...props}
                          >
                            <span style={{ display: 'inline-block', maxWidth: 360, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                              {children}
                            </span>
                          </td>
                        );
                      },
                      tbody: ({ children }) => <tbody>{children}</tbody>,
                      code: JsonCodeBlockRenderer,
                      h1: ({ children }) => (
                        <h1 className={classes.mdH1}>{children}</h1>
                      ),
                      h2: ({ children }) => (
                        <h2 className={classes.mdH2}>{children}</h2>
                      ),
                      h3: ({ children }) => (
                        <h3 className={classes.mdH3}>{children}</h3>
                      ),
                      p: ({ children }) => (
                        <p className={classes.mdP}>{children}</p>
                      ),
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
                      a: ({ children, href }) => (
                        <a
                          href={href}
                          target="_blank"
                          rel="noopener noreferrer"
                          className={classes.mdLink}
                        >
                          {children}
                        </a>
                      ),
                    }}
                  >
                    {selectedFile.analysisContent}
                  </ReactMarkdown>
                  
                  {/* Collapsible Metrics Section at the end */}
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
                style: { fontSize: 48, marginBottom: 8, opacity: 0.7 } 
              })}
              <div className={`${classes.placeholderTitle} ${typography.headingL}`}>
                {selectedFile.name}
              </div>
              <div className={`${classes.placeholderText} ${typography.bodyM}`}>
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
            <Document24Regular style={{ fontSize: 48, marginBottom: 8, opacity: 0.7 }} />
            <div className={`${classes.placeholderTitle} ${typography.headingL}`}>No File Selected</div>
            <div className={`${classes.placeholderText} ${typography.bodyM}`}>Select a file from the list to preview its contents</div>
            <div className={classes.placeholderFrame}>
              <div className={`${classes.placeholderMuted} ${typography.bodyS}`}>Content preview will show here.</div>
            </div>
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
