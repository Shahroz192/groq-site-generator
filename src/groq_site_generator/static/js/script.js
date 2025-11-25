const promptInput = document.getElementById('prompt-input');
const generateBtn = document.getElementById('generate-btn');
const previewFrame = document.getElementById('preview-frame');
const themeSwitcher = document.getElementById('theme-switcher');
const themeIcon = themeSwitcher ? themeSwitcher.querySelector('i') : null;
const promptCharCount = document.getElementById('prompt-char-count');
const lineCount = document.getElementById('line-count');
const charCount = document.getElementById('char-count');
const previewLoading = document.getElementById('preview-loading');
const refreshPreview = document.getElementById('refresh-preview');
const openPreview = document.getElementById('open-preview');
const historySearch = document.getElementById('history-search');
let monacoEditor;
let isGenerating = false;

require.config({ paths: { 'vs': 'https://cdn.jsdelivr.net/npm/monaco-editor@0.45.0/min/vs' } });
require(['vs/editor/editor.main'], function () {
    monacoEditor = monaco.editor.create(document.getElementById('monaco-editor-container'), {
        value: '',
        language: 'html',
        theme: 'vs-dark',
        automaticLayout: true,
        readOnly: false,
        wordWrap: 'on',
        minimap: { enabled: false },
        scrollBeyondLastLine: false,
    });

    monacoEditor.getModel().onDidChangeContent(() => {
        const content = monacoEditor.getValue();
        previewFrame.srcdoc = content;
        updateStatusInfo(content);
    });

    setTheme(localStorage.getItem('theme') || 'dark');
});

function setTheme(theme) {
    if (theme === 'light') {
        document.body.classList.remove('dark-mode');
        document.body.classList.add('light-mode');
        themeIcon.classList.remove('fa-moon');
        themeIcon.classList.add('fa-sun');
        if (monacoEditor) monaco.editor.setTheme('vs');
        localStorage.setItem('theme', 'light');
    } else {
        document.body.classList.remove('light-mode');
        document.body.classList.add('dark-mode');
        themeIcon.classList.remove('fa-sun');
        themeIcon.classList.add('fa-moon');
        if (monacoEditor) monaco.editor.setTheme('vs-dark');
        localStorage.setItem('theme', 'dark');
    }
}

themeSwitcher.addEventListener('click', () => {
    const currentTheme = localStorage.getItem('theme');
    setTheme(currentTheme === 'light' ? 'dark' : 'light');
});

// Character counter for prompt
promptInput.addEventListener('input', () => {
    const length = promptInput.value.length;
    promptCharCount.textContent = length;

    if (length > 950) {
        promptCharCount.style.color = 'var(--error)';
    } else if (length > 900) {
        promptCharCount.style.color = 'var(--warning)';
    } else {
        promptCharCount.style.color = 'var(--light-text-tertiary)';
    }
});

// Update status info
function updateStatusInfo(content) {
    const lines = content.split('\n').length;
    const chars = content.length;

    lineCount.textContent = `Line ${monacoEditor.getPosition().lineNumber}`;
    charCount.textContent = `${chars} chars`;
}

// Preview controls
refreshPreview.addEventListener('click', () => {
    const currentContent = monacoEditor.getValue();
    previewFrame.srcdoc = currentContent;

    // Show loading state briefly
    previewLoading.style.display = 'flex';
    setTimeout(() => {
        previewLoading.style.display = 'none';
    }, 500);
});

openPreview.addEventListener('click', () => {
    const content = monacoEditor.getValue();
    const newWindow = window.open();
    newWindow.document.write(content);
    newWindow.document.close();
});

// History search functionality
historySearch.addEventListener('input', (e) => {
    const searchTerm = e.target.value.toLowerCase();
    const sessionContainers = document.querySelectorAll('.session-container');

    sessionContainers.forEach(container => {
        const sessionTitle = container.querySelector('.session-title span').textContent.toLowerCase();
        const sessionMeta = container.querySelector('.session-meta').textContent.toLowerCase();
        const versionItems = container.querySelectorAll('.version-item');

        // Check if search term matches session title or meta
        const sessionMatches = sessionTitle.includes(searchTerm) || sessionMeta.includes(searchTerm);

        // Check if any version in this session matches
        let hasMatchingVersions = false;
        versionItems.forEach(versionItem => {
            const prompt = versionItem.querySelector('.version-prompt').textContent.toLowerCase();
            if (prompt.includes(searchTerm)) {
                versionItem.style.display = 'block';
                hasMatchingVersions = true;
            } else {
                versionItem.style.display = 'none';
            }
        });

        // Show/hide the session based on matches
        if (sessionMatches || hasMatchingVersions) {
            container.style.display = 'block';
        } else {
            container.style.display = 'none';
        }
    });
});


const resizer = document.getElementById('resizer');
const editorPane = document.getElementById('editor-pane');
const previewPane = document.getElementById('preview-pane');

let isResizing = false;
resizer.addEventListener('mousedown', (e) => {
    isResizing = true;
    document.body.style.userSelect = 'none';
    document.body.style.pointerEvents = 'none';
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', stopResizing);
});

function handleMouseMove(e) {
    if (!isResizing) return;
    const mainPanel = resizer.parentNode;
    const totalWidth = mainPanel.offsetWidth;
    const newLeftWidth = e.clientX - mainPanel.getBoundingClientRect().left;
    const leftPercentage = (newLeftWidth / totalWidth) * 100;
    editorPane.style.flex = `0 0 ${leftPercentage}%`;
    previewPane.style.flex = `1 1 ${100 - leftPercentage}%`;
}

function stopResizing() {
    isResizing = false;
    document.body.style.userSelect = '';
    document.body.style.pointerEvents = '';
    document.removeEventListener('mousemove', handleMouseMove);
    document.removeEventListener('mouseup', stopResizing);
}

generateBtn.addEventListener('click', async () => {
    const prompt = promptInput.value.trim();
    if (!prompt) {
        showNotification('Please enter a prompt.', 'warning');
        return;
    }

    if (isGenerating) return;

    isGenerating = true;
    generateBtn.disabled = true;
    generateBtn.classList.add('loading');
    generateBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';

    // Update status
    document.querySelector('.status-indicator span:last-child').textContent = 'Generating...';
    document.querySelector('.status-dot').style.background = 'var(--warning)';

    monacoEditor.setValue('');
    previewFrame.srcdoc = '';
    previewLoading.style.display = 'flex';

    let accumulatedCode = '';
    const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');

    try {
        const response = await fetch('/generate', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify({ prompt: prompt, code: monacoEditor.getValue() })
        });

        if (!response.body) {
            throw new Error("Response body is missing.");
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value, { stream: true });
            accumulatedCode += chunk;

            monacoEditor.setValue(accumulatedCode);
            previewFrame.srcdoc = accumulatedCode;
        }

        // Success notification
        showNotification('Code generated successfully!', 'success');

    } catch (error) {
        const errorMessage = `/*
 Error: ${error.message}
 */`;
        monacoEditor.setValue(errorMessage);
        previewFrame.srcdoc = `<p style="color:red; font-family: sans-serif; text-align: center; padding: 2rem;">${error.message}</p>`;
        console.error('Error:', error);
        showNotification(`Error: ${error.message}`, 'error');
    } finally {
        isGenerating = false;
        generateBtn.disabled = false;
        generateBtn.classList.remove('loading');
        generateBtn.innerHTML = '<i class="fas fa-paper-plane"></i>';
        previewLoading.style.display = 'none';

        // Update status
        document.querySelector('.status-indicator span:last-child').textContent = 'Ready';
        document.querySelector('.status-dot').style.background = 'var(--success)';
    }
});

const downloadBtn = document.getElementById('download-btn');
downloadBtn.addEventListener('click', () => {
    const code = monacoEditor.getValue();
    if (!code || code.trim() === '') {
        alert('Nothing to download.');
        return;
    }
    const blob = new Blob([code], { type: 'text/html' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'index.html';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(a.href);
});

const newChatBtn = document.getElementById('new-chat-btn');
newChatBtn.addEventListener('click', async () => {
    monacoEditor.setValue('');
    previewFrame.srcdoc = '';
    promptInput.value = '';
    const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
    try {
        await fetch('/new_chat', {
            method: 'POST',
            headers: {
                'X-CSRFToken': csrfToken
            }
        });
    } catch (error) {
        console.error('Error starting new chat:', error);
    }
});

/* History Logic */
const historyBtn = document.getElementById('history-btn');
const historySidebar = document.getElementById('history-sidebar');
const closeHistoryBtn = document.getElementById('close-history-btn');
const historyList = document.getElementById('history-list');

historyBtn.addEventListener('click', () => {
    historySidebar.classList.add('open');
    loadHistory();
});

closeHistoryBtn.addEventListener('click', () => {
    historySidebar.classList.remove('open');
});

async function loadHistory() {
    historyList.innerHTML = '<p style="text-align:center; padding: 1rem;">Loading sessions...</p>';
    try {
        const response = await fetch('/api/sessions');
        if (!response.ok) throw new Error('Failed to load sessions');
        const sessions = await response.json();
        renderSessionHistory(sessions);
    } catch (error) {
        historyList.innerHTML = `<p style="color:red; text-align:center;">Error: ${error.message}</p>`;
    }
}

function renderSessionHistory(sessions) {
    historyList.innerHTML = '';
    if (sessions.length === 0) {
        historyList.innerHTML = `
            <div class="history-empty">
                <div class="history-empty-icon">💭</div>
                <div class="history-empty-text">No sessions found</div>
                <div class="history-empty-subtext">Start a new chat to create your first session</div>
            </div>
        `;
        return;
    }

    sessions.forEach(session => {
        // Create session container
        const sessionContainer = document.createElement('div');
        sessionContainer.className = 'session-container';

        // Create session header (clickable to switch)
        const sessionHeader = document.createElement('div');
        sessionHeader.className = 'session-header';

        const sessionDate = new Date(session.created_at).toLocaleDateString();
        const sessionTime = new Date(session.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

        sessionHeader.innerHTML = `
            <div class="session-info">
                <div class="session-title">
                    <i class="fas fa-folder session-folder-icon"></i>
                    <span>Session - ${sessionDate} ${sessionTime}</span>
                </div>
                <div class="session-meta">
                    <span class="session-count">${session.version_count} versions</span>
                </div>
            </div>
            <div class="session-expand-btn">
                <i class="fas fa-chevron-down"></i>
            </div>
        `;

        // Create versions list container
        const versionList = document.createElement('div');
        versionList.className = 'version-list';

        // Get session expand button
        const sessionExpandBtn = sessionHeader.querySelector('.session-expand-btn');

        // Add click handler for session switching
        sessionHeader.addEventListener('click', async () => {
            if (sessionHeader.classList.contains('expanded')) {
                // Collapse
                sessionHeader.classList.remove('expanded');
                versionList.style.display = 'none';
                sessionExpandBtn.querySelector('i').className = 'fas fa-chevron-down';
            } else {
                // Expand or switch session
                sessionHeader.classList.add('expanded');

                if (!versionList.hasChildNodes()) {
                    // Load versions for this session
                    await loadSessionVersions(session.id, versionList, session);
                }

                versionList.style.display = 'block';
                sessionExpandBtn.querySelector('i').className = 'fas fa-chevron-up';
            }
        });

        sessionContainer.appendChild(sessionHeader);
        sessionContainer.appendChild(versionList);
        historyList.appendChild(sessionContainer);
    });
}

async function loadSessionVersions(sessionId, container, session) {
    container.innerHTML = '<div class="versions-loading">Loading versions...</div>';

    try {
        const response = await fetch(`/api/sessions/${sessionId}`);
        if (!response.ok) throw new Error('Failed to load session details');

        const sessionData = await response.json();
        renderSessionVersions(sessionData.versions, container, session);
    } catch (error) {
        container.innerHTML = `<div class="versions-error">Error: ${error.message}</div>`;
    }
}

function renderSessionVersions(versions, container, session) {
    container.innerHTML = '';

    if (versions.length === 0) {
        container.innerHTML = '<div class="version-empty">No versions in this session</div>';
        return;
    }

    versions.forEach(version => {
        const versionItem = document.createElement('div');
        versionItem.className = 'version-item';

        const versionDate = new Date(version.created_at).toLocaleString();
        const truncatedPrompt = version.prompt.length > 100
            ? version.prompt.substring(0, 100) + '...'
            : version.prompt;

        versionItem.innerHTML = `
            <div class="version-content">
                <div class="version-timestamp">${versionDate}</div>
                <div class="version-prompt">${truncatedPrompt}</div>
            </div>
        `;

        versionItem.addEventListener('click', async () => {
            // First switch to the session, then load the version
            await switchToSession(session.id);
            await loadVersionContent(version.id);
        });

        container.appendChild(versionItem);
    });
}

async function switchToSession(sessionId) {
    try {
        const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
        const response = await fetch(`/api/sessions/${sessionId}/switch`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            }
        });

        if (!response.ok) throw new Error('Failed to switch session');

        const data = await response.json();
        console.log('Switched to session:', data.session_id);
        return true;
    } catch (error) {
        console.error('Error switching session:', error);
        showNotification(`Error switching session: ${error.message}`, 'error');
        return false;
    }
}

async function loadVersionContent(versionId) {
    try {
        previewLoading.style.display = 'flex';
        const response = await fetch(`/api/versions/${versionId}`);
        if (!response.ok) throw new Error('Failed to load version content');
        const data = await response.json();

        monacoEditor.setValue(data.html_content);
        previewFrame.srcdoc = data.html_content;
        promptInput.value = data.prompt;

        // Update character counter
        promptCharCount.textContent = data.prompt.length;

        // Close sidebar on mobile or if desired
        if (window.innerWidth < 768) {
            historySidebar.classList.remove('open');
        }

        showNotification('Version loaded successfully', 'success');
    } catch (error) {
        showNotification(`Error loading version: ${error.message}`, 'error');
    } finally {
        previewLoading.style.display = 'none';
    }
}

// Notification system
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.innerHTML = `
        <div class="notification-content">
            <i class="fas fa-${getNotificationIcon(type)}"></i>
            <span>${message}</span>
        </div>
    `;

    document.body.appendChild(notification);

    // Animate in
    setTimeout(() => {
        notification.classList.add('show');
    }, 100);

    // Remove after 3 seconds
    setTimeout(() => {
        notification.classList.remove('show');
        setTimeout(() => {
            document.body.removeChild(notification);
        }, 300);
    }, 3000);
}

function getNotificationIcon(type) {
    switch (type) {
        case 'success': return 'check-circle';
        case 'error': return 'exclamation-circle';
        case 'warning': return 'exclamation-triangle';
        default: return 'info-circle';
    }
}
