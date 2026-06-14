const API_BASE_URL = 'http://localhost:8000';

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

// State Variables
let currentClaimId = null;
let currentFeedbackVote = null;
let selectedFile = null;

// Demo Claims Prefills
const demos = {
    carrot: "New study finds drinking carrot juice cures cancer",
    eiffel: "Eiffel Tower to turn off lights due to Earth Day",
    workweek: "Canada legalizes four-day workweek"
};

document.getElementById('demo-carrot').addEventListener('click', () => prefillDemo('carrot'));
document.getElementById('demo-eiffel').addEventListener('click', () => prefillDemo('eiffel'));
document.getElementById('demo-workweek').addEventListener('click', () => prefillDemo('workweek'));

function prefillDemo(key) {
    claimTextInput.value = demos[key];
    claimUrlInput.value = "";
    removeSelectedFile();
    // Scroll to form smoothly
    analyzeForm.scrollIntoView({ behavior: 'smooth' });
}

// Drag & Drop / File selection logic
imageUploadInput.addEventListener('change', handleFileSelect);

dropzone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropzone.style.borderColor = '#2563eb';
    dropzone.style.backgroundColor = '#eff6ff';
});

dropzone.addEventListener('dragleave', () => {
    dropzone.style.borderColor = '#e5e7eb';
    dropzone.style.backgroundColor = '#f9fafb';
});

dropzone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropzone.style.borderColor = '#e5e7eb';
    dropzone.style.backgroundColor = '#f9fafb';

    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        imageUploadInput.files = e.dataTransfer.files;
        handleFileSelect();
    }
});

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

// Submit Form Action
analyzeForm.addEventListener('submit', async (e) => {
    e.preventDefault();

    const text = claimTextInput.value.trim();
    const url = claimUrlInput.value.trim();

    if (!text) return;

    // UI Loading State
    btnSubmit.disabled = true;
    spinner.style.display = 'inline-block';
    document.querySelector('.btn-text').textContent = 'Auditing...';

    try {
        let result;

        if (selectedFile) {
            // Case A: Analyze with image forensics
            const formData = new FormData();
            formData.append('file', selectedFile);
            formData.append('claim_text', text);

            const response = await fetch(`${API_BASE_URL}/analyze-image`, {
                method: 'POST',
                body: formData
            });

            if (!response.ok) throw new Error('Image analysis failed');
            result = await response.json();
        } else {
            // Case B: Text-only analysis
            const response = await fetch(`${API_BASE_URL}/analyze`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text, url: url || null })
            });

            if (!response.ok) throw new Error('Veracity audit request failed');
            result = await response.json();
        }

        displayResults(result);
        loadHistory(); // Reload history sidebar

    } catch (err) {
        console.error(err);
        alert(`Verification failed: ${err.message}. Ensure the backend is running on http://localhost:8000`);
    } finally {
        btnSubmit.disabled = false;
        spinner.style.display = 'none';
        document.querySelector('.btn-text').textContent = 'Audit Statement';
    }
});

// Render results
function displayResults(data) {
    currentClaimId = data.id;
    resetFeedback();

    resultCard.style.display = 'block';
    resultCard.scrollIntoView({ behavior: 'smooth' });

    // 1. Render Score Gauge
    const score = data.trust_score;
    scoreVal.textContent = score;

    // Circle circumference is 314.159 (2 * PI * r, where r=50)
    const offset = 314.159 - (score / 100) * 314.159;
    scoreRingFg.style.strokeDashoffset = offset;

    // Style verdict badge & progress ring colors
    verdictBadge.textContent = data.label;
    verdictBadge.className = 'verdict-badge'; // reset

    let colorVar = '#2563eb'; // Default primary blue

    if (score <= 30) {
        verdictBadge.classList.add('verdict-fake');
        colorVar = '#ef4444'; // Red
    } else if (score <= 60) {
        verdictBadge.classList.add('verdict-unverified');
        colorVar = '#eab308'; // Yellow/Amber
    } else {
        verdictBadge.classList.add('verdict-reliable');
        colorVar = '#10b981'; // Green
    }
    scoreRingFg.style.stroke = colorVar;

    // 2. Explanatory text
    explanationText.textContent = data.explanation;

    // 3. System badges
    badgeMethod.textContent = formatMethodName(data.method);
    badgeLang.textContent = formatLanguageName(data.language) + (data.translation_applied ? ' (Translated)' : '');

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
        elaNote.textContent = data.forensics.note || 'Error Level Analysis active.';

        // Progress color
        if (data.manipulation_score > 0.6) {
            elaProgressBar.style.backgroundColor = '#d946ef'; // Magenta warning
        } else {
            elaProgressBar.style.backgroundColor = '#a855f7'; // Purple normal
        }
    } else {
        imageElaResults.style.display = 'none';
    }
}

function formatMethodName(m) {
    if (m === 'finetuned-distilbert-liar') return 'Fine-Tuned DistilBERT';
    if (m === 'zero-shot-bart') return 'Zero-Shot BART Model';
    if (m === 'heuristic') return 'Heuristic Veracity Classifier';
    return m || 'Unknown Model';
}

function formatLanguageName(l) {
    const codes = { en: 'English', es: 'Spanish', fr: 'French', ur: 'Urdu', ar: 'Arabic' };
    return codes[l] || l.toUpperCase();
}

// Feedback Loop Actions
btnFeedbackAgree.addEventListener('click', () => setFeedbackVote('agree'));
btnFeedbackDisagree.addEventListener('click', () => setFeedbackVote('disagree'));

function setFeedbackVote(vote) {
    currentFeedbackVote = vote;
    feedbackStatus.style.display = 'none';

    btnFeedbackAgree.className = 'btn btn-feedback';
    btnFeedbackDisagree.className = 'btn btn-feedback';

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
        const response = await fetch(`${API_BASE_URL}/feedback`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                claim_id: currentClaimId,
                user_vote: currentFeedbackVote,
                comment: feedbackComment.value.trim() || null
            })
        });

        if (!response.ok) throw new Error('Failed to record feedback');

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
    btnFeedbackAgree.className = 'btn btn-feedback';
    btnFeedbackDisagree.className = 'btn btn-feedback';
    feedbackCommentContainer.style.display = 'none';
    feedbackStatus.style.display = 'none';
}

// Load Recent Audits Registry
async function loadHistory() {
    try {
        const response = await fetch(`${API_BASE_URL}/history`);
        if (!response.ok) throw new Error('History fetch failed');
        const data = await response.json();

        renderHistoryList(data);
    } catch (err) {
        console.error('Failed to load history:', err);
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

        // Verdict styling class
        let classColor = 'history-score-reliable';
        if (item.score <= 30) {
            classColor = 'history-score-fake';
        } else if (item.score <= 60) {
            classColor = 'history-score-unverified';
        }

        li.innerHTML = `
            <div class="history-item-claim" title="${escapeHtml(item.claim_text)}">${escapeHtml(item.claim_text)}</div>
            <div class="history-item-meta">
                <span class="${classColor}">${item.score}%</span>
                <span>${formatTime(item.created_at)}</span>
            </div>
        `;

        li.addEventListener('click', () => {
            claimTextInput.value = item.claim_text;
            claimUrlInput.value = item.source === 'Direct Entry' || item.source === 'Image Forensics Entry' ? '' : item.source;
            removeSelectedFile();
            // Trigger analysis (re-submits text to ensure fresh scoring/caching check)
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
        // SQLite timestamps default to UTC: YYYY-MM-DD HH:MM:SS
        // Replace space with T and append Z to format as ISO UTC
        const date = new Date(timestamp.replace(' ', 'T') + 'Z');
        if (isNaN(date.getTime())) return timestamp;
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) + ' ' + date.toLocaleDateString([], { month: 'short', day: 'numeric' });
    } catch {
        return timestamp;
    }
}

btnRefreshHistory.addEventListener('click', loadHistory);

// Initial Load
window.addEventListener('DOMContentLoaded', () => {
    loadHistory();
    // Poll history every 30 seconds
    setInterval(loadHistory, 30000);
});
