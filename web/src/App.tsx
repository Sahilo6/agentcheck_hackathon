import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { Activity, GitCompare, ListTree, ShieldCheck } from "lucide-react";
import Scorecard from "./pages/Scorecard";
import ScenarioDetail from "./pages/ScenarioDetail";
import Regression from "./pages/Regression";
import Taxonomy from "./pages/Taxonomy";

const NAV = [
  { to: "/scorecard", label: "Scorecard", icon: Activity },
  { to: "/regression", label: "Regression", icon: GitCompare },
  { to: "/taxonomy", label: "Taxonomy", icon: ListTree },
];

export default function App() {
  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-10 border-b border-ink-600 bg-ink-950/90 backdrop-blur">
        <div className="mx-auto flex max-w-[1180px] items-center gap-8 px-6 py-4">
          <div className="flex items-center gap-2.5">
            <ShieldCheck size={22} className="text-pass" />
            <div>
              <div className="text-lg font-semibold leading-none">agentcheck</div>
              <div className="text-[11px] leading-tight text-slate-500">
                continuous integration for agents
              </div>
            </div>
          </div>
          <nav className="flex gap-1">
            {NAV.map(({ to, label, icon: Icon }) => (
              <NavLink
                key={to}
                to={to}
                className={({ isActive }) =>
                  `flex items-center gap-2 rounded-lg px-3.5 py-2 text-sm transition ${
                    isActive
                      ? "bg-ink-700 text-slate-100"
                      : "text-slate-400 hover:bg-ink-800 hover:text-slate-200"
                  }`
                }
              >
                <Icon size={16} />
                {label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-[1180px] px-6 py-8">
        <Routes>
          <Route path="/" element={<Navigate to="/scorecard" replace />} />
          <Route path="/scorecard" element={<Scorecard />} />
          <Route path="/scenario/:domain/:agentId/:scenarioId" element={<ScenarioDetail />} />
          <Route path="/regression" element={<Regression />} />
          <Route path="/taxonomy" element={<Taxonomy />} />
          <Route path="*" element={<Navigate to="/scorecard" replace />} />
        </Routes>
      </main>
    </div>
  );
}
