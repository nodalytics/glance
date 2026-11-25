
import {
  Spade,
  LayoutDashboard,
  Images,
  Users,
  ScanLine,
  FileJson,
  Settings,
  ShieldCheck,
  X,
} from 'lucide-react'

import type {
  Page,
  ConnectionStatus,
} from '../../types/navigation'

interface SidebarProps {
  activePage: Page
  onNavigate: (page: Page) => void
  status: ConnectionStatus
  version: string
  mobileOpen: boolean
  onClose: () => void
}

const navigation = [
  {
    id: 'dashboard',
    label: 'Dashboard',
    icon: LayoutDashboard,
  },
  {
    id: 'screenshots',
    label: 'Screenshots',
    icon: Images,
  },
  {
    id: 'players',
    label: 'Players',
    icon: Users,
  },
  {
    id: 'recognition',
    label: 'Recognition',
    icon: ScanLine,
  },
  {
    id: 'json',
    label: 'JSON Data',
    icon: FileJson,
  },
  {
    id: 'settings',
    label: 'Settings',
    icon: Settings,
  },
] as const

export default function Sidebar({
  activePage,
  onNavigate,
  status,
  version,
  mobileOpen,
  onClose,
}: SidebarProps) {
  return (
    <>
      {mobileOpen && (
        <button
          aria-label="Close navigation"
          className="fixed inset-0 z-40 bg-black/60 lg:hidden"
          onClick={onClose}
        />
      )}

      <aside
        className={`
          fixed inset-y-0 left-0 z-50
          flex w-64 flex-col
          border-r border-slate-800
          bg-[#111827]
          transition-transform duration-200
          lg:translate-x-0
          ${
            mobileOpen
              ? 'translate-x-0'
              : '-translate-x-full'
          }
        `}
      >
        <div className="flex items-center gap-3 border-b border-slate-800 px-5 py-6">
          <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/10 p-3">
            <Spade
              size={25}
              className="text-emerald-400"
            />
          </div>

          <div className="min-w-0">
            <h1 className="text-sm font-bold tracking-wide">
              POKER CONNECTOR
            </h1>

            <p className="mt-1 text-xs text-slate-400">
              Analysis Studio
            </p>
          </div>

          <button
            aria-label="Close sidebar"
            onClick={onClose}
            className="ml-auto text-slate-400 lg:hidden"
          >
            <X size={20} />
          </button>
        </div>

        <nav
          aria-label="Main navigation"
          className="flex-1 overflow-y-auto px-3 py-6"
        >
          <p className="mb-3 px-3 text-[10px] font-semibold uppercase tracking-widest text-slate-500">
            Workspace
          </p>

          <div className="space-y-1">
            {navigation.map((item) => {
              const Icon = item.icon

              const active =
                activePage === item.id

              return (
                <button
                  key={item.id}
                  aria-current={
                    active ? 'page' : undefined
                  }
                  onClick={() => {
                    onNavigate(item.id)
                    onClose()
                  }}
                  className={`
                    flex w-full items-center gap-3
                    rounded-lg px-3 py-3
                    text-left text-sm
                    transition-colors
                    ${
                      active
                        ? 'bg-emerald-500/10 font-medium text-emerald-400'
                        : 'text-slate-400 hover:bg-slate-800 hover:text-white'
                    }
                  `}
                >
                  <Icon size={19} />

                  {item.label}

                  {active && (
                    <span className="ml-auto h-2 w-2 rounded-full bg-emerald-400" />
                  )}
                </button>
              )
            })}
          </div>
        </nav>

        <div className="border-t border-slate-800 p-4">
          <div className="rounded-xl border border-slate-800 bg-[#0b1018] p-4">
            <p className="mb-3 text-[10px] font-semibold uppercase tracking-widest text-slate-500">
              System status
            </p>

            <div className="flex items-center gap-2 text-sm">
              <span
                className={`h-2 w-2 rounded-full ${
                  status === 'connected'
                    ? 'bg-emerald-400'
                    : status === 'checking'
                      ? 'bg-amber-400'
                      : 'bg-red-400'
                }`}
              />

              {status === 'connected'
                ? 'API Online'
                : status === 'checking'
                  ? 'Checking API'
                  : 'API Offline'}
            </div>

            <div className="mt-3 flex items-center gap-2 text-xs text-slate-400">
              <ShieldCheck size={15} />
              Offline processing
            </div>

            <p className="mt-3 text-xs text-slate-500">
              Version {version}
            </p>
          </div>
        </div>
      </aside>
    </>
  )
}
