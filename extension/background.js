// background.js - Service Worker for TruthLens Extension

chrome.runtime.onInstalled.addListener(() => {
  // Create a context menu option for highlighted text selection
  chrome.contextMenus.create({
    id: "auditClaim",
    title: "Audit with TruthLens",
    contexts: ["selection"]
  });
  console.log("TruthLens Context Menu registered successfully.");
});

// Listen for context menu click events
chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId === "auditClaim" && info.selectionText && tab.id) {
    const textToAnalyze = info.selectionText.trim();
    
    // Save text in local storage to pre-fill the popup dashboard if opened
    chrome.storage.local.set({ lastSelectedText: textToAnalyze }, () => {
      // Send a message to the active tab's content script to inject the floating audit panel
      chrome.tabs.sendMessage(tab.id, {
        action: "auditSelectedText",
        text: textToAnalyze
      }).catch((err) => {
        console.warn("Content script not active or loaded on this tab yet. Injecting fallback details...", err);
      });
    });
  }
});
