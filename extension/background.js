/**
 * Background service worker — handles:
 * 1. Opening the side panel when the action button is clicked
 * 2. Periodic health-check ping to the local bot server
 * 3. Badge update when new signals arrive
 */

const API = 'http://localhost:7474'

// Open side panel on toolbar click
chrome.action.onClicked.addListener((tab) => {
  chrome.sidePanel.open({ tabId: tab.id })
})

// Enable side panel for all URLs
chrome.runtime.onInstalled.addListener(() => {
  chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true })

  // Set up a repeating alarm to ping the server every 2 minutes
  chrome.alarms.create('server-ping', { periodInMinutes: 2 })
})

// Health-check alarm handler
chrome.alarms.onAlarm.addListener(async (alarm) => {
  if (alarm.name !== 'server-ping') return
  try {
    const res = await fetch(`${API}/api/health`, { signal: AbortSignal.timeout(3000) })
    const data = await res.json()
    if (data.status === 'ok') {
      chrome.action.setBadgeText({ text: '●' })
      chrome.action.setBadgeBackgroundColor({ color: '#22c55e' })
    }
  } catch {
    // Server offline
    chrome.action.setBadgeText({ text: '!' })
    chrome.action.setBadgeBackgroundColor({ color: '#ef4444' })
  }
})

// Listen for symbol auto-detection messages from content scripts
chrome.runtime.onMessage.addListener((message) => {
  if (message.type === 'SYMBOL_DETECTED') {
    // Forward to the side panel via storage
    chrome.storage.session.set({ detectedSymbol: message.symbol })
  }
})
