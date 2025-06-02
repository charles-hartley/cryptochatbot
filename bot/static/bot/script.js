// Django integration utilities
function getCsrfToken() {
    const metaTag = document.querySelector('meta[name="csrf-token"]');
    return metaTag ? metaTag.getAttribute('content') : '';
}

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// Global variables
const chatbox = document.getElementById('chatbox');
const userInput = document.getElementById('userInput');
const sendButton = document.querySelector('.send-button');
let isTyping = false;
let messageQueue = [];
let isProcessingQueue = false;

// API Configuration
const API_CONFIG = {
    chatEndpoint: '/chat/',
    cryptoAdviceEndpoint: '/crypto/',
    addCryptoEndpoint: '/add-crypto/',
    timeout: 10000,
    retryAttempts: 3,
    retryDelay: 1000
};

// Enhanced error handling
class ChatError extends Error {
    constructor(message, type = 'generic', statusCode = null) {
        super(message);
        this.name = 'ChatError';
        this.type = type;
        this.statusCode = statusCode;
    }
}

// Start chat function with enhanced initialization
function startChat() {
    try {
        document.getElementById('home').style.display = 'none';
        document.getElementById('chat-section').style.display = 'flex';
        document.getElementById('chat-section').classList.add('fade-in');
        
        // Initialize session
        initializeSession();
        
        // Welcome message with delay for better UX
        setTimeout(() => {
            const welcomeMessages = [
                "🚀 GM! I'm your CryptoAI assistant. Ready to dive into the world of crypto?",
                "💎 Hey there! Ask me about any cryptocurrency - I've got the latest insights and some spicy takes!",
                "🌟 Welcome to CryptoAI! Whether you're a diamond hands veteran or crypto-curious newcomer, I'm here to help!"
            ];
            const randomWelcome = welcomeMessages[Math.floor(Math.random() * welcomeMessages.length)];
            addBotMessage(randomWelcome);
        }, 800);
        
        // Focus on input
        setTimeout(() => {
            userInput.focus();
        }, 1000);
        
    } catch (error) {
        console.error('Error starting chat:', error);
        showErrorToast('Failed to initialize chat. Please refresh the page.');
    }
}

// Session initialization
function initializeSession() {
    // Store session start time
    sessionStorage.setItem('chatStartTime', new Date().toISOString());
    
    // Initialize message counter
    sessionStorage.setItem('messageCount', '0');
    
    // Check for existing session
    const sessionKey = getCookie('sessionid');
    if (!sessionKey) {
        console.log('New session started');
    }
}

// Enhanced message functions
function addUserMessage(message) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message user-message';
    messageDiv.innerHTML = `
        <div class="message-content">
            ${escapeHtml(message)}
            <div class="message-time">${getCurrentTime()}</div>
        </div>
    `;
    chatbox.appendChild(messageDiv);
    scrollToBottom();
    incrementMessageCount();
}

function addBotMessage(message, format = 'text') {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message bot-message';
    
    // Handle different message formats
    let content = message;
    if (format === 'html') {
        content = message; // Already formatted HTML
    } else {
        content = escapeHtml(message).replace(/\n/g, '<br>');
    }
    
    messageDiv.innerHTML = `
        <div class="bot-avatar">
            <i class="fas fa-robot"></i>
        </div>
        <div class="message-content">
            ${content}
            <div class="message-time">${getCurrentTime()}</div>
        </div>
    `;
    chatbox.appendChild(messageDiv);
    scrollToBottom();
}

// Enhanced typing indicator with personality
function showTypingIndicator() {
    if (isTyping) return;
    isTyping = true;
    
    const typingDiv = document.createElement('div');
    typingDiv.className = 'message bot-message typing-indicator';
    typingDiv.id = 'typing-indicator';
    
    const thinkingMessages = [
        "Analyzing the blockchain...",
        "Consulting my crystal ball...",
        "Checking the charts...",
        "Thinking...",
        "Processing alpha..."
    ];
    
    const randomThinking = thinkingMessages[Math.floor(Math.random() * thinkingMessages.length)];
    
    typingDiv.innerHTML = `
        <div class="bot-avatar">
            <i class="fas fa-robot"></i>
        </div>
        <div class="typing-content">
            <div class="typing-text">${randomThinking}</div>
            <div class="typing-dots">
                <span></span>
                <span></span>
                <span></span>
            </div>
        </div>
    `;
    chatbox.appendChild(typingDiv);
    scrollToBottom();
}

function hideTypingIndicator() {
    const typingIndicator = document.getElementById('typing-indicator');
    if (typingIndicator) {
        typingIndicator.remove();
        isTyping = false;
    }
}

// Enhanced API call with retry logic
async function makeApiCall(url, options = {}) {
    const defaultOptions = {
        method: 'GET',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken(),
        },
        timeout: API_CONFIG.timeout,
        ...options
    };

    for (let attempt = 1; attempt <= API_CONFIG.retryAttempts; attempt++) {
        try {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), defaultOptions.timeout);
            
            const response = await fetch(url, {
                ...defaultOptions,
                signal: controller.signal
            });
            
            clearTimeout(timeoutId);
            
            if (!response.ok) {
                throw new ChatError(
                    `Server error: ${response.status} ${response.statusText}`,
                    'server_error',
                    response.status
                );
            }
            
            const data = await response.json();
            return data;
            
        } catch (error) {
            console.error(`API call attempt ${attempt} failed:`, error);
            
            if (attempt === API_CONFIG.retryAttempts) {
                if (error.name === 'AbortError') {
                    throw new ChatError('Request timed out. Please try again.', 'timeout');
                }
                throw error;
            }
            
            // Wait before retry
            await new Promise(resolve => setTimeout(resolve, API_CONFIG.retryDelay * attempt));
        }
    }
}

// Main send message function with enhanced error handling
async function sendMessage() {
    const message = userInput.value.trim();
    if (!message || isTyping) return;

    try {
        // Add user message
        addUserMessage(message);
        userInput.value = '';
        disableInput();
        showTypingIndicator();

        // Add to message queue for rate limiting
        await addToMessageQueue(message);

    } catch (error) {
        console.error('Error sending message:', error);
        hideTypingIndicator();
        handleApiError(error);
        enableInput();
    }
}

// Message queue system for rate limiting
async function addToMessageQueue(message) {
    messageQueue.push(message);
    
    if (!isProcessingQueue) {
        await processMessageQueue();
    }
}

async function processMessageQueue() {
    if (isProcessingQueue || messageQueue.length === 0) return;
    
    isProcessingQueue = true;
    
    while (messageQueue.length > 0) {
        const message = messageQueue.shift();
        await sendMessageToApi(message);
        
        // Rate limiting: wait between messages
        if (messageQueue.length > 0) {
            await new Promise(resolve => setTimeout(resolve, 500));
        }
    }
    
    isProcessingQueue = false;
}

// Enhanced API communication
async function sendMessageToApi(message) {
    try {
        const url = `${API_CONFIG.chatEndpoint}?message=${encodeURIComponent(message)}`;
        const data = await makeApiCall(url);
        
        // Simulate realistic typing delay
        const typingDelay = Math.min(1000 + (data.response.length * 10), 3000);
        
        setTimeout(() => {
            hideTypingIndicator();
            
            // Handle different response formats
            if (data.format === 'html') {
                addBotMessage(data.response, 'html');
            } else {
                addBotMessage(data.response);
            }
            
            // Handle special response types
            handleSpecialResponseTypes(data);
            
            enableInput();
        }, typingDelay);
        
    } catch (error) {
        hideTypingIndicator();
        handleApiError(error);
        enableInput();
    }
}

// Handle special response types from Django backend
function handleSpecialResponseTypes(data) {
    switch (data.type) {
        case 'crypto_analysis':
            if (data.coin) {
                trackCoinInteraction(data.coin);
            }
            break;
            
        case 'portfolio_summary':
            // Could trigger additional UI updates
            break;
            
        case 'market_overview':
            // Could show market indicators
            break;
            
        case 'greeting':
            // Could trigger welcome animations
            break;
    }
}

// Enhanced error handling
function handleApiError(error) {
    let errorMessage = "I'm having trouble connecting right now. ";
    
    if (error instanceof ChatError) {
        switch (error.type) {
            case 'timeout':
                errorMessage = "⏱️ That took too long! Let me try to think faster next time.";
                break;
            case 'server_error':
                if (error.statusCode >= 500) {
                    errorMessage = "🔧 My servers are having a moment. Give me a sec to get back up!";
                } else if (error.statusCode === 404) {
                    errorMessage = "🔍 Hmm, I couldn't find what you're looking for. Try rephrasing?";
                } else {
                    errorMessage = "⚠️ Something went wrong on my end. Please try again!";
                }
                break;
            default:
                errorMessage = "🤖 I'm experiencing some technical difficulties. Please try again!";
        }
    }
    
    addBotMessage(errorMessage);
    showErrorToast(error.message || 'Connection error');
}

// Quick message function with loading state
function quickMessage(message) {
    if (isTyping) return;
    
    userInput.value = message;
    
    // Add visual feedback for quick actions
    const quickActions = document.querySelectorAll('.quick-action');
    quickActions.forEach(action => {
        if (action.onclick.toString().includes(message)) {
            action.classList.add('active');
            setTimeout(() => action.classList.remove('active'), 300);
        }
    });
    
    sendMessage();
}

// Utility functions
function disableInput() {
    userInput.disabled = true;
    userInput.placeholder = "Sending...";
    if (sendButton) {
        sendButton.disabled = true;
        sendButton.innerHTML = '<div class="loading"></div><span>Sending</span>';
    }
}

function enableInput() {
    userInput.disabled = false;
    userInput.placeholder = "Ask me about Bitcoin, Ethereum, or any crypto...";
    if (sendButton) {
        sendButton.disabled = false;
        sendButton.innerHTML = '<i class="fas fa-paper-plane"></i><span>Send</span>';
    }
    userInput.focus();
}

function scrollToBottom() {
    chatbox.scrollTop = chatbox.scrollHeight;
}

function getCurrentTime() {
    return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function incrementMessageCount() {
    const count = parseInt(sessionStorage.getItem('messageCount') || '0') + 1;
    sessionStorage.setItem('messageCount', count.toString());
}

function trackCoinInteraction(coin) {
    // Track user interactions with specific coins
    const interactions = JSON.parse(localStorage.getItem('coinInteractions') || '{}');
    interactions[coin] = (interactions[coin] || 0) + 1;
    localStorage.setItem('coinInteractions', JSON.stringify(interactions));
}

// Error toast system
function showErrorToast(message, duration = 5000) {
    const toastContainer = document.getElementById('toast-container');
    const errorToast = document.getElementById('error-toast');
    const errorMessage = document.getElementById('error-message');
    
    if (toastContainer && errorToast && errorMessage) {
        errorMessage.textContent = message;
        toastContainer.style.display = 'block';
        errorToast.classList.add('show');
        
        setTimeout(() => {
            errorToast.classList.remove('show');
            setTimeout(() => {
                toastContainer.style.display = 'none';
            }, 300);
        }, duration);
    }
}

// Enhanced event listeners with better UX
document.addEventListener('DOMContentLoaded', function() {
    // Input handling with improved UX
    userInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            if (!isTyping && this.value.trim()) {
                sendMessage();
            }
        }
    });

    // Auto-resize input with better limits
    userInput.addEventListener('input', function() {
        this.style.height = 'auto';
        const newHeight = Math.min(this.scrollHeight, 120);
        this.style.height = newHeight + 'px';
        
        // Update placeholder based on content
        if (this.value.length > 100) {
            this.placeholder = "That's a long message! 📝";
        } else {
            this.placeholder = "Ask me about Bitcoin, Ethereum, or any crypto...";
        }
    });

    // Handle page visibility changes
    document.addEventListener('visibilitychange', function() {
        if (document.visibilityState === 'visible' && userInput) {
            userInput.focus();
        }
    });

    // Check URL hash for direct chat access
    if (window.location.hash === '#chat') {
        startChat();
    }

    // Add keyboard shortcuts
    document.addEventListener('keydown', function(e) {
        // Escape to clear input
        if (e.key === 'Escape' && userInput === document.activeElement) {
            userInput.value = '';
            userInput.blur();
        }
        
        // Ctrl/Cmd + / to focus input
        if ((e.ctrlKey || e.metaKey) && e.key === '/') {
            e.preventDefault();
            userInput.focus();
        }
    });

    // Initialize service worker for offline support (optional)
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('/static/bot/sw.js')
            .then(() => console.log('Service Worker registered'))
            .catch(err => console.log('Service Worker registration failed'));
    }

    console.log('CryptoAI Chat initialized successfully! 🚀');
});

// Handle online/offline status
window.addEventListener('online', function() {
    const statusElement = document.querySelector('.status span');
    if (statusElement) {
        statusElement.textContent = 'Online & Ready';
        statusElement.style.color = '#4ade80';
    }
});

window.addEventListener('offline', function() {
    const statusElement = document.querySelector('.status span');
    if (statusElement) {
        statusElement.textContent = 'Offline';
        statusElement.style.color = '#ef4444';
    }
    showErrorToast('You appear to be offline. Messages will be sent when connection is restored.');
});