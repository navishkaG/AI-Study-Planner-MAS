// src/pages/Conflicts.jsx
import { useState, useEffect } from "react";
import { RefreshCw, AlertTriangle, CheckCircle } from "lucide-react";
import * as api from "../api.js";

const TYPE_CONFIG = {
  overload: {
    icon: "⚠️",
    label: "Overload",
    cardClass: "bg-orange-50 border border-orange-200",
    badgeClass: "bg-orange-100 text-orange-800",
  },
  deadline_clash: {
    icon: "📅",
    label: "Deadline Clash",
    cardClass: "bg-red-50 border border-red-200",
    badgeClass: "bg-red-100 text-red-800",
  },
  consecutive_hard: {
    icon: "🔥",
    label: "Consecutive Hard",
    cardClass: "bg-yellow-50 border border-yellow-200",
    badgeClass: "bg-yellow-100 text-yellow-800",
  },
};

function ConflictCard({ conflict, index }) {
  const cfg = TYPE_CONFIG[conflict.conflict_type] || TYPE_CONFIG.overload;

  return (
    <div
      className={`${cfg.cardClass} rounded-xl p-4`}
      style={{ animationDelay: `${index * 0.07}s` }}
    >
      <div className="flex items-start gap-3">
        <div className="w-9 h-9 rounded-xl flex items-center justify-center text-lg flex-shrink-0 bg-white/60">
          {cfg.icon}
        </div>
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-2 flex-wrap">
            <span className={`text-[10px] font-bold px-2.5 py-0.5 rounded-full uppercase tracking-wide ${cfg.badgeClass}`}>
              {cfg.label}
            </span>
            {conflict.affected_day && (
              <span className="text-[11px] text-green-500">{conflict.affected_day}</span>
            )}
          </div>
          <p className="text-[13px] leading-relaxed text-green-900">{conflict.description}</p>
          {conflict.affected_topics?.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-2">
              {conflict.affected_topics.map((t, i) => (
                <span key={i} className="text-[11px] bg-black/5 px-2 py-0.5 rounded-md">{t}</span>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function ResolvedCard({ text, index }) {
  return (
    <div
      className="bg-green-50 border border-green-200 rounded-xl p-4 flex items-start gap-3"
      style={{ animationDelay: `${index * 0.07}s` }}
    >
      <div className="w-2 h-2 rounded-full bg-green-500 mt-1.5 flex-shrink-0" />
      <p className="text-[13px] leading-relaxed text-green-900">{text}</p>
    </div>
  );
}

export default function Conflicts() {
  const [conflicts, setConflicts] = useState([]);
  const [resolved,  setResolved]  = useState([]);
  const [loading,   setLoading]   = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await api.getConflicts();
      setConflicts(data.conflicts || []);
      setResolved(data.resolved   || []);
    } catch { setConflicts([]); setResolved([]); }
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  return (
    <div className="flex flex-col min-h-screen">
      <header className="bg-white border-b border-green-100 h-[60px] px-8 flex items-center justify-between sticky top-0 z-40">
        <span className="text-[16px] font-bold text-green-900">Conflicts & Resolutions</span>
        <button
          onClick={load}
          className="flex items-center gap-1.5 text-[12px] font-semibold border border-green-200 text-green-700 rounded-lg px-3 py-2 hover:bg-green-50 transition-colors"
        >
          <RefreshCw size={13} /> Refresh
        </button>
      </header>

      <div className="p-8 flex-1">
        {/* Summary pills */}
        <div className="flex gap-3 mb-6">
          <span className="flex items-center gap-2 bg-red-50 border border-red-200 text-red-700 text-[12px] font-semibold px-4 py-2 rounded-full">
            <AlertTriangle size={13} /> {conflicts.length} Detected
          </span>
          <span className="flex items-center gap-2 bg-green-50 border border-green-200 text-green-700 text-[12px] font-semibold px-4 py-2 rounded-full">
            <CheckCircle size={13} /> {resolved.length} Resolved
          </span>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-20 text-green-400">
            <RefreshCw size={20} className="animate-spin mr-2" /> Loading...
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-6">

            {/* Detected */}
            <div>
              <h2 className="text-[14px] font-bold text-green-900 mb-4 flex items-center gap-2">
                <AlertTriangle size={15} className="text-red-500" /> Detected Conflicts
              </h2>
              {conflicts.length === 0 ? (
                <div className="bg-green-50 border border-green-200 rounded-xl p-6 text-center">
                  <CheckCircle size={28} className="mx-auto mb-2 text-green-500" />
                  <p className="text-[13px] text-green-700 font-semibold">No conflicts detected</p>
                  <p className="text-[12px] text-green-500 mt-1">Your schedule looks balanced!</p>
                </div>
              ) : (
                <div className="flex flex-col gap-3">
                  {conflicts.map((c, i) => <ConflictCard key={i} conflict={c} index={i} />)}
                </div>
              )}
            </div>

            {/* Resolved */}
            <div>
              <h2 className="text-[14px] font-bold text-green-900 mb-4 flex items-center gap-2">
                <CheckCircle size={15} className="text-green-500" /> Resolved by Optimizer
              </h2>
              {resolved.length === 0 ? (
                <div className="bg-green-50 border border-green-100 rounded-xl p-6 text-center">
                  <p className="text-[13px] text-green-400">
                    {conflicts.length === 0
                      ? "Nothing to resolve — no conflicts were found."
                      : "Run the full pipeline to see optimizer resolutions."}
                  </p>
                </div>
              ) : (
                <div className="flex flex-col gap-3">
                  {resolved.map((r, i) => <ResolvedCard key={i} text={r} index={i} />)}
                </div>
              )}
            </div>

          </div>
        )}
      </div>
    </div>
  );
}