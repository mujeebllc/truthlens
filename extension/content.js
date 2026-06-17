// content.js - TruthLens Content Script

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === "auditSelectedText") {
    createOrUpdateOverlay(message.text);
  }
  return true;
});

function createOrUpdateOverlay(text) {
  let root = document.getElementById("truthlens-root");
  if (!root) {
    root = document.createElement("div");
    root.id = "truthlens-root";
    document.body.appendChild(root);
  }
  
  const shadow = root.shadowRoot || root.attachShadow({ mode: "open" });
  shadow.innerHTML = ""; // Clear existing contents
  
  // Link extension CSS
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = chrome.runtime.getURL("content.css");
  shadow.appendChild(link);
  
  // Create overlay container
  const container = document.createElement("div");
  container.className = "truthlens-overlay-card animate-fade-in";
  shadow.appendChild(container);
  
  // Build interior structure
  container.innerHTML = `
    <div class="truthlens-header">
      <div class="truthlens-logo">
        <span class="logo-emoji">🔍</span>
        <div class="logo-text">
          <h3>TruthLens</h3>
          <span>Autonomous Audit Node</span>
        </div>
      </div>
      <button class="truthlens-close-btn" aria-label="Close panel">&times;</button>
    </div>
    <div class="truthlens-body">
      <div class="truthlens-claim-box">
        <strong>Auditing Claim:</strong>
        <p class="claim-snippet" id="tl-claim-snippet"></p>
      </div>
      
      <div class="truthlens-loader-container" id="tl-loader">
        <div class="truthlens-spinner"></div>
        <p class="truthlens-loading-text">Auditing statement against multi-tiered NLP classifiers and verification registry...</p>
      </div>
      
      <div class="truthlens-result" id="tl-result" style="display: none;">
        <div class="truthlens-score-row">
          <div class="truthlens-gauge">
            <svg viewBox="0 0 100 100">
              <circle cx="50" cy="50" r="40" class="gauge-bg"></circle>
              <circle cx="50" cy="50" r="40" class="gauge-fg" id="tl-gauge-fg" stroke-dasharray="251.2" stroke-dashoffset="251.2"></circle>
            </svg>
            <div class="gauge-value" id="tl-score-val">0</div>
          </div>
          <div class="truthlens-verdict-info">
            <span class="verdict-label" id="tl-verdict-label">Analyzing...</span>
            <span class="method-badge" id="tl-method-badge">-</span>
          </div>
        </div>
        
        <div class="truthlens-details">
          <h4>Contextual Explanation</h4>
          <div class="explanation-box">
            <p id="tl-explanation"></p>
          </div>
          
          <div class="truthlens-factcheck" id="tl-factcheck" style="display: none;">
            <h5>🔍 Verified Fact-Check Match</h5>
            <p class="fc-snippet" id="tl-fc-snippet"></p>
            <p class="fc-meta">Source: <a href="#" target="_blank" id="tl-fc-link" class="fc-link"></a></p>
          </div>
        </div>
      </div>
      
      <div class="truthlens-error" id="tl-error" style="display: none;">
        <span class="error-emoji">⚠️</span>
        <p id="tl-error-msg">Failed to connect to backend server. Make sure TruthLens is running locally at http://localhost:8000.</p>
      </div>
    </div>
    <div class="truthlens-footer">
      <span>TruthLens AI Network</span>
    </div>
  `;
  
  // Set the claims text snippet (truncate if too long)
  const displaySnippet = text.length > 180 ? text.slice(0, 177) + "..." : text;
  shadow.getElementById("tl-claim-snippet").textContent = `"${displaySnippet}"`;
  
  // Event listeners
  container.querySelector(".truthlens-close-btn").addEventListener("click", () => {
    root.remove();
  });
  
  // Retrieve backend configuration URL (defaults to localhost:8000)
  chrome.storage.local.get({ backendUrl: "http://localhost:8000" }, (settings) => {
    const backendUrl = settings.backendUrl;
    
    // Perform audit fetch
    fetch(`${backendUrl}/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: text })
    })
    .then(res => {
      if (!res.ok) throw new Error(`HTTP Error ${res.status}`);
      return res.json();
    })
    .then(data => {
      // Hide loader
      shadow.getElementById("tl-loader").style.display = "none";
      shadow.getElementById("tl-result").style.display = "block";
      
      // Update score
      const score = data.trust_score;
      shadow.getElementById("tl-score-val").textContent = score;
      
      // Stroke dashoffset logic for gauge
      const circumference = 2 * Math.PI * 40;
      const offset = circumference - (score / 100) * circumference;
      const gaugeFg = shadow.getElementById("tl-gauge-fg");
      gaugeFg.style.strokeDashoffset = offset;
      
      // Set coloring class depending on score
      let colorClass = "suspicious";
      if (score >= 70) colorClass = "reliable";
      else if (score >= 40) colorClass = "caution";
      gaugeFg.setAttribute("class", `gauge-fg ${colorClass}`);
      
      // Verdict label & Method
      const labelEl = shadow.getElementById("tl-verdict-label");
      labelEl.textContent = data.label;
      labelEl.className = `verdict-label ${colorClass}`;
      
      shadow.getElementById("tl-method-badge").textContent = `Classifier Method: ${data.method}`;
      
      // Explanation (handle newline spacing nicely)
      const explanationText = data.explanation.replace(/\n\n/g, "<br/><br/>");
      shadow.getElementById("tl-explanation").innerHTML = explanationText;
      
      // Factcheck details if matching Snopes/Factcheck
      if (data.factcheck_match) {
        shadow.getElementById("tl-factcheck").style.display = "block";
        shadow.getElementById("tl-fc-snippet").textContent = data.factcheck_match.explanation_snippet;
        const linkEl = shadow.getElementById("tl-fc-link");
        linkEl.textContent = `${data.factcheck_match.source_name} ↗`;
        linkEl.href = data.factcheck_match.source_url;
      }
    })
    .catch(err => {
      shadow.getElementById("tl-loader").style.display = "none";
      shadow.getElementById("tl-error").style.display = "block";
      shadow.getElementById("tl-error-msg").textContent = `Auditing Failed: ${err.message}. Make sure the TruthLens server is running locally at ${backendUrl}.`;
    });
  });
}
