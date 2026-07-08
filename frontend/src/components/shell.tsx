'use client'

import { useState, type ReactNode } from 'react'
import { ShieldIcon } from './ui'

export type ViewName = 'list' | 'new' | 'run'

export interface SessionInfo {
  /** A run is actively streaming. */
  running: boolean
  /** Live estimated cost (USD) for the active/most-recent run. */
  cost: number
  /** Provider/model display, e.g. "Gemini". */
  model: string
}

interface NavItem {
  key: string
  label: string
  target: ViewName
  icon: ReactNode
}

const NAV: NavItem[] = [
  { key: 'dashboard', label: 'Dashboard', target: 'list', icon: <GridIcon /> },
  { key: 'engagements', label: 'Engagements', target: 'list', icon: <FolderIcon /> },
  { key: 'new', label: 'New engagement', target: 'new', icon: <PlusIcon /> },
  { key: 'findings', label: 'Findings', target: 'run', icon: <BugIcon /> },
]

export function AppShell({
  active,
  activeNav,
  breadcrumb,
  session,
  onNavigate,
  children,
}: {
  active: ViewName
  /** Which nav item to highlight (Dashboard vs Engagements share the list view). */
  activeNav: string
  breadcrumb: string
  session: SessionInfo
  onNavigate: (v: ViewName) => void
  children: ReactNode
}) {
  const [drawerOpen, setDrawerOpen] = useState(false)

  return (
    <div className="min-h-screen lg:pl-[248px]">
      {/* Backdrop for mobile drawer */}
      {drawerOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/40 lg:hidden"
          aria-hidden="true"
          onClick={() => setDrawerOpen(false)}
        />
      )}

      <Sidebar
        activeNav={activeNav}
        session={session}
        drawerOpen={drawerOpen}
        onNavigate={(v) => {
          setDrawerOpen(false)
          onNavigate(v)
        }}
      />

      <div className="flex min-h-screen flex-col">
        <Header
          breadcrumb={breadcrumb}
          session={session}
          onHamburger={() => setDrawerOpen((o) => !o)}
        />
        <main className="flex-1">
          <div className="mx-auto w-full max-w-6xl px-5 py-8 sm:px-8">{children}</div>
        </main>
        <Footer />
      </div>
    </div>
  )
}

function Sidebar({
  activeNav,
  session,
  drawerOpen,
  onNavigate,
}: {
  activeNav: string
  session: SessionInfo
  drawerOpen: boolean
  onNavigate: (v: ViewName) => void
}) {
  return (
    <aside
      className={`fixed inset-y-0 left-0 z-40 flex w-[248px] flex-col bg-sidebar text-sidebar-ink transition-transform duration-200 lg:translate-x-0 ${
        drawerOpen ? 'translate-x-0' : '-translate-x-full'
      }`}
    >
      {/* Brand */}
      <div className="flex items-center gap-3 px-5 py-5">
        <span className="grid h-9 w-9 place-items-center rounded-md bg-primary text-white">
          <ShieldIcon size={18} />
        </span>
        <div className="leading-tight">
          <h1 className="text-base font-semibold tracking-tight text-white">Sentinel</h1>
          <p className="text-[11px] text-sidebar-muted">Security Console</p>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 space-y-0.5 px-3 py-2" aria-label="Primary">
        {NAV.map((item) => {
          const active = item.key === activeNav
          return (
            <button
              key={item.key}
              onClick={() => onNavigate(item.target)}
              aria-current={active ? 'page' : undefined}
              className={`relative flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition ${
                active
                  ? 'bg-sidebar-active text-white'
                  : 'text-sidebar-muted hover:bg-sidebar-active/60 hover:text-sidebar-ink'
              }`}
            >
              {active && (
                <span className="absolute left-0 top-1/2 h-5 w-0.5 -translate-y-1/2 rounded-r bg-primary" />
              )}
              <span className={active ? 'text-white' : 'text-sidebar-muted'}>{item.icon}</span>
              {item.label}
            </button>
          )
        })}
      </nav>

      {/* Session mini-panel */}
      <div className="border-t border-white/10 px-4 py-4">
        <p className="text-[10px] font-semibold uppercase tracking-wider text-sidebar-muted">Session</p>
        <div className="mt-2 flex items-center justify-between">
          <span className="inline-flex items-center gap-1.5 text-xs text-sidebar-ink">
            <span className="h-2 w-2 rounded-full" style={{ background: '#818cf8' }} />
            {session.model}
          </span>
          <span
            className={`inline-flex items-center gap-1 text-[11px] ${
              session.running ? 'text-[#fdb022]' : 'text-sidebar-muted'
            }`}
          >
            <span
              className="h-1.5 w-1.5 rounded-full"
              style={{ background: session.running ? '#fdb022' : '#475467' }}
            />
            {session.running ? 'Running' : 'Idle'}
          </span>
        </div>
        <div className="mt-2 flex items-center justify-between rounded-md bg-black/25 px-2.5 py-1.5">
          <span className="text-[11px] text-sidebar-muted">Est. cost</span>
          <span className="font-mono text-xs text-sidebar-ink">⌗ ${session.cost.toFixed(4)}</span>
        </div>
      </div>
    </aside>
  )
}

function Header({
  breadcrumb,
  session,
  onHamburger,
}: {
  breadcrumb: string
  session: SessionInfo
  onHamburger: () => void
}) {
  return (
    <header className="sticky top-0 z-20 flex h-14 items-center justify-between border-b border-hairline bg-surface/95 px-5 backdrop-blur sm:px-8">
      <div className="flex min-w-0 items-center gap-3">
        <button
          onClick={onHamburger}
          aria-label="Open navigation"
          className="grid h-9 w-9 place-items-center rounded-md text-ink hover:bg-canvas lg:hidden"
        >
          <MenuIcon />
        </button>
        <p className="truncate text-sm font-medium text-ink-strong">{breadcrumb}</p>
      </div>

      <div className="flex items-center gap-2 sm:gap-3">
        <span className="hidden items-center gap-1.5 rounded-md bg-canvas px-2 py-1 font-mono text-xs text-ink ring-1 ring-hairline sm:inline-flex">
          ⌗ ${session.cost.toFixed(4)}
        </span>
        <span className="hidden items-center gap-1 rounded-md bg-primary-tint px-2 py-1 text-xs font-medium text-primary ring-1 ring-primary/20 sm:inline-flex">
          {session.model}
        </span>
        <span
          className="inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs font-medium ring-1"
          style={
            session.running
              ? { color: '#b54708', background: '#fffaeb', boxShadow: 'inset 0 0 0 1px #fedf89' }
              : { color: '#067647', background: '#ecfdf3', boxShadow: 'inset 0 0 0 1px #a6f4c5' }
          }
        >
          <span
            className="h-1.5 w-1.5 rounded-full"
            style={{ background: session.running ? '#dc6803' : '#067647' }}
          />
          {session.running ? 'Running' : 'Ready'}
        </span>
      </div>
    </header>
  )
}

function Footer() {
  return (
    <footer className="border-t border-hairline px-5 py-4 sm:px-8">
      <div className="mx-auto flex w-full max-w-6xl flex-col items-start justify-between gap-2 text-xs text-ink-muted sm:flex-row sm:items-center">
        <span>Sentinel · Security Assessment Platform</span>
        <div className="flex items-center gap-2">
          {['PostgreSQL', 'Gemini', 'scope-gated'].map((b) => (
            <span key={b} className="rounded bg-canvas px-1.5 py-0.5 ring-1 ring-hairline">
              {b}
            </span>
          ))}
          <span className="font-mono text-ink-muted">v0.3</span>
        </div>
      </div>
    </footer>
  )
}

// ── Nav icons ────────────────────────────────────────────────────────────────
function iconProps() {
  return {
    width: 18,
    height: 18,
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 2,
    strokeLinecap: 'round' as const,
    strokeLinejoin: 'round' as const,
    'aria-hidden': true,
  }
}
function GridIcon() {
  return (
    <svg {...iconProps()}>
      <rect x="3" y="3" width="7" height="7" rx="1" />
      <rect x="14" y="3" width="7" height="7" rx="1" />
      <rect x="3" y="14" width="7" height="7" rx="1" />
      <rect x="14" y="14" width="7" height="7" rx="1" />
    </svg>
  )
}
function FolderIcon() {
  return (
    <svg {...iconProps()}>
      <path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
    </svg>
  )
}
function PlusIcon() {
  return (
    <svg {...iconProps()}>
      <path d="M12 5v14M5 12h14" />
    </svg>
  )
}
function BugIcon() {
  return (
    <svg {...iconProps()}>
      <rect x="8" y="6" width="8" height="12" rx="4" />
      <path d="M12 2v3M4 9h3M17 9h3M4 15h3M17 15h3M9 3l1 2M15 3l-1 2" />
    </svg>
  )
}
function MenuIcon() {
  return (
    <svg {...iconProps()}>
      <path d="M4 6h16M4 12h16M4 18h16" />
    </svg>
  )
}
