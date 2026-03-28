/**
 * Content script — auto-detects the ticker symbol on financial websites
 * and sends it to the background worker for the side panel to pick up.
 *
 * Supported sites: TradingView, Yahoo Finance, Finviz, StockAnalysis
 */

(function () {
  const hostname = window.location.hostname

  function detect() {
    let symbol = null

    if (hostname.includes('tradingview.com')) {
      // TradingView: symbol is in the page title  "AAPL · TradingView"
      const match = document.title.match(/^([A-Z0-9.\-]+)\s*[·—]/)
      if (match) symbol = match[1]
    } else if (hostname.includes('finance.yahoo.com')) {
      // Yahoo Finance: /quote/AAPL/
      const match = window.location.pathname.match(/\/quote\/([A-Z0-9.\-]+)/)
      if (match) symbol = match[1]
    } else if (hostname.includes('finviz.com')) {
      // Finviz: ?t=AAPL
      const params = new URLSearchParams(window.location.search)
      symbol = params.get('t')
    } else if (hostname.includes('stockanalysis.com')) {
      // StockAnalysis: /stocks/AAPL/
      const match = window.location.pathname.match(/\/stocks\/([a-z0-9.\-]+)/)
      if (match) symbol = match[1].toUpperCase()
    }

    if (symbol) {
      chrome.runtime.sendMessage({ type: 'SYMBOL_DETECTED', symbol })
    }
  }

  // Run on load and on navigation changes
  detect()
  const observer = new MutationObserver(() => detect())
  observer.observe(document.title
    ? document.querySelector('title') ?? document.head
    : document.head,
    { childList: true, subtree: true, characterData: true }
  )
})()
