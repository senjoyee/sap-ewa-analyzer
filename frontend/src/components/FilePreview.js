import React, { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import rehypeRaw from 'rehype-raw';
import remarkGfm from 'remark-gfm';
import { makeStyles } from '@griffel/react';
import { tokens, Button, Tooltip, Accordion as FluentAccordion, AccordionItem, AccordionHeader, AccordionPanel } from '@fluentui/react-components';
import { DocumentPdf24Regular, ChevronDown24Regular, DataBarVertical24Regular, Settings24Regular } from '@fluentui/react-icons';
 
 
import { Image24Regular, Document24Regular, TextDescription24Regular } from '@fluentui/react-icons';
 
 

// Import our custom table components
// import MetricsTable from './MetricsTable';
// import ParametersTable from './ParametersTable';
import DocumentChat from './DocumentChat';

// Import the SAP logo
import sapLogo from '../logo/sap-3.svg';

// Helper function to get appropriate file type label and icon
const API_BASE = 'http://localhost:8001';
const getFileTypeInfo = (fileName) => {
  if (!fileName || typeof fileName !== 'string') {
    return { icon: <Document24Regular />, label: 'UNKNOWN', color: 'default' };
  }
  
  // Extract extension safely
  let extension = '';
  if (fileName.includes('.')) {
    extension = fileName.split('.').pop().toLowerCase();
  }
  
  switch(extension) {
    case 'pdf':
      return { 
        icon: <DocumentPdf24Regular style={{ color: '#F44336' }} />, 
        label: 'PDF',
        color: 'error' 
      };
    case 'jpg':
    case 'jpeg':
    case 'png':
    case 'gif':
    case 'bmp':
      return { 
        icon: <Image24Regular style={{ color: '#29B6F6' }} />, 
        label: 'IMAGE',
        color: 'info' 
      };
    case 'doc':
    case 'docx':
      return { 
        icon: <Document24Regular style={{ color: '#90CAF9' }} />, 
        label: 'DOCUMENT',
        color: 'primary' 
      };
    case 'txt':
      return { 
        icon: <TextDescription24Regular style={{ color: '#CE93D8' }} />, 
        label: 'TEXT',
        color: 'secondary' 
      };
    default:
      return { 
        icon: <Document24Regular style={{ color: '#9E9E9E' }} />, 
        label: extension ? extension.toUpperCase() : 'FILE',
        color: 'default' 
      };
  }
};

// Styles for Fluent migration
const useStyles = makeStyles({
  container: {
    padding: '0px',
    backgroundColor: tokens.colorNeutralBackground1,
    borderRadius: '8px',
    height: '100%',
    width: '100%',
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden',
    border: `1px solid ${tokens.colorNeutralStroke1}`,
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
  },
  title: {
    fontWeight: tokens.fontWeightSemibold,
    color: tokens.colorNeutralForeground1,
    fontSize: tokens.fontSizeBase500,
    lineHeight: '24px',
    flexGrow: 1,
  },
  actionBar: {
    display: 'flex',
    alignItems: 'center',
    gap: tokens.spacingHorizontalXS,
  },
  accordionSection: {
    marginTop: tokens.spacingVerticalL,
    marginBottom: tokens.spacingVerticalL,
  },
  accordionHeader: {
    backgroundColor: tokens.colorNeutralBackground2,
  },
  accordionPanel: {
    padding: tokens.spacingHorizontalL,
  },
  fileBadge: {
    display: 'inline-flex',
    alignItems: 'center',
    borderRadius: '6px',
    padding: '4px 8px',
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
    fontSize: '1.75rem',
    letterSpacing: '-0.02em',
    color: tokens.colorNeutralForeground1,
  },
  mdH2: {
    marginTop: tokens.spacingVerticalL,
    marginBottom: tokens.spacingVerticalS,
    fontWeight: tokens.fontWeightSemibold,
    fontSize: '1.375rem',
    letterSpacing: '-0.01em',
    color: tokens.colorNeutralForeground1,
  },
  mdH3: {
    marginTop: tokens.spacingVerticalM,
    marginBottom: tokens.spacingVerticalXS,
    fontWeight: tokens.fontWeightSemibold,
    fontSize: '1.125rem',
    color: tokens.colorNeutralForeground1,
  },
  mdP: {
    marginBottom: tokens.spacingVerticalS,
    fontSize: '0.85rem',
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
    fontSize: '0.85rem',
  },
  mdLink: {
    color: '#2563eb',
    textDecoration: 'underline',
    fontWeight: 500,
  },
  mdPre: {
    padding: tokens.spacingHorizontalS,
    marginTop: tokens.spacingVerticalXS,
    marginBottom: tokens.spacingVerticalXS,
    backgroundColor: tokens.colorNeutralBackground3,
    borderRadius: tokens.borderRadiusMedium,
    overflowX: 'auto',
    fontSize: '0.875rem',
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
    ':focus-visible': {
      outline: `2px solid ${tokens.colorBrandStroke1}`,
      outlineOffset: '2px',
    },
  },
  mdTable: {
    width: '100%',
    borderCollapse: 'collapse',
    tableLayout: 'auto',
  },
  mdTh: {
    textAlign: 'left',
    padding: '12px',
    fontWeight: tokens.fontWeightSemibold,
    fontSize: '0.875rem',
    color: tokens.colorNeutralForeground1,
    borderBottom: `1px solid ${tokens.colorNeutralStroke1}`,
    backgroundColor: tokens.colorNeutralBackground2,
  },
  mdTd: {
    padding: '10px 12px',
    fontSize: '0.8125rem',
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
});

const JsonCodeBlockRenderer = ({ node, inline, className, children, ...props }) => {
  const classes = useStyles();
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
            <div className={classes.tableTitle}>{jsonData.tableTitle}</div>
            <div className={classes.tableScroll} tabIndex={0} role="group" aria-label={`${jsonData.tableTitle} table`}>
              <table className={classes.mdTable} aria-label={`${jsonData.tableTitle} data`}>
                <thead>
                  <tr>
                    <th className={classes.mdTh} style={{ width: '40%' }} scope="col">Parameter</th>
                    <th className={classes.mdTh} style={{ width: '60%' }} scope="col">Value</th>
                  </tr>
                </thead>
                <tbody>
                  {jsonData.items.map((item, index) => {
                    const isLongText = item.value.length > 20 && /[a-zA-Z]/.test(item.value);
                    const isNumericOrShort = !isLongText && (/^[\d.,\s%]+$/.test(item.value) || item.value.length < 10);
                    return (
                      <tr key={index}>
                        <td className={classes.mdTd} style={{ fontWeight: 500 }}>{item.parameter}</td>
                        <td className={classes.mdTd} style={{ textAlign: isNumericOrShort ? 'center' : 'left' }}>{item.value}</td>
                      </tr>
                    );
                  })}
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
            <div className={classes.tableTitle}>{jsonData.tableTitle}</div>
            <div className={classes.tableScroll} tabIndex={0} role="group" aria-label={`${jsonData.tableTitle} table`}>
              <table className={classes.mdTable} aria-label={`${jsonData.tableTitle} data`}>
                <thead>
                  <tr>
                    {jsonData.headers.map((header, index) => {
                      const hasLongTextInColumn = jsonData.rows.some(row => {
                        const val = String(row[header] === undefined || row[header] === null ? '' : row[header]);
                        return val.length > 20 && /[a-zA-Z]/.test(val);
                      });
                      const isNumericHeader = !hasLongTextInColumn && (
                        header.toLowerCase().includes('count') || 
                        header.toLowerCase().includes('value') ||
                        header.toLowerCase().includes('qty') ||
                        header.toLowerCase().includes('mhz') ||
                        header.toLowerCase().includes('cpus')
                      );
                      return (
                        <th key={index} className={classes.mdTh} style={{ textAlign: isNumericHeader ? 'center' : 'left' }} scope="col">
                          {header.charAt(0).toUpperCase() + header.slice(1).replace(/_/g, ' ')}
                        </th>
                      );
                    })}
                  </tr>
                </thead>
                <tbody>
                  {jsonData.rows.map((row, rowIndex) => (
                    <tr key={rowIndex}>
                      {jsonData.headers.map((header, cellIndex) => {
                        const cellValue = String(row[header] === undefined || row[header] === null ? '' : row[header]);
                        const hasLongTextInColumn = jsonData.rows.some(r => {
                          const val = String(r[header] === undefined || r[header] === null ? '' : r[header]);
                          return val.length > 20 && /[a-zA-Z]/.test(val);
                        });
                        const isNumeric = !hasLongTextInColumn && (
                          /^[\d.,\s%]+$/.test(cellValue) || 
                          header.toLowerCase().includes('count') || 
                          header.toLowerCase().includes('value') ||
                          header.toLowerCase().includes('qty') ||
                          header.toLowerCase().includes('mhz') ||
                          header.toLowerCase().includes('cpus')
                        );
                        const extraStyle = cellValue.length > 50 ? { maxWidth: '300px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' } : {};
                        return (
                          <td key={cellIndex} className={classes.mdTd} style={{ textAlign: isNumeric ? 'center' : 'left', ...extraStyle }}>
                            {cellValue}
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
                <div className={classes.tableTitle}>{tableTitle}</div>
                <div className={classes.tableScroll} tabIndex={0} role="group" aria-label={`${tableTitle} table`}>
                  <table className={classes.mdTable} aria-label={`${tableTitle} data`}>
                    <thead>
                      <tr>
                        {headers.map((header, idx) => {
                          const hasLongTextInColumn = tableData.some(row => {
                            const val = String(row[header] === undefined || row[header] === null ? '' : row[header]);
                            return val.length > 20 && /[a-zA-Z]/.test(val);
                          });
                          const isNumericHeader = !hasLongTextInColumn && (
                            header.toLowerCase().includes('count') || 
                            header.toLowerCase().includes('value') ||
                            header.toLowerCase().includes('qty') ||
                            header.toLowerCase().includes('mhz') ||
                            header.toLowerCase().includes('cpus')
                          );
                          return (
                            <th key={idx} className={classes.mdTh} style={{ textAlign: isNumericHeader ? 'center' : 'left' }} scope="col">
                              {header}
                            </th>
                          );
                        })}
                      </tr>
                    </thead>
                    <tbody>
                      {tableData.map((row, rowIndex) => (
                        <tr key={rowIndex}>
                          {headers.map((header, cellIndex) => {
                            const cellValue = String(row[header] === undefined || row[header] === null ? '' : row[header]);
                            const hasLongTextInColumn = tableData.some(r => {
                              const val = String(r[header] === undefined || r[header] === null ? '' : r[header]);
                              return val.length > 20 && /[a-zA-Z]/.test(val);
                            });
                            const isNumeric = !hasLongTextInColumn && (
                              /^[\d.,\s%]+$/.test(cellValue) || 
                              header.toLowerCase().includes('count') || 
                              header.toLowerCase().includes('value') ||
                              header.toLowerCase().includes('qty') ||
                              header.toLowerCase().includes('mhz') ||
                              header.toLowerCase().includes('cpus')
                            );
                            const extraStyle = cellValue.length > 50 ? { maxWidth: '300px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' } : {};
                            return (
                              <td key={cellIndex} className={classes.mdTd} style={{ textAlign: isNumeric ? 'center' : 'left', ...extraStyle }}>
                                {cellValue}
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
  const fileTypeInfo = selectedFile ? getFileTypeInfo(selectedFile.name) : null;
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

  const classes = useStyles();
  return (
    <div className={classes.container}>
      <div className={classes.headerBar}>
        <div className={classes.title}>
          {isAnalysisView ? 'AI Analysis' : 'File Preview'}
        </div>
        {selectedFile && (
          <div className={classes.actionBar}>
            {selectedFile && selectedFile.name && (
              <Tooltip content="Export to PDF" relationship="label">
                <Button
                  appearance="transparent"
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
                <span className={classes.badgeLabel}>{fileTypeInfo?.label}</span>
              )}
            </div>
          </div>
        )}
      </div>

      <div className={`${classes.contentArea} ${isAnalysisView ? classes.analysisArea : classes.centerArea}`}>
        {selectedFile ? (
          isAnalysisView ? (
            <div className={classes.analysisInner}>
              {/* Main Analysis Content - We'll add metrics at the end */}
              
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
                  td: ({ children }) => <td className={classes.mdTd}>{children}</td>,
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
              
              {/* Error display if metrics failed to load */}
              {/* No metrics error UI: setError is unused; keeping UI minimal */}
            </div>
          ) : (
            <div className={classes.placeholderContainer}> 
              {fileTypeInfo && fileTypeInfo.icon && React.cloneElement(fileTypeInfo.icon, { 
                style: { fontSize: 48, marginBottom: 8, opacity: 0.7 } 
              })}
              <div className={classes.placeholderTitle}>
                {selectedFile.name}
              </div>
              <div className={classes.placeholderText}>
                Preview functionality will be added in a future update
              </div>
              <div className={classes.placeholderFrame}>
                <div className={classes.placeholderMuted}>
                  Content preview placeholder
                </div>
              </div>
            </div>
          )
        ) : (
          <div className={classes.noFileSelected} role="status" aria-live="polite">
            <Document24Regular style={{ fontSize: 64, color: '#9e9e9e', marginBottom: 8 }} />
            <div className={classes.noFileTitle}>
              No File Selected
            </div>
            <div className={classes.noFileText}>
              Select a file from the list to preview its contents
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
