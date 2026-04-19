import { NavLink } from "react-router-dom";
import {
  LayoutGrid, Calendar, BarChart2, FileText,
  Activity, AlertTriangle, Layers,
} from "lucide-react";

const NAV = [
  { section: "Main" },
  { to: "/", label: "Dashboard", icon: LayoutGrid },
  { to: "/schedule", label: "Study Schedule", icon: Calendar },
  { to: "/priorities", label: "Priorities", icon: BarChart2 },
  { to: "/topics", label: "Topics", icon: FileText },
  { section: "Monitoring" },
  { to: "/trace", label: "Agent Trace", icon: Activity },
  { to: "/conflicts", label: "Conflicts", icon: AlertTriangle },
];

export default function Sidebar({ ollamaStatus }) {
  return (
    <aside className="w-60 bg-green-900 min-h-screen fixed left-0 top-0 flex flex-col text-white">
      <div className="px-6 py-7 border-b border-green-800">
        <div className="w-9 h-9 bg-green-600 rounded-lg flex items-center justify-center mb-3">
          <Layers size={18} />
        </div>
        <h1 className="text-[15px] font-bold">AI Study Planner</h1>
        <p className="text-green-300 text-[11px]">Multi-Agent System</p>
      </div>

      <nav className="flex-1 pt-2">
        {NAV.map((item, i) =>
          item.section ? (
            <div key={i} className="px-6 pt-4 pb-2 text-green-400 text-[10px] uppercase tracking-wider">
              {item.section}
            </div>
          ) : (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) =>
                `flex items-center gap-3 px-6 py-3 text-sm border-l-4 transition-all ${
                  isActive
                    ? "bg-green-700 border-green-400 text-white"
                    : "hover:bg-green-800 border-transparent text-green-200"
                }`
              }
            >
              <item.icon size={15} />
              {item.label}
            </NavLink>
          )
        )}
      </nav>

      <div className="px-6 py-5 border-t border-green-800">
        <div className="text-xs text-green-400 mb-1">LLM Engine</div>
        <div className="flex items-center gap-2 text-sm">
          <span className={`w-2 h-2 rounded-full ${ollamaStatus === "running" ? "bg-green-400" : "bg-red-400"}`} />
          {ollamaStatus === "running" ? "Ollama running" : "Ollama offline"}
        </div>
      </div>
    </aside>
  );
}