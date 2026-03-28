const API = 'http://localhost:7474'

async function init() {
  const dot = document.getElementById('dot')
  const statusText = document.getElementById('status-text')
  const stats = document.getElementById('stats')

  try {
    const res = await fetch(`${API}/api/health`, { signal: AbortSignal.timeout(2000) })
    const data = await res.json()
    dot.style.background = '#22c55e'
    statusText.textContent = 'Server online'

    // Try to get journal summary
    try {
      const jRes = await fetch(`${API}/api/journal?limit=1`, { signal: AbortSignal.timeout(2000) })
      const jData = await jRes.json()
      const s = jData.summary
      stats.innerHTML = `
        <div class="row"><span class="label">Win Rate</span><span class="value">${(s.win_rate * 100).toFixed(0)}%</span></div>
        <div class="row"><span class="label">Total Trades</span><span class="value">${s.total_resolved}</span></div>
        <div class="row"><span class="label">Avg R</span><span class="value ${s.avg_pnl_r >= 0 ? '' : 'offline'}">${s.avg_pnl_r >= 0 ? '+' : ''}${s.avg_pnl_r.toFixed(2)}R</span></div>
        <div class="row"><span class="label">AI Skipped</span><span class="value">${s.skipped_by_ai}</span></div>
      `
    } catch {
      // journal not available
    }
  } catch {
    dot.style.background = '#ef4444'
    statusText.innerHTML = '<span class="offline">Server offline</span>'
    stats.innerHTML = '<p style="color:#71717a;margin-top:8px;font-size:10px;">Start server:<br><code style="color:#f59e0b">py -m uvicorn server.main:app --port 7474</code></p>'
  }
}

document.getElementById('open-btn').addEventListener('click', () => {
  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    if (tabs[0]) chrome.sidePanel.open({ tabId: tabs[0].id })
  })
  window.close()
})

init()
