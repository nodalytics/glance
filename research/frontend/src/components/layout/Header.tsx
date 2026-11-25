
import {
  Menu,
  CircleCheck,
  CircleX,
  LoaderCircle,
  ShieldCheck,
} from 'lucide-react'

import type {
  ConnectionStatus,
} from '../../types/navigation'

interface HeaderProps {
  title: string
  status: ConnectionStatus
  busy: boolean
  onMenuClick: () => void
}

export default function Header({
  title,
  status,
  busy,
  onMenuClick,
}: HeaderProps) {
  return (
    <header className="sticky top-0 z-30 flex min-h-18 items-center justify-between gap-4 border-b border-slate-800 bg-[#111827]/95 px-4 backdrop-blur md:px-6">

      <div className="flex items-center gap-3">
        <button
          aria-label="Open navigation"
          onClick={onMenuClick}
          className="rounded-lg p-2 text-slate-400 hover:bg-slate-800 lg:hidden"
        >
          <Menu size={22} />
        </button>

        <div>
          <p className="hidden text-xs text-slate-500 sm:block">
            Workspace
          </p>

          <h2 className="text-base font-semibold">
            {title}
          </h2>
        </div>
      </div>

      <div className="flex items-center gap-3">

        {busy && (
          <span className="flex items-center gap-2 text-xs text-amber-400">
            <LoaderCircle
              size={15}
              className="animate-spin"
            />
            Processing
          </span>
        )}

        <div className="hidden items-center gap-2 rounded-full border border-slate-700 px-3 py-2 text-xs text-slate-400 md:flex">
          <ShieldCheck
            size={15}
            className="text-emerald-400"
          />
          Offline Mode
        </div>

        <div
          role="status"
          className="flex items-center gap-2 rounded-full border border-slate-800 bg-[#0b1018] px-3 py-2 text-xs"
        >
          {status === 'connected' && (
            <>
              <CircleCheck
                size={15}
                className="text-emerald-400"
              />
              <span className="text-emerald-400">
                Connected
              </span>
            </>
          )}

          {status === 'checking' && (
            <>
              <LoaderCircle
                size={15}
                className="animate-spin text-amber-400"
              />
              <span className="text-amber-400">
                Checking
              </span>
            </>
          )}

          {status === 'disconnected' && (
            <>
              <CircleX
                size={15}
                className="text-red-400"
              />
              <span className="text-red-400">
                Disconnected
              </span>
            </>
          )}
        </div>
      </div>
    </header>
  )
}
