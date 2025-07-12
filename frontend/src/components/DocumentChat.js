import React, { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  Box,
  Paper,
  IconButton,
  TextField,
  Typography,
  List,
  ListItem,
  ListItemText,
  CircularProgress,
  Collapse,
  Fab,
  Avatar,
  Divider
} from '@mui/material';
import {
  Chat as ChatIcon,
  Send as SendIcon,
  Close as CloseIcon,
  SmartToy as BotIcon,
  Person as PersonIcon
} from '@mui/icons-material';
import { styled } from '@mui/material/styles';

const ChatContainer = styled(Paper)(({ theme, expanded }) => ({
  position: 'fixed',
  bottom: 20,
  right: 20,
  width: expanded ? 550 : 'auto',
  height: expanded ? 600 : 'auto',
  zIndex: 1300,
  transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
  display: 'flex',
  flexDirection: 'column',
  backgroundColor: theme.palette.background.paper,
  boxShadow: '0 10px 40px rgba(0, 0, 0, 0.15)',
  borderRadius: 16,
  overflow: 'hidden',
  border: theme.palette.mode === 'dark' 
    ? '1px solid rgba(255, 255, 255, 0.1)' 
    : `1px solid ${theme.palette.divider}`,
  '&::before': {
    content: '""',
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    height: 3,
    background: 'linear-gradient(90deg, #4285F4, #34A853, #FBBC05, #EA4335)',
    zIndex: 1301,
  },
}));

const ChatHeader = styled(Box)(({ theme }) => ({
  padding: theme.spacing(1.25, 2),
  borderBottom: `1px solid ${theme.palette.divider}`,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  backgroundColor: theme.palette.background.paper,
  color: theme.palette.text.primary,
  boxShadow: '0 1px 3px rgba(0, 0, 0, 0.05)',
  position: 'relative',
  zIndex: 2,
  '& .MuiTypography-root': {
    fontSize: '0.9rem',
    fontWeight: 500,
  },
}));

const MessagesContainer = styled(Box)(({ theme }) => ({
  flexGrow: 1,
  overflowY: 'auto',
  padding: '8px 16px',
  display: 'flex',
  flexDirection: 'column',
  gap: '4px',
  backgroundColor: theme.palette.mode === 'dark' ? 'rgba(0, 0, 0, 0.1)' : 'rgba(0, 0, 0, 0.02)',
  '&::-webkit-scrollbar': {
    width: '6px',
    height: '6px',
  },
  '&::-webkit-scrollbar-track': {
    backgroundColor: 'rgba(0, 0, 0, 0.05)',
    borderRadius: '3px',
  },
  '&::-webkit-scrollbar-thumb': {
    backgroundColor: 'rgba(0, 0, 0, 0.2)',
    borderRadius: '3px',
    '&:hover': {
      backgroundColor: 'rgba(0, 0, 0, 0.3)',
    }
  },
  // Force scrollbar to always be visible in modern browsers
  scrollbarWidth: 'thin',
  msOverflowStyle: 'auto',
}));

const InputContainer = styled(Box)(({ theme }) => ({
  padding: theme.spacing(1.25),
  borderTop: `1px solid ${theme.palette.divider}`,
  display: 'flex',
  gap: theme.spacing(0.75),
  backgroundColor: theme.palette.mode === 'dark' 
    ? 'rgba(0, 0, 0, 0.2)' 
    : theme.palette.grey[50],
  boxShadow: '0 -1px 5px rgba(0, 0, 0, 0.05)',
  position: 'relative',
}));

const MessageBubble = styled(Box)(({ theme, isUser }) => ({
  display: 'flex',
  padding: theme.spacing(0.2, 0.5),
  alignItems: 'flex-start',
  gap: theme.spacing(0.5),
  flexDirection: isUser ? 'row-reverse' : 'row',
  marginBottom: theme.spacing(0.4),
}));

const BubbleContent = styled(Paper)(({ theme, isUser, isError }) => ({
  padding: theme.spacing(1, 1.5),
  maxWidth: '90%',
  backgroundColor: isError
    ? theme.palette.error.light
    : isUser
      ? theme.palette.primary.main
      : theme.palette.mode === 'dark' ? 'rgba(255, 255, 255, 0.05)' : theme.palette.grey[50],
  color: isError
    ? theme.palette.error.contrastText
    : isUser
      ? theme.palette.primary.contrastText
      : theme.palette.text.primary,
  borderRadius: isUser ? '18px 18px 4px 18px' : '18px 18px 18px 4px',
  wordWrap: 'break-word',
  boxShadow: '0 1px 4px rgba(0, 0, 0, 0.08)',
  border: isUser
    ? 'none'
    : isError
      ? `1px solid ${theme.palette.error.main}`
      : theme.palette.mode === 'dark' 
        ? '1px solid rgba(255, 255, 255, 0.1)' 
        : `1px solid ${theme.palette.divider}`,
  fontSize: '0.82rem',  // Smaller base font size
  lineHeight: 1.35,     // Tighter line height
  fontFamily: '"Roboto", "Segoe UI", "Helvetica", "Arial", sans-serif',
  '& pre': {
    backgroundColor: theme.palette.mode === 'dark' ? 'rgba(0, 0, 0, 0.3)' : 'rgba(0, 0, 0, 0.05)',
    padding: theme.spacing(0.75),
    borderRadius: 4,
    overflowX: 'auto',
    fontFamily: '"Consolas", "Monaco", "Andale Mono", monospace',
    fontSize: '0.75rem',
    margin: theme.spacing(0.75, 0),
    maxHeight: '300px',
    overflowY: 'auto',
  },
  '& code': {
    backgroundColor: theme.palette.mode === 'dark' ? 'rgba(0, 0, 0, 0.3)' : 'rgba(0, 0, 0, 0.05)',
    padding: '2px 4px',
    borderRadius: 3,
    fontFamily: '"Consolas", "Monaco", "Andale Mono", monospace',
    fontSize: '0.75rem',
  },
  '& p': {
    margin: theme.spacing(0.25, 0),
  },
  '& h1, & h2, & h3, & h4, & h5, & h6': {
    margin: theme.spacing(1, 0, 0.5),
    fontSize: '0.9rem',
    fontWeight: 600,
  },
  '& h1': { fontSize: '1rem' },
  '& h2': { fontSize: '0.95rem' },
  '& h3': { fontSize: '0.9rem' },
  '& ul, & ol': {
    paddingLeft: theme.spacing(1.75),
    margin: theme.spacing(0.25, 0),
  },
  '& li': {
    margin: theme.spacing(0.1, 0),
    fontSize: '0.8rem',
  },
  '& table': {
    borderCollapse: 'collapse',
    width: '100%',
    margin: theme.spacing(1.5, 0),
    fontSize: '0.8rem',
    border: `1px solid ${theme.palette.divider}`,
    boxShadow: '0 2px 5px rgba(0, 0, 0, 0.1)',
    borderRadius: '4px',
    overflow: 'hidden',
  },
  '& thead': {
    backgroundColor: theme.palette.mode === 'dark' ? 'rgba(255, 255, 255, 0.15)' : theme.palette.primary.light,
  },
  '& th': {
    padding: theme.spacing(0.75, 1),
    textAlign: 'center',
    fontWeight: 'bold',
    color: theme.palette.mode === 'dark' ? 'white' : theme.palette.primary.contrastText,
    borderBottom: `2px solid ${theme.palette.mode === 'dark' ? 'rgba(255, 255, 255, 0.2)' : theme.palette.primary.main}`,
  },
  '& td': {
    padding: theme.spacing(0.75, 1),
    borderBottom: `1px solid ${theme.palette.divider}`,
    textAlign: 'center',
    borderRight: `1px solid ${theme.palette.divider}`,
  },
  '& tr:nth-of-type(even)': {
    backgroundColor: theme.palette.mode === 'dark' ? 'rgba(255, 255, 255, 0.05)' : 'rgba(0, 0, 0, 0.02)',
  },
  '& tr:hover': {
    backgroundColor: theme.palette.mode === 'dark' ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.04)',
  },
  '& tr:last-child td': {
    borderBottom: 'none',
  },
  '& td:last-child': {
    borderRight: 'none',
  },
  '& code': {
    backgroundColor: theme.palette.mode === 'dark' ? 'rgba(0, 0, 0, 0.4)' : 'rgba(0, 0, 0, 0.06)',
    padding: '3px 5px',
    borderRadius: 4,
    fontFamily: '"Consolas", "Monaco", "Andale Mono", monospace',
    fontSize: '0.75rem',
    color: theme.palette.mode === 'dark' ? theme.palette.primary.light : theme.palette.primary.dark,
  },
}));

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

  // Determine API base URL: env var or same-origin
// Backend base URL (no trailing slash)
const API_BASE = 'https://sap-ewa-analyzer-backend.azurewebsites.net';

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
      
      const response = await fetch(`${API_BASE}/api/chat`, {
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

  if (!expanded) {
    return (
      <Fab
        color="primary"
        aria-label="chat"
        sx={{ position: 'fixed', bottom: 20, right: 20, zIndex: 1300 }}
        onClick={() => setExpanded(true)}
      >
        <ChatIcon />
      </Fab>
    );
  }

  return (
    <ChatContainer elevation={8} expanded={expanded}>
      <ChatHeader>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <BotIcon />
          <Typography variant="subtitle1" fontWeight="bold">
            Document Assistant
          </Typography>
        </Box>
        <IconButton
          size="small"
          onClick={() => setExpanded(false)}
          sx={{ color: 'inherit' }}
        >
          <CloseIcon />
        </IconButton>
      </ChatHeader>

      <MessagesContainer>
        {messages.length === 0 && (
          <Box sx={{ textAlign: 'center', py: 4, color: 'text.secondary' }}>
            <BotIcon sx={{ fontSize: 48, mb: 1, opacity: 0.5 }} />
            {contentStatus === 'available' ? (
              <Typography variant="body2">
                Ask me anything about this SAP EWA report!
              </Typography>
            ) : contentStatus === 'missing' || contentStatus === 'minimal' ? (
              <Box>
                <Typography variant="body2" color="error.main" sx={{ mb: 1 }}>
                  Document content is limited or missing.
                </Typography>
                <Typography variant="caption">
                  Please ensure the document has been processed first by clicking the "Process file" button.
                </Typography>
              </Box>
            ) : contentStatus === 'error' ? (
              <Box>
                <Typography variant="body2" color="error.main" sx={{ mb: 1 }}>
                  Error loading document content.
                </Typography>
                <Typography variant="caption">
                  Please try reprocessing the document or check server logs.
                </Typography>
              </Box>
            ) : (
              <Typography variant="body2">
                Ask me anything about this document!
              </Typography>
            )}
          </Box>
        )}
        
        {messages.map((message, index) => (
          <MessageBubble key={index} isUser={message.isUser}>
            <Avatar sx={{ width: 26, height: 26, bgcolor: message.isError ? 'error.main' : (message.isUser ? 'primary.main' : 'grey.500') }}>
              {message.isUser ? <PersonIcon fontSize="small" /> : <BotIcon fontSize="small" />}
            </Avatar>
            <BubbleContent isUser={message.isUser} isError={message.isError}>
              {message.isUser ? (
                <Typography sx={{ whiteSpace: 'pre-wrap', fontSize: '0.85rem', lineHeight: 1.4 }}>
                  {message.text}
                </Typography>
              ) : (
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {message.text}
                </ReactMarkdown>
              )}
            </BubbleContent>
          </MessageBubble>
        ))}
        
        {loading && (
          <MessageBubble isUser={false}>
            <Avatar sx={{ width: 26, height: 26, bgcolor: 'primary.light' }}>
              <BotIcon fontSize="small" />
            </Avatar>
            <BubbleContent isUser={false} sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
              <CircularProgress size={14} thickness={4} sx={{ color: 'primary.main' }} />
              <Typography variant="body2" sx={{ fontStyle: 'italic', opacity: 0.7, fontSize: '0.8rem' }}>
                Thinking...
              </Typography>
            </BubbleContent>
          </MessageBubble>
        )}
        <div ref={messagesEndRef} />
      </MessagesContainer>

      <InputContainer>
        <TextField
          fullWidth
          variant="outlined"
          placeholder="Ask about this document..."
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyPress={handleKeyPress}
          disabled={loading}
          size="small"
          multiline
          maxRows={3}
          sx={{
            '& .MuiOutlinedInput-root': {
              borderRadius: '20px',
              backgroundColor: theme => theme.palette.background.paper,
              '&.Mui-focused': {
                boxShadow: '0 0 0 2px rgba(25, 118, 210, 0.2)',
              },
              '& .MuiOutlinedInput-input': {
                fontSize: '0.85rem',
                lineHeight: 1.4,
                padding: '8px 14px',
              },
            },
          }}
        />
        <IconButton
          color="primary"
          onClick={handleSendMessage}
          disabled={!inputValue.trim() || loading}
          sx={{
            backgroundColor: theme => theme.palette.primary.main,
            color: 'white',
            '&:hover': {
              backgroundColor: theme => theme.palette.primary.dark,
            },
            '&.Mui-disabled': {
              backgroundColor: 'rgba(0, 0, 0, 0.12)',
              color: 'rgba(0, 0, 0, 0.26)',
            },
            width: 40,
            height: 40,
          }}
        >
          <SendIcon fontSize="small" />
        </IconButton>
      </InputContainer>
    </ChatContainer>
  );
};

export default DocumentChat;
