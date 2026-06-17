// popup.js - TruthLens Extension Logic

// State variables
let backendUrl = 'http://localhost:8000';
let currentClaimId = null;
let currentFeedbackVote = null;
let selectedFile = null;

// DOM Elements
const analyzeForm = document.getElementById('analyze-form');
const claimTextInput = document.getElementById('claim-text');
const claimUrlInput = document.getElementById('claim-url');
const imageUploadInput = document.getElementById('image-upload');
const dropzone = document.getElementById('dropzone');
const fileInfoBar = document.getElementById('file-info-bar');
const selectedFileName = document.getElementById('selected-file-name');
const btnRemoveFile = document.getElementById('btn-remove-file');
const btnSubmit = document.getElementById('btn-submit');
const spinner = document.getElementById('spinner');

const resultCard = document.getElementById('result-card');
const scoreRingFg = document.getElementById('score-ring-fg');
const scoreVal = document.getElementById('score-val');
const verdictBadge = document.getElementById('verdict-badge');
const explanationText = document.getElementById('explanation-text');
const badgeMethod = document.getElementById('badge-method');
const badgeLang = document.getElementById('badge-lang');
const badgeApi = document.getElementById('badge-api');

const factcheckReference = document.getElementById('factcheck-reference');
const refSnippet = document.getElementById('ref-snippet');
const refSourceName = document.getElementById('ref-source-name');
const refSourceLink = document.getElementById('ref-source-link');
const refOriginBadge = document.getElementById('ref-origin-badge');

const imageElaResults = document.getElementById('image-ela-results');
const elaProgressBar = document.getElementById('ela-progress-bar');
const elaScoreText = document.getElementById('ela-score-text');
const elaNote = document.getElementById('ela-note');

const btnFeedbackAgree = document.getElementById('btn-feedback-agree');
const btnFeedbackDisagree = document.getElementById('btn-feedback-disagree');
const feedbackCommentContainer = document.getElementById('feedback-comment-container');
const feedbackComment = document.getElementById('feedback-comment');
const btnSubmitFeedback = document.getElementById('btn-submit-feedback');
const feedbackStatus = document.getElementById('feedback-status');

const historyList = document.getElementById('history-list');
const btnRefreshHistory = document.getElementById('btn-refresh-history');

// Settings Elements
const btnToggleSettings = document.getElementById('btn-toggle-settings');
const settingsDrawer = document.getElementById('settings-drawer');
const inputBackendUrl = document.getElementById('settings-backend-url');
const btnSaveSettings = document.getElementById('btn-save-settings');
const btnCloseSettings = document.getElementById('btn-close-settings');

// 1. Settings Drawer Logic
btnToggleSettings.addEventListener('click', () => {
    const isVisible = settingsDrawer.style.display === 'block';
    settingsDrawer.style.display = isVisible ? 'none' : 'block';
});

btnCloseSettings.addEventListener('click', () => {
    settingsDrawer.style.display = 'none';
});

btnSaveSettings.addEventListener('click', () => {
    let url = inputBackendUrl.value.trim();
    if (!url) return;
    
    // Remove trailing slash if present
    if (url.endsWith('/')) {
        url = url.slice(0, -1);
    }
    
    chrome.storage.local.set({ backendUrl: url }, () => {
        backendUrl = url;
        inputBackendUrl.value = url;
        settingsDrawer.style.display = 'none';
        
        // Show indicator visual confirmation
        const dot = document.querySelector('.status-dot');
        dot.style.backgroundColor = '#10b981';
        dot.style.boxShadow = '0 0 8px #10b981';
        
        // Refresh history from new endpoint
        loadHistory();
    });
});

// 2. Tab Navigation
const tabLinks = document.querySelectorAll('.tab-link');
const tabContents = document.querySelectorAll('.tab-content');

tabLinks.forEach(link => {
    link.addEventListener('click', () => {
        const targetTab = link.getAttribute('data-tab');
        
        tabLinks.forEach(btn => btn.classList.remove('active'));
        tabContents.forEach(content => content.style.display = 'none');
        
        link.classList.add('active');
        document.getElementById(targetTab).style.display = 'flex';
        
        if (targetTab === 'tab-history') {
            loadHistory();
        }
    });
});

// 3. File upload/dropzone logic
dropzone.addEventListener('click', () => {
    imageUploadInput.click();
});

imageUploadInput.addEventListener('change', handleFileSelect);

// Handle file selection updates
function handleFileSelect() {
    if (imageUploadInput.files && imageUploadInput.files.length > 0) {
        selectedFile = imageUploadInput.files[0];
        selectedFileName.textContent = selectedFile.name;
        fileInfoBar.style.display = 'flex';
        document.querySelector('.dropzone-content').style.display = 'none';
    }
}

btnRemoveFile.addEventListener('click', (e) => {
    e.stopPropagation();
    removeSelectedFile();
});

function removeSelectedFile() {
    selectedFile = null;
    imageUploadInput.value = '';
    fileInfoBar.style.display = 'none';
    document.querySelector('.dropzone-content').style.display = 'flex';
}

// 4. Submit claim for audit
analyzeForm.addEventListener('submit', async (e) => {
    e.preventDefault();

    const text = claimTextInput.value.trim();
    const url = claimUrlInput.value.trim();

    if (!text) return;

    // UI Loading State
    btnSubmit.disabled = true;
    spinner.style.display = 'inline-block';
    document.querySelector('.btn-text').textContent = 'Auditing...';
    resultCard.style.display = 'none';

    try {
        let result;

        if (selectedFile) {
            // Case A: Analyze with image forensics
            const formData = new FormData();
            formData.append('file', selectedFile);
            formData.append('claim_text', text);

            const response = await fetch(`${backendUrl}/analyze-image`, {
                method: 'POST',
                body: formData
            });

            if (!response.ok) throw new Error('Image ELA forensics request failed');
            result = await response.json();
        } else {
            // Case B: Text-only analysis
            const response = await fetch(`${backendUrl}/analyze`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text, url: url || null })
            });

            if (!response.ok) throw new Error('Text veracity audit request failed');
            result = await response.json();
        }

        displayResults(result);
        removeSelectedFile();
    } catch (err) {
        console.error(err);
        alert(`Audit connection failed: ${err.message}. Confirm the TruthLens backend server is running at ${backendUrl}`);
    } finally {
        btnSubmit.disabled = false;
        spinner.style.display = 'none';
        document.querySelector('.btn-text').textContent = 'Audit Statement';
    }
});

// Render results inside popup card
function displayResults(data) {
    currentClaimId = data.id;
    resetFeedback();

    resultCard.style.display = 'block';

    // 1. Render Score Gauge
    const score = data.trust_score;
    scoreVal.textContent = score;

    // Circle circumference is 213.6 (2 * PI * r, where r=34)
    const offset = 213.6 - (score / 100) * 213.6;
    scoreRingFg.style.strokeDashoffset = offset;

    // Style verdict badge & progress ring colors
    verdictBadge.textContent = data.label;
    verdictBadge.className = 'verdict-badge'; // reset

    let colorVar = '#22d3ee'; // Default neon cyan

    if (score <= 30) {
        verdictBadge.classList.add('verdict-fake');
        colorVar = '#ef4444'; // Red
    } else if (score <= 60) {
        verdictBadge.classList.add('verdict-unverified');
        colorVar = '#f59e0b'; // Amber/Yellow
    } else {
        verdictBadge.classList.add('verdict-reliable');
        colorVar = '#10b981'; // Green
    }
    scoreRingFg.style.stroke = colorVar;

    // 2. Explanatory text
    explanationText.innerHTML = data.explanation.replace(/\n\n/g, '<br/><br/>');

    // 3. System badges
    badgeMethod.textContent = formatMethodName(data.method);
    badgeLang.textContent = formatLanguageName(data.language) + (data.translation_applied ? ' (Translated)' : '');
    updateApiStatusBadge(data.factcheck_api_status);

    // 4. Reference Factcheck
    if (data.factcheck_match) {
        factcheckReference.style.display = 'block';
        refSnippet.textContent = `"${data.factcheck_match.explanation_snippet}"`;
        refSourceName.textContent = data.factcheck_match.source_name;
        refSourceLink.href = data.factcheck_match.source_url || '#';
        refSourceLink.style.display = data.factcheck_match.source_url ? 'inline' : 'none';
        refOriginBadge.textContent = `Origin: ${data.factcheck_match.origin === 'google-factcheck-api' ? 'Google Fact Check Tools API' : 'Local Seed Database'}`;
    } else {
        factcheckReference.style.display = 'none';
    }

    // 5. Image forensics
    if (data.manipulation_score !== undefined && data.forensics) {
        imageElaResults.style.display = 'block';
        const manipulationPct = (data.manipulation_score * 100).toFixed(1);
        elaProgressBar.style.width = `${manipulationPct}%`;
        elaScoreText.textContent = `${manipulationPct}%`;
        elaNote.textContent = data.forensics.note || 'Error Level Analysis complete.';

        // Progress color
        if (data.manipulation_score > 0.6) {
            elaProgressBar.style.backgroundColor = '#d946ef'; // Magenta
        } else {
            elaProgressBar.style.backgroundColor = '#c084fc'; // Purple
        }
    } else {
        imageElaResults.style.display = 'none';
    }
}

function formatMethodName(m) {
    if (m === 'finetuned-distilbert-liar') return 'DistilBERT';
    if (m === 'zero-shot-bart') return 'Zero-Shot BART';
    if (m === 'heuristic') return 'Heuristics';
    return m || 'Classifier';
}

function formatLanguageName(l) {
    const codes = { en: 'English', es: 'Spanish', fr: 'French', ur: 'Urdu', ar: 'Arabic' };
    return codes[l] || l.toUpperCase();
}

function updateApiStatusBadge(status) {
    badgeApi.className = 'badge badge-api';
    if (status === 'active') {
        badgeApi.textContent = 'Google API';
        badgeApi.classList.add('badge-api-active');
    } else if (status === 'failed') {
        badgeApi.textContent = 'API Error';
        badgeApi.classList.add('badge-api-failed');
    } else {
        badgeApi.textContent = 'Local Seeds';
        badgeApi.classList.add('badge-api-no-key');
    }
}

// 5. Feedback Actions
btnFeedbackAgree.addEventListener('click', () => setFeedbackVote('agree'));
btnFeedbackDisagree.addEventListener('click', () => setFeedbackVote('disagree'));

function setFeedbackVote(vote) {
    currentFeedbackVote = vote;
    feedbackStatus.style.display = 'none';

    btnFeedbackAgree.className = 'btn btn-feedback btn-xs';
    btnFeedbackDisagree.className = 'btn btn-feedback btn-xs';

    if (vote === 'agree') {
        btnFeedbackAgree.classList.add('active-agree');
        feedbackCommentContainer.style.display = 'flex';
    } else if (vote === 'disagree') {
        btnFeedbackDisagree.classList.add('active-disagree');
        feedbackCommentContainer.style.display = 'flex';
    }
}

btnSubmitFeedback.addEventListener('click', async () => {
    if (!currentClaimId || !currentFeedbackVote) return;
    btnSubmitFeedback.disabled = true;

    try {
        const response = await fetch(`${backendUrl}/feedback`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                claim_id: currentClaimId,
                user_vote: currentFeedbackVote,
                comment: feedbackComment.value.trim() || null
            })
        });

        if (!response.ok) throw new Error('Feedback log request failed');

        feedbackCommentContainer.style.display = 'none';
        feedbackStatus.style.display = 'block';
    } catch (err) {
        console.error(err);
        alert('Could not submit feedback.');
    } finally {
        btnSubmitFeedback.disabled = false;
    }
});

function resetFeedback() {
    currentFeedbackVote = null;
    feedbackComment.value = '';
    btnFeedbackAgree.className = 'btn btn-feedback btn-xs';
    btnFeedbackDisagree.className = 'btn btn-feedback btn-xs';
    feedbackCommentContainer.style.display = 'none';
    feedbackStatus.style.display = 'none';
}

// 6. Audit Registry History Load
async function loadHistory() {
    try {
        const response = await fetch(`${backendUrl}/history`);
        if (!response.ok) throw new Error('Failed to load history');
        const data = await response.json();
        renderHistoryList(data);
        
        // Mark status dot green
        const dot = document.querySelector('.status-dot');
        dot.style.backgroundColor = '#10b981';
        dot.style.boxShadow = '0 0 8px #10b981';
    } catch (err) {
        console.warn('Backend server unreachable:', err);
        // Mark status dot red (offline)
        const dot = document.querySelector('.status-dot');
        dot.style.backgroundColor = '#ef4444';
        dot.style.boxShadow = '0 0 8px #ef4444';
        
        historyList.innerHTML = '<li class="history-placeholder">Server offline. Check Settings and try again.</li>';
    }
}

function renderHistoryList(items) {
    historyList.innerHTML = '';

    if (items.length === 0) {
        historyList.innerHTML = '<li class="history-placeholder">No audit entries found.</li>';
        return;
    }

    items.forEach(item => {
        const li = document.createElement('li');
        li.className = 'history-item';

        let classColor = 'history-score-reliable';
        if (item.score <= 30) {
            classColor = 'history-score-fake';
        } else if (item.score <= 60) {
            classColor = 'history-score-unverified';
        }

        li.innerHTML = `
            <div class="history-item-claim" title="${escapeHtml(item.claim_text)}">${escapeHtml(item.claim_text)}</div>
            <div class="history-item-meta">
                <span class="${classColor}">${item.score}% Veracity</span>
                <span>${formatTime(item.created_at)}</span>
            </div>
        `;

        li.addEventListener('click', () => {
            claimTextInput.value = item.claim_text;
            claimUrlInput.value = item.source === 'Direct Entry' || item.source === 'Image Forensics Entry' ? '' : item.source;
            removeSelectedFile();
            
            // Switch tab back to console
            const consoleTabLink = document.querySelector('[data-tab="tab-console"]');
            consoleTabLink.click();
            
            // Trigger analyze form submission
            analyzeForm.dispatchEvent(new Event('submit'));
        });

        historyList.appendChild(li);
    });
}

function escapeHtml(str) {
    return str
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function formatTime(timestamp) {
    try {
        const date = new Date(timestamp.replace(' ', 'T') + 'Z');
        if (isNaN(date.getTime())) return timestamp;
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) + ' ' + date.toLocaleDateString([], { month: 'short', day: 'numeric' });
    } catch {
        return timestamp;
    }
}

btnRefreshHistory.addEventListener('click', loadHistory);

// 7. Initial Load and Chrome Selection pre-fill
window.addEventListener('DOMContentLoaded', () => {
    // Read backendUrl and pre-filled text from storage
    chrome.storage.local.get({ 
        backendUrl: 'http://localhost:8000',
        lastSelectedText: '' 
    }, (settings) => {
        backendUrl = settings.backendUrl;
        inputBackendUrl.value = backendUrl;
        
        loadHistory();
        
        // Check if selection auditing was requested via context menu
        if (settings.lastSelectedText) {
            claimTextInput.value = settings.lastSelectedText;
            
            // Remove text from storage so it doesn't prefill next time
            chrome.storage.local.remove('lastSelectedText');
            
            // Automatically submit analysis
            analyzeForm.dispatchEvent(new Event('submit'));
        }
    });
});
