// Clicking the toolbar icon opens the side panel, where the agent runs.
chrome.sidePanel
  .setPanelBehavior({ openPanelOnActionClick: true })
  .catch((err) => console.error(err));
