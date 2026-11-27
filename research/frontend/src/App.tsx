
import { useState } from 'react'

import Sidebar
  from './components/layout/Sidebar'

import Header
  from './components/layout/Header'

import ProcessingBanner
  from './components/dashboard/ProcessingBanner'

import ScreenshotUpload
  from './components/dashboard/ScreenshotUpload'

import Dashboard
  from './pages/Dashboard'

import Players
  from './pages/Players'

import Recognition
  from './pages/Recognition'

import JsonData
  from './pages/JsonData'

import Settings
  from './pages/Settings'

import {
  useBackendHealth,
} from './hooks/useBackendHealth'

import {
  useScreenshotAnalysis,
} from './hooks/useScreenshotAnalysis'

import type {
  Page,
} from './types/navigation'

import PerformanceLab
  from './pages/PerformanceLab'

const pageTitles: Record<Page, string> = {
  dashboard: 'Dashboard',
  screenshots: 'Screenshots',
  players: 'Players',
  recognition: 'Recognition',
  json: 'JSON Data',
  performance: 'Performance Lab',
  settings: 'Settings',
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

  function handleFileChange(
    file: File | null
  ) {

    if (isProcessing) {
      return
    }

    reset()

    setSelectedFile(file)
  }

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

  function viewDashboard() {
    setActivePage('dashboard')
  }

  const screenshotProps = {
    file: selectedFile,
    onFileChange: handleFileChange,
    onAnalyze: handleAnalyze,
    analysis,
    connectionStatus: status,
    backendBusy,
  }

  function renderPage() {

    switch (activePage) {

      case 'dashboard':

        return (
          <Dashboard
            {...screenshotProps}
          />
        )

      case 'screenshots':

        return (
          <div className="space-y-6">

            <div>

              <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-emerald-400">

                Screenshot Workspace

              </p>

              <h1 className="text-2xl font-semibold tracking-tight md:text-3xl">

                Screenshots

              </h1>

              <p className="mt-2 text-sm text-slate-400">

                Submit saved screenshots for
                offline poker table analysis.

              </p>

            </div>

            <ScreenshotUpload
              {...screenshotProps}
            />

          </div>
        )

      case 'players':

        return (
          <Players
            result={analysis.result}
            onViewDashboard={viewDashboard}
          />
        )

      case 'recognition':

        return (
          <Recognition
            result={analysis.result}
            onViewDashboard={viewDashboard}
          />
        )

      case 'json':

        return (
          <JsonData
            result={analysis.result}
            onViewDashboard={viewDashboard}
          />
        )

        case 'performance':

  return <PerformanceLab />

      case 'settings':

        return <Settings />

      default:

        return (
          <Dashboard
            {...screenshotProps}
          />
        )
    }
  }

  return (
    <div className="min-h-screen bg-[#0b1018] text-slate-200">

      <Sidebar
        activePage={activePage}
        onNavigate={setActivePage}
        status={status}
        version={
          health?.version ?? '1.0.0'
        }
        mobileOpen={mobileOpen}
        onClose={() =>
          setMobileOpen(false)
        }
      />

      <div className="flex min-h-screen flex-col lg:ml-64">

        <Header
          title={pageTitles[activePage]}
          status={status}
          busy={
            isProcessing || backendBusy
          }
          onMenuClick={() =>
            setMobileOpen(true)
          }
        />

        <ProcessingBanner
          analysis={analysis}
          backendBusy={backendBusy}
          onViewAnalysis={viewDashboard}
        />

        <main className="mx-auto w-full max-w-400 flex-1 p-4 md:p-6 lg:p-8">

          {renderPage()}

        </main>

        <footer className="flex flex-wrap items-center justify-between gap-2 border-t border-slate-800 px-4 py-4 text-xs text-slate-500 md:px-8">

          <span>

            Poker Connector · Offline Analysis Studio

          </span>

          <span>

            Version {
              health?.version ?? '1.0.0'
            }

          </span>

        </footer>

      </div>

    </div>
  )
}

export default App
