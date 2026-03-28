import { useStore } from '../store/useStore'
import type { TabId } from '../types'

const TABS: { id: TabId; label: string; icon: string }[] = [
  { id: 'signals',  label: 'Signals',  icon: '⚡' },
  { id: 'context',  label: 'Context',  icon: '🌐' },
  { id: 'journal',  label: 'Journal',  icon: '📋' },
]

export function Tabs() {
  const { activeTab, setTab, signals } = useStore()

  return (
    <div className="flex border-b border-zinc-800 bg-zinc-950">
      {TABS.map((tab) => (
        <button
          key={tab.id}
          onClick={() => setTab(tab.id)}
          className={`flex-1 flex items-center justify-center gap-1 py-2 text-[11px] font-semibold transition-colors relative
            ${activeTab === tab.id
              ? 'text-emerald-400 border-b-2 border-emerald-500'
              : 'text-zinc-500 hover:text-zinc-300'
            }`}
        >
          <span>{tab.icon}</span>
          <span>{tab.label}</span>
          {tab.id === 'signals' && signals.length > 0 && (
            <span className="ml-0.5 bg-emerald-600 text-white text-[9px] rounded-full px-1 leading-tight">
              {signals.length}
            </span>
          )}
        </button>
      ))}
    </div>
  )
}
