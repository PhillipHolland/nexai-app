document.addEventListener('DOMContentLoaded', () => {
    console.log('DOM loaded, initializing chat.js');
    const chatForm = document.getElementById('chat-form');
    const messageInput = document.getElementById('message-input');
    const fileInput = document.getElementById('file-input');
    const sendButton = document.getElementById('send-button');
    const messages = document.getElementById('messages');
    const clientSelector = document.getElementById('client-selector');
    const promptStarters = document.querySelectorAll('.prompt-starter');
    const promptStartersContainer = document.getElementById('prompt-starters');
    const toggleSidebar = document.getElementById('toggle-sidebar');
    const collapseSidebar = document.getElementById('collapse-sidebar');
    const sidebar = document.getElementById('sidebar');
    const chatHistory = document.getElementById('history');
    const clientDocuments = document.getElementById('client-documents');
    const clientInfo = document.getElementById('client-info');
    const saveClientInfo = document.getElementById('save-client-info');
    const tabButtons = document.querySelectorAll('.tab-button');
    const tabPanes = document.querySelectorAll('.tab-pane');
    const newConversationButton = document.getElementById('new-conversation');
    const historyBadge = document.getElementById('history-badge');
    const documentsBadge = document.getElementById('documents-badge');
    const replyPrompt = document.getElementById('reply-prompt');
    const replyPopup = document.getElementById('reply-popup');
    const replyInput = document.getElementById('reply-input');
    const replySubmit = document.getElementById('reply-submit');
    const replyCancel = document.getElementById('reply-cancel');
    const searchPrompt = document.getElementById('search-prompt');
    const searchPopup = document.getElementById('search-popup');
    const searchInput = document.getElementById('search-input');
    const searchSubmit = document.getElementById('search-submit');
    const searchCancel = document.getElementById('search-cancel');

    if (!chatForm) console.error('chat-form not found');
    if (!messageInput) console.error('message-input not found');
    if (!sendButton) console.error('send-button not found');
    if (!clientSelector) console.error('client-selector not found');
    if (!messages) console.error('messages not found');
    if (!replyPrompt) console.error('reply-prompt not found');
    if (!replyPopup) console.error('reply-popup not found');
    if (!searchPrompt) console.error('search-prompt not found');
    if (!searchPopup) console.error('search-popup not found');
    if (!toggleSidebar) console.error('toggle-sidebar not found');
    if (!sidebar) console.error('sidebar not found');
    if (!promptStartersContainer) console.error('prompt-starters not found');
    if (!fileInput) console.error('file-input not found');

    let currentClientId = '';
    let historyCount = 0;
    let documentCount = 0;

    // Sidebar toggling
    toggleSidebar.addEventListener('click', () => {
        console.log('Toggling sidebar');
        sidebar.classList.toggle('active');
        if (sidebar.classList.contains('active')) {
            sidebar.classList.remove('hidden');
            sidebar.classList.remove('collapsed');
        } else {
            sidebar.classList.add('hidden');
        }
    });

    collapseSidebar.addEventListener('click', () => {
        console.log('Collapsing sidebar');
        sidebar.classList.add('hidden');
        sidebar.classList.remove('active');
        sidebar.classList.add('collapsed');
    });

    // Tab handling
    tabButtons.forEach(button => {
        button.addEventListener('click', () => {
            console.log('Switching tab:', button.id);
            tabButtons.forEach(btn => btn.classList.remove('active'));
            tabPanes.forEach(pane => pane.classList.remove('active'));
            button.classList.add('active');
            document.getElementById(button.id.replace('tab-', '')).classList.add('active');
        });
    });

    // Default to info tab
    document.getElementById('client-info-tab').classList.add('active');
    clientInfo.classList.add('active');

    // Client selection (optional)
    clientSelector.addEventListener('change', async () => {
        currentClientId = clientSelector.value;
        console.log('Selected client:', currentClientId);
        if (!currentClientId) return;

        try {
            const response = await fetch(`/api/client/${currentClientId}`, {
                method: 'GET',
                credentials: 'same-origin',
                headers: {
                    'Accept': 'application/json',
                },
            });
            if (!response.ok) throw new Error(`Failed to fetch client data: ${response.status} ${response.statusText}`);
            const data = await response.json();
            console.log('Client data received:', data);
            // Update client info
            document.getElementById('client-name').value = data.info.name || '';
            document.getElementById('client-case-number').value = data.info.case_number || '';
            document.getElementById('client-email').value = data.info.email || '';
            document.getElementById('client-phone').value = data.info.phone || '';
            document.getElementById('client-case-type').value = data.info.case_type || '';
            document.getElementById('client-notes').value = data.info.notes || '';

            // Update history
            chatHistory.innerHTML = '';
            historyCount = (data.history || []).length;
            historyBadge.textContent = historyCount;
            historyBadge.classList.toggle('active', historyCount > 0);
            (data.history || []).forEach(entry => {
                const div = document.createElement('div');
                div.className = 'p-2 bg-light-cream rounded-lg';
                div.innerHTML = `<span class="text-sm text-dark-green">${new Date(entry.timestamp).toLocaleString()}</span><br><strong>${entry.role === 'user' ? 'You' : 'LexAI'}:</strong> ${entry.content}`;
                chatHistory.appendChild(div);
            });

            // Update documents
            clientDocuments.innerHTML = '';
            documentCount = (data.documents || []).length;
            documentsBadge.textContent = documentCount;
            documentsBadge.classList.toggle('active', documentCount > 0);
            (data.documents || []).forEach(doc => {
                const div = document.createElement('div');
                div.className = 'p-2 bg-light-cream rounded-lg';
                div.innerHTML = `<span class="text-sm text-dark-green">${new Date(doc.upload_date).toLocaleString()}</span><br><strong>${doc.filename}</strong><br>${doc.text.substring(0, 100)}...`;
                clientDocuments.appendChild(div);
            });
        } catch (error) {
            console.error('Error fetching client data:', error);
            const errorMessage = document.createElement('div');
            errorMessage.className = 'mb-2 text-left';
            errorMessage.innerHTML = `<span class="inline-block p-2 rounded-lg bg-warm-cream text-dark-green">Error loading client data: ${error.message}</span>`;
            messages.appendChild(errorMessage);
        }
    });

    // Save client info
    saveClientInfo.addEventListener('click', () => {
        console.log('Saving client info');
        if (!currentClientId) {
            alert('Please select a client');
            return;
        }
        const info = {
            name: document.getElementById('client-name').value,
            case_number: document.getElementById('client-case-number').value,
            email: document.getElementById('client-email').value,
            phone: document.getElementById('client-phone').value,
            case_type: document.getElementById('client-case-type').value,
            notes: document.getElementById('client-notes').value,
        };
        fetch(`/api/client/${currentClientId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
            },
            body: JSON.stringify(info),
            credentials: 'same-origin',
        }).then(response => response.json()).then(data => {
            if (data.success) {
                alert('Client info saved');
            } else {
                alert('Error saving client info');
            }
        }).catch(error => {
            console.error('Error saving client info:', error);
            alert('Failed to save client info');
        });
    });

    // New conversation
    newConversationButton.addEventListener('click', async () => {
        console.log('Starting new conversation');
        if (currentClientId) {
            try {
                const response = await fetch(`/api/new_conversation/${currentClientId}`, {
                    method: 'POST',
                    credentials: 'same-origin',
                    headers: {
                        'Content-Type': 'application/json',
                        'Accept': 'application/json',
                    },
                });
                if (!response.ok) throw new Error(`Failed to start new conversation: ${response.status} ${response.statusText}`);
                console.log('New conversation started');
                messages.innerHTML = '';
                historyCount = 0;
                historyBadge.textContent = '0';
                historyBadge.classList.remove('active');
                clientSelector.dispatchEvent(new Event('change')); // Refresh history
                messageInput.value = '';
                sendButton.classList.add('hidden'); // Hide send button on new conversation
            } catch (error) {
                console.error('Error starting new conversation:', error);
                alert('Failed to start new conversation');
            }
        } else {
            // If no client is selected, just clear the UI
            messages.innerHTML = '';
            historyCount = 0;
            historyBadge.textContent = '0';
            historyBadge.classList.remove('active');
            messageInput.value = '';
            sendButton.classList.add('hidden'); // Hide send button on new conversation
        }
    });

    // Prompt starters
    promptStarters.forEach(starter => {
        if (starter.id === 'reply-prompt') {
            starter.addEventListener('click', () => {
                console.log('Reply prompt clicked');
                replyPopup.classList.add('active');
                replyInput.focus();
            });
        } else if (starter.id === 'search-prompt') {
            starter.addEventListener('click', () => {
                console.log('Search prompt clicked');
                searchPopup.classList.add('active');
                searchInput.focus();
            });
        } else {
            starter.addEventListener('click', () => {
                const text = starter.querySelector('span').textContent;
                console.log('Prompt starter clicked:', text);
                messageInput.value = text;
                messageInput.focus();
                sendButton.classList.remove('hidden'); // Show send button when prompt starter is clicked
                // Do not hide prompt starters
            });
        }
    });

    replySubmit.addEventListener('click', () => {
        const replyText = replyInput.value.trim();
        console.log('Reply submitted:', replyText);
        if (replyText) {
            messageInput.value = `Draft a reply to: ${replyText}`;
            messageInput.focus();
            sendButton.classList.remove('hidden'); // Show send button when reply is submitted
            // Do not hide prompt starters
        }
        replyPopup.classList.remove('active');
        replyInput.value = '';
    });

    replyCancel.addEventListener('click', () => {
        console.log('Reply cancelled');
        replyPopup.classList.remove('active');
        replyInput.value = '';
    });

    searchSubmit.addEventListener('click', () => {
        const searchText = searchInput.value.trim();
        console.log('Search submitted:', searchText);
        if (searchText) {
            messageInput.value = `Search document for: ${searchText}`;
            messageInput.focus();
            sendButton.classList.remove('hidden'); // Show send button when search is submitted
            // Do not hide prompt starters
        }
        searchPopup.classList.remove('active');
        searchInput.value = '';
    });

    searchCancel.addEventListener('click', () => {
        console.log('Search cancelled');
        searchPopup.classList.remove('active');
        searchInput.value = '';
    });

    messageInput.addEventListener('input', () => {
        const hasText = messageInput.value.trim().length > 0;
        console.log('Input changed, hasText:', hasText, 'Current value:', messageInput.value);
        sendButton.classList.toggle('hidden', !hasText); // Show/hide send button based on input
        // Do not hide prompt starters
    });

    chatForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        console.log('Form submission triggered');
        const rawMessage = messageInput.value; // Capture raw value before trimming
        const message = rawMessage.trim();
        const file = fileInput.files[0];
        console.log('Submitting - Raw Message:', rawMessage, 'Trimmed Message:', message, 'File:', file ? file.name : 'None', 'Client ID:', currentClientId);

        if (!message && !file) {
            console.warn('No message or file provided, submission aborted');
            return;
        }

        sendButton.disabled = true;
        sendButton.innerHTML = `<svg class="w-6 h-6 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 12a8 8 0 018-8v8H4z" /></svg>`;

        // Always display user message if present, even if trimmed to empty
        if (rawMessage) {
            console.log('Displaying user message:', message || rawMessage);
            const userMessage = document.createElement('div');
            userMessage.className = 'mb-2 text-right';
            userMessage.innerHTML = `<span class="inline-block p-2 rounded-lg">${message || rawMessage}</span>`;
            messages.appendChild(userMessage);
            messages.scrollTop = messages.scrollHeight;
        }

        messageInput.value = ''; // Clear input after displaying
        sendButton.classList.add('hidden'); // Hide send button after submission

        // Handle file upload
        let fileContent = '';
        if (file) {
            console.log('Uploading file:', file.name);
            const formData = new FormData();
            formData.append('file', file);
            // Use currentClientId if set, otherwise default to "default_client"
            formData.append('client_id', currentClientId || "default_client");
            try {
                const uploadResponse = await fetch('/api/upload', {
                    method: 'POST',
                    body: formData,
                    credentials: 'same-origin',
                });
                if (!uploadResponse.ok) throw new Error(`File upload failed: ${uploadResponse.status} ${uploadResponse.statusText}`);
                const uploadData = await uploadResponse.json();
                console.log('File upload response:', uploadData);
                fileContent = uploadData.text;
                const fileMessage = document.createElement('div');
                fileMessage.className = 'mb-2 text-right';
                fileMessage.innerHTML = `<span class="inline-block p-2 rounded-lg">File Content: ${fileContent}</span>`;
                messages.appendChild(fileMessage);
                fileInput.value = '';
                documentCount++;
                documentsBadge.textContent = documentCount;
                documentsBadge.classList.add('active');
                clientSelector.dispatchEvent(new Event('change')); // Refresh documents
            } catch (error) {
                console.error('File upload error:', error);
                const errorMessage = document.createElement('div');
                errorMessage.className = 'mb-2 text-left';
                errorMessage.innerHTML = `<span class="inline-block p-2 rounded-lg bg-warm-cream text-dark-green">Error: ${error.message}</span>`;
                messages.appendChild(errorMessage);
                sendButton.disabled = false;
                sendButton.innerHTML = `<svg class="w-6 h-6 transform rotate-45" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" /></svg>`;
                return;
            }
        }

        // Send chat message only if there’s a message to send
        if (message) {
            const payload = {
                messages: [{ role: 'user', content: message + (fileContent ? `\n\nFile Content: ${fileContent}` : '') }],
                client_id: currentClientId || "default_client", // Default to "default_client" if none selected
            };
            try {
                console.log('Sending chat request to /api/chat with payload:', JSON.stringify(payload));
                const chatResponse = await fetch('/api/chat', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Accept': 'application/json',  // Expecting a single JSON response
                    },
                    body: JSON.stringify(payload),
                    credentials: 'same-origin',
                });

                if (!chatResponse.ok) {
                    const errorText = await chatResponse.text();
                    throw new Error(`Chat API error: ${chatResponse.status} ${chatResponse.statusText} - ${errorText}`);
                }

                console.log('Chat response received, processing as JSON');
                const data = await chatResponse.json();
                console.log('API response data:', data);

                let typingIndicator = document.createElement('div');
                typingIndicator.id = 'typing-indicator';
                typingIndicator.className = 'mb-2 text-left active';
                typingIndicator.innerHTML = `<span class="inline-block p-2 rounded-lg bg-light-cream text-dark-green">Typing...</span>`;
                messages.appendChild(typingIndicator);
                messages.scrollTop = messages.scrollHeight;

                let assistantMessage = document.createElement('div');
                assistantMessage.className = 'mb-2 text-left relative';
                let messageContent = '';
                assistantMessage.innerHTML = `
                    <div class="markdown-content inline-block p-2 rounded-lg bg-light-cream text-dark-green"></div>
                    <button class="copy-button absolute top-2 right-2">
                        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                        </svg>
                    </button>
                    <span class="copy-tooltip">Copied!</span>
                    <div class="follow-up-area mt-2">
                        <textarea class="w-full p-2 bg-light-cream border border-dark-green rounded-lg text-dark-green" placeholder="Refine or ask a follow-up question..."></textarea>
                        <button class="follow-up-button bg-warm-orange text-dark-green px-4 py-1 rounded-lg mt-2 hover:bg-bright-coral">Send Follow-Up</button>
                    </div>
                `;
                messages.appendChild(assistantMessage);
                const contentDiv = assistantMessage.querySelector('.markdown-content');
                const copyButton = assistantMessage.querySelector('.copy-button');
                const copyTooltip = assistantMessage.querySelector('.copy-tooltip');
                const followUpArea = assistantMessage.querySelector('.follow-up-area');
                const followUpButton = assistantMessage.querySelector('.follow-up-button');
                const followUpInput = assistantMessage.querySelector('textarea');

                copyButton.addEventListener('click', () => {
                    console.log('Copying message content');
                    navigator.clipboard.writeText(messageContent);
                    copyTooltip.classList.add('active');
                    setTimeout(() => copyTooltip.classList.remove('active'), 1000);
                    if (navigator.vibrate) navigator.vibrate(50); // Haptic feedback
                });

                followUpButton.addEventListener('click', () => {
                    console.log('Sending follow-up message');
                    if (followUpInput.value.trim()) {
                        messageInput.value = followUpInput.value;
                        followUpInput.value = '';
                        chatForm.dispatchEvent(new Event('submit'));
                    }
                });

                // Handle the non-streaming JSON response
                typingIndicator.remove();
                if (data.choices && data.choices.length > 0) {
                    messageContent = data.choices[0].delta.content || 'No content received';
                    contentDiv.innerHTML = marked.parse(messageContent);
                    messages.scrollTop = messages.scrollHeight;
                    followUpArea.classList.add('active');
                    historyCount += 2; // User + assistant message
                    historyBadge.textContent = historyCount;
                    historyBadge.classList.add('active');
                    clientSelector.dispatchEvent(new Event('change')); // Refresh history
                } else {
                    throw new Error('Invalid response format: No choices found');
                }
            } catch (error) {
                console.error('Chat submission failed:', error);
                const errorMessage = document.createElement('div');
                errorMessage.className = 'mb-2 text-left';
                errorMessage.innerHTML = `<span class="inline-block p-2 rounded-lg bg-warm-cream text-dark-green">Error: ${error.message}</span>`;
                messages.appendChild(errorMessage);
                if (typingIndicator) typingIndicator.remove();
            }
        }

        sendButton.disabled = false;
        sendButton.innerHTML = `<svg class="w-6 h-6 transform rotate-45" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" /></svg>`;
        messages.scrollTop = messages.scrollHeight;
    });
});
