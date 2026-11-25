
import { useState } from 'react'

import {
  Images,
  
  ScanLine,
  FileJson,
} from 'lucide-react'

import Sidebar from './components/layout/Sidebar'

import ProcessingBanner from './components/dashboard/ProcessingBanner'

import Header from './components/layout/Header'

import Dashboard from './pages/Dashboard'

import Players from './pages/Players'

import Settings from './pages/Settings'

import ScreenshotUpload from './components/dashboard/ScreenshotUpload'

import {
  useBackendHealth,
} from './hooks/useBackendHealth'

import {
  useScreenshotAnalysis,
} from './hooks/useScreenshotAnalysis'

import type {
  Page,
} from './types/navigation'

const pageTitles: Record<Page, string> = {
  dashboard: 'Dashboard',
  screenshots: 'Screenshots',
  players: 'Players',
  recognition: 'Recognition',
  json: 'JSON Data',
  settings: 'Settings',
}

const placeholderPages = {
  recognition: {
    icon: ScanLine,
    description:
      'Card recognition details and validation results will appear here.',
  },

  json: {
    icon: FileJson,
    description:
      'Inspect and export the structured API response.',
  },
}

function App() {
  const [activePage, setActivePage] =
    useState<Page>('dashboard')

  const [mobileOpen, setMobileOpen] =
    useState(false)

  const [selectedFile, setSelectedFile] =
    useState<File | null>(null)

  const {
    status,
    health,
  } = useBackendHealth()

  const {
    state: analysis,
    analyze,
    reset,
    isProcessing,
  } = useScreenshotAnalysis()

  const backendBusy =
    health?.busy ?? false

  // ----------------------------------------------
  // SHARED FILE SELECTION
  // ----------------------------------------------

  function handleFileChange(
    file: File | null
  ) {
    if (isProcessing) {
      return
    }

    reset()

    setSelectedFile(file)
  }

  // ----------------------------------------------
  // SCREENSHOT SUBMISSION
  // ----------------------------------------------

  function handleAnalyze() {
    if (
      !selectedFile ||
      isProcessing ||
      backendBusy ||
      status !== 'connected'
    ) {
      return
    }

    void analyze(selectedFile)
  }

  // ----------------------------------------------
  // SHARED SCREENSHOT PROPERTIES
  // ----------------------------------------------

  const screenshotProps = {
    file: selectedFile,

    onFileChange: handleFileChange,

    onAnalyze: handleAnalyze,

    analysis,

    connectionStatus: status,

    backendBusy,
  }

  // ----------------------------------------------
  // PAGE RENDERING
  // ----------------------------------------------

  function renderPage() {
    if (activePage === 'dashboard') {
      return (
        <Dashboard
          {...screenshotProps}
        />
      )
    }

    if (activePage === 'screenshots') {
      return (
        <div className="space-y-6">

          <div>

            <div className="mb-3 flex items-center gap-2 text-emerald-400">

              <Images size={20} />

              <span className="text-xs font-semibold uppercase tracking-widest">
                Screenshot workspace
              </span>

            </div>

            <h1 className="text-3xl font-semibold">
              Screenshots
            </h1>

            <p className="mt-2 text-sm text-slate-400">
              Select and analyze saved screenshots.
            </p>

          </div>

          <ScreenshotUpload
            {...screenshotProps}
          />

        </div>
      )
    }

    if (activePage === 'players') {
  return (
    <Players
      result={analysis.result}
      onViewDashboard={() => {
        setActivePage('dashboard')
      }}
    />
  )
}

    if (activePage === 'settings') {
      return <Settings />
    }

    const page =
      placeholderPages[activePage]

    const Icon = page.icon

    return (
      <div className="space-y-6">

        <h1 className="text-3xl font-semibold">
          {pageTitles[activePage]}
        </h1>

        <section className="rounded-xl border border-slate-800 bg-[#111827] px-6 py-20 text-center">

          <div className="mx-auto mb-5 flex h-16 w-16 items-center justify-center rounded-2xl bg-emerald-500/10">

            <Icon
              size={30}
              className="text-emerald-400"
            />

          </div>

          <h2 className="text-xl font-semibold">
            {pageTitles[activePage]}
          </h2>

          <p className="mx-auto mt-3 max-w-md text-sm leading-relaxed text-slate-400">
            {page.description}
          </p>

          {analysis.result ? (
            <p className="mt-5 text-xs text-emerald-400">
              Analysis data available.
              Detailed view integration pending.
            </p>
          ) : (
            <p className="mt-5 text-xs text-slate-500">
              No analysis result available.
            </p>
          )}

          <button
            onClick={() => {
              setActivePage('dashboard')
            }}
            className="mt-6 rounded-lg border border-slate-700 px-4 py-2 text-sm text-slate-300 hover:bg-slate-800"
          >
            Return to Dashboard
          </button>

        </section>

      </div>
    )
  }

  // ----------------------------------------------
  // APPLICATION LAYOUT
  // ----------------------------------------------

  return (
    <div className="min-h-screen bg-[#0b1018] text-slate-200">

      <Sidebar
        activePage={activePage}
        onNavigate={setActivePage}
        status={status}
        version={health?.version ?? '1.0.0'}
        mobileOpen={mobileOpen}
        onClose={() => setMobileOpen(false)}
      />

      <div className="flex min-h-screen flex-col lg:ml-64">

        <Header
          title={pageTitles[activePage]}
          status={status}
          busy={isProcessing || backendBusy}
          onMenuClick={() => {
            setMobileOpen(true)
          }}
        />

        <ProcessingBanner
  analysis={analysis}
  backendBusy={backendBusy}
  onViewAnalysis={() => {
    setActivePage('dashboard')
  }}
/>

        <main className="mx-auto w-full max-w-400 flex-1 p-4 md:p-6 lg:p-8">

          {renderPage()}

        </main>

        <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-800 px-6 py-4 text-xs text-slate-500">

          <span>
            Poker Connector · Offline Analysis Studio
          </span>

          <span>
            Version {health?.version ?? '1.0.0'}
          </span>

        </footer>

      </div>

    </div>
  )
}

export default App
