import React, { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  Chat24Regular,
  Send24Regular,
  Dismiss24Regular,
  Bot24Regular,
  Person24Regular,
} from '@fluentui/react-icons';
import { Button, Textarea, Spinner, Field, makeStyles, shorthands, tokens } from '@fluentui/react-components';
import { apiUrl } from '../config';

const useStyles = makeStyles({
  chatContainer: {
    position: 'fixed',
    bottom: '20px',
    right: '20px',
    width: '550px',
    height: '600px',
    zIndex: 1300,
    display: 'flex',
    flexDirection: 'column',
    backgroundColor: tokens.colorNeutralBackground1,
    boxShadow: tokens.shadow64,
    ...shorthands.borderRadius('16px'),
    overflow: 'hidden',
    ...shorthands.border('1px', 'solid', tokens.colorNeutralStroke1),
    '::before': {
      content: '""',
      position: 'absolute',
      top: 0,
      left: 0,
      right: 0,
      height: '3px',
      backgroundImage: 'linear-gradient(90deg, #4285F4, #34A853, #FBBC05, #EA4335)',
      zIndex: 1301,
    },
  },
  header: {
    ...shorthands.padding('10px', '16px'),
    ...shorthands.borderBottom('1px', 'solid', tokens.colorNeutralStroke1),
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: tokens.colorNeutralBackground1,
    color: tokens.colorNeutralForeground1,
    position: 'relative',
    zIndex: 2,
  },
  headerLeft: {
    display: 'flex',
    alignItems: 'center',
    columnGap: '8px',
  },
  headerTitle: {
    fontSize: '0.9rem',
    fontWeight: 600,
  },
  messages: {
    flexGrow: 1,
    overflowY: 'auto',
    padding: '8px 16px',
    display: 'flex',
    flexDirection: 'column',
    rowGap: '4px',
    backgroundColor: tokens.colorNeutralBackground2,
    scrollbarWidth: 'thin',
    msOverflowStyle: 'auto',
  },
  emptyIcon: {
    width: '48px',
    height: '48px',
    opacity: 0.5,
    marginBottom: '8px',
  },
  messageRow: {
    display: 'flex',
    alignItems: 'flex-start',
    columnGap: '6px',
    marginBottom: '4px',
  },
  messageRowUser: {
    flexDirection: 'row-reverse',
  },
  avatar: {
    width: '26px',
    height: '26px',
    ...shorthands.borderRadius('50%'),
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: tokens.colorNeutralBackground4,
    color: tokens.colorNeutralForeground2,
  },
  avatarUser: {
    backgroundColor: tokens.colorBrandBackground,
    color: tokens.colorNeutralForegroundOnBrand,
  },
  avatarError: {
    backgroundColor: tokens.colorPaletteRedBackground2,
    color: tokens.colorPaletteRedForeground2,
  },
  bubble: {
    padding: '8px 12px',
    maxWidth: '90%',
    wordWrap: 'break-word',
    boxShadow: tokens.shadow4,
    fontSize: '0.82rem',
    lineHeight: 1.35,
    ...shorthands.border('1px', 'solid', tokens.colorNeutralStroke1),
    ...shorthands.borderRadius('18px'),
    backgroundColor: tokens.colorNeutralBackground1,
    color: tokens.colorNeutralForeground1,
  },
  bubbleUser: {
    backgroundColor: tokens.colorBrandBackground,
    color: tokens.colorNeutralForegroundOnBrand,
    borderStyle: 'none',
  },
  bubbleError: {
    backgroundColor: tokens.colorPaletteRedBackground2,
    color: tokens.colorPaletteRedForeground2,
    ...shorthands.border('1px', 'solid', tokens.colorPaletteRedBorderActive),
  },
  inputContainer: {
    ...shorthands.padding('10px'),
    ...shorthands.borderTop('1px', 'solid', tokens.colorNeutralStroke1),
    display: 'flex',
    columnGap: '8px',
    alignItems: 'flex-end',
    backgroundColor: tokens.colorNeutralBackground2,
  },
  inputArea: {
    flexGrow: 1,
  },
  controlFullWidth: {
    width: '100%',
  },
});

const DocumentChat = ({ fileName, documentContent }) => {
  const [expanded, setExpanded] = useState(false);
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [loading, setLoading] = useState(false);
  const [contentStatus, setContentStatus] = useState('unknown');
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Check document content and reset chat when document changes
  useEffect(() => {
    setMessages([]);
    setInputValue('');
    
    // Check document content status
    if (!documentContent) {
      setContentStatus('missing');
    } else if (documentContent.length < 100) {
      setContentStatus('minimal');
      console.warn(`Very short document content (${documentContent.length} chars) for ${fileName}`); 
    } else if (documentContent.includes('Could not load content')) {
      setContentStatus('error');
      console.error(`Error loading content for ${fileName}`); 
    } else {
      setContentStatus('available');
      console.log(`Document content available for ${fileName}: ${documentContent.length} chars`);
    }
  }, [fileName, documentContent]);

  // API base is centralized in src/config.js

const handleSendMessage = async () => {
    if (!inputValue.trim() || loading) return;

    const userMessage = { text: inputValue, isUser: true, timestamp: new Date() };
    setMessages(prev => [...prev, userMessage]);
    setInputValue('');
    setLoading(true);

    try {
      // Simple approach - use relative URL with the proxy
      const requestBody = {
        message: inputValue,
        fileName: fileName,
        documentContent: documentContent || 'No document content available',
        chatHistory: messages.map(m => ({ text: m.text, isUser: m.isUser }))
      };
      
      console.log(`Sending chat request for ${fileName} with content length: ${documentContent?.length || 0}`);
      
      const response = await fetch(apiUrl('/api/chat'), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestBody),
      });
      
      if (!response.ok) {
        throw new Error(`Server error: ${response.status} ${response.statusText}`);
      }
      
      const data = await response.json();
      
      // Check if the response contains an error
      if (data.error) {
        console.error('Error from chat API:', data.response);
        const errorMessage = { 
          text: data.response || 'An error occurred while processing your request.', 
          isUser: false, 
          timestamp: new Date(),
          isError: true
        };
        setMessages(prev => [...prev, errorMessage]);
        return;
      }
      
      const botMessage = { 
        text: data.response, 
        isUser: false, 
        timestamp: new Date() 
      };
      setMessages(prev => [...prev, botMessage]);
    } catch (error) {
      console.error('Chat error:', error);
      const errorMessage = { 
        text: `Error: ${error.message || 'An unexpected error occurred. Please try again.'}`, 
        isUser: false, 
        timestamp: new Date(),
        isError: true
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      handleSendMessage();
    }
  };

  const classes = useStyles();

  if (!expanded) {
    return (
      <Button
        aria-label="chat"
        onClick={() => setExpanded(true)}
        icon={<Chat24Regular />}
        shape="circular"
        appearance="primary"
        style={{ position: 'fixed', bottom: 20, right: 20, zIndex: 1300 }}
      />
    );
  }

  return (
    <div className={classes.chatContainer} role="dialog" aria-label="Document Assistant chat">
      <div className={classes.header}>
        <div className={classes.headerLeft}>
          <Bot24Regular />
          <div className={classes.headerTitle}>Document Assistant</div>
        </div>
        <Button
          aria-label="Close chat"
          onClick={() => setExpanded(false)}
          icon={<Dismiss24Regular style={{ width: 20, height: 20 }} />}
          appearance="subtle"
          shape="circular"
        />
      </div>

      <div className={classes.messages}>
        {messages.length === 0 && (
          <div style={{ textAlign: 'center', padding: '32px 0', color: tokens.colorNeutralForeground3 }}>
            <Bot24Regular className={classes.emptyIcon} />
            {contentStatus === 'available' ? (
              <div style={{ fontSize: '0.9rem' }}>Ask me anything about this SAP EWA report!</div>
            ) : contentStatus === 'missing' || contentStatus === 'minimal' ? (
              <div>
                <div style={{ marginBottom: 4, color: tokens.colorPaletteRedForeground1, fontSize: '0.9rem' }}>
                  Document content is limited or missing.
                </div>
                <div style={{ fontSize: '0.8rem' }}>
                  Please ensure the document has been processed first by clicking the "Process file" button.
                </div>
              </div>
            ) : contentStatus === 'error' ? (
              <div>
                <div style={{ marginBottom: 4, color: tokens.colorPaletteRedForeground1, fontSize: '0.9rem' }}>
                  Error loading document content.
                </div>
                <div style={{ fontSize: '0.8rem' }}>
                  Please try reprocessing the document or check server logs.
                </div>
              </div>
            ) : (
              <div style={{ fontSize: '0.9rem' }}>Ask me anything about this document!</div>
            )}
          </div>
        )}
        
        {messages.map((message, index) => (
          <div
            key={index}
            className={`${classes.messageRow} ${message.isUser ? classes.messageRowUser : ''}`}
          >
            <div
              className={`${classes.avatar} ${message.isUser ? classes.avatarUser : ''} ${message.isError ? classes.avatarError : ''}`}
              aria-hidden="true"
            >
              {message.isUser ? (
                <Person24Regular style={{ width: 16, height: 16 }} />
              ) : (
                <Bot24Regular style={{ width: 16, height: 16 }} />
              )}
            </div>
            <div
              className={`${classes.bubble} ${message.isUser ? classes.bubbleUser : ''} ${message.isError ? classes.bubbleError : ''}`}
              role="group"
              aria-label={message.isUser ? 'User message' : message.isError ? 'Error message' : 'Assistant message'}
            >
              {message.isUser ? (
                <div style={{ whiteSpace: 'pre-wrap', fontSize: '0.85rem', lineHeight: 1.4 }}>
                  {message.text}
                </div>
              ) : (
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {message.text}
                </ReactMarkdown>
              )}
            </div>
          </div>
        ))}
        
        {loading && (
          <div className={classes.messageRow}>
            <div className={classes.avatar} aria-hidden="true">
              <Bot24Regular style={{ width: 16, height: 16 }} />
            </div>
            <div className={classes.bubble}>
              <Spinner label="Thinking..." />
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className={classes.inputContainer}>
        <Field label="Message" hint="Press Enter to send" className={classes.inputArea}>
          <Textarea
            className={classes.controlFullWidth}
            placeholder="Ask about this document..."
            value={inputValue}
            onChange={(e, data) => setInputValue(data.value)}
            onKeyDown={handleKeyPress}
            disabled={loading}
            resize="none"
          />
        </Field>
        <Button
          aria-label="Send message"
          onClick={handleSendMessage}
          disabled={!inputValue.trim() || loading}
          icon={<Send24Regular style={{ width: 16, height: 16 }} />}
          appearance="primary"
          shape="circular"
        />
      </div>
    </div>
  );
};

export default DocumentChat;
