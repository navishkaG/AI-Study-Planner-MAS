// src/pages/Priorities.jsx
import { useState, useEffect } from "react";
import { RefreshCw, BarChart2 } from "lucide-react";
import * as api from "../api.js";

const DIFF_BADGE = {
  high:   "bg-red-100 text-red-700",
  medium: "bg-blue-100 text-blue-700",
  low:    "bg-green-100 text-green-700",
};

function PriorityRow({ item, rank, maxScore }) {
  const rankStyle = rank <= 3
    ? ["bg-red-100 text-red-700", "bg-orange-100 text-orange-700", "bg-amber-100 text-amber-700"][rank - 1]
    : "bg-green-50 text-green-400";

  return (
    <div
      className="grid gap-3 items-center px-4 py-3.5 border-b border-green-100 hover:bg-green-50 transition-colors last:border-0"
      style={{ gridTemplateColumns: "32px 1fr 80px 80px 120px 110px" }}
    >
      <div className={`w-7 h-7 rounded-full flex items-center justify-center text-[12px] font-bold ${rankStyle}`}>
        {rank}
      </div>
      <div>
        <div className="text-[13px] font-semibold text-green-900">{item.topic}</div>
        {item.due_date && (
          <div className="text-[11px] text-amber-600 mt-0.5">Due: {item.due_date}</div>
        )}
      </div>
      <span className={`text-[10px] font-bold px-2.5 py-1 rounded-full uppercase tracking-wide inline-block ${DIFF_BADGE[item.difficulty] || DIFF_BADGE.low}`}>
        {item.difficulty}
      </span>
      <span className="text-[13px] text-green-500">{item.estimated_hours}h</span>
      <div className="flex flex-col gap-1.5">
        <span className="text-[13px] font-semibold text-green-900">{item.priority_score}</span>
        <div className="h-1.5 bg-green-100 rounded-full overflow-hidden">
          <div
            className="h-full rounded-full bg-green-600 transition-all duration-700"
            style={{ width: `${(item.priority_score / maxScore) * 100}%` }}
          />
        </div>
      </div>
      <span className="text-[12px] text-green-500">
        {item.urgency > 0.4 ? "🔴 High" : item.urgency > 0.1 ? "🟡 Medium" : "🟢 Low"}
      </span>
    </div>
  );
}

export default function Priorities() {
  const [priorities, setPriorities] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await api.getPriorities();
      setPriorities(data.priorities || []);
    } catch { setPriorities([]); }
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const maxScore = priorities.length ? Math.max(...priorities.map(p => p.priority_score)) : 1;

  return (
    <div className="flex flex-col min-h-screen">
      <header className="bg-white border-b border-green-100 h-[60px] px-8 flex items-center justify-between sticky top-0 z-40">
        <span className="text-[16px] font-bold text-green-900">Topic Priorities</span>
        <button
          onClick={load}
          className="flex items-center gap-1.5 text-[12px] font-semibold border border-green-200 text-green-700 rounded-lg px-3 py-2 hover:bg-green-50 transition-colors"
        >
          <RefreshCw size={13} /> Refresh
        </button>
      </header>

      <div className="p-8 flex-1">
        <div className="bg-white border border-green-100 rounded-2xl overflow-hidden shadow-sm">
          <div className="px-6 py-4 border-b border-green-100 flex items-center justify-between">
            <h2 className="text-[15px] font-bold text-green-900">Ranked Study Tasks</h2>
            <span className="text-[12px] text-green-400">{priorities.length} topics</span>
          </div>

          {/* Header row */}
          <div
            className="grid gap-3 px-4 py-2.5 text-[11px] font-semibold text-green-400 uppercase tracking-wider border-b border-green-100 bg-green-50"
            style={{ gridTemplateColumns: "32px 1fr 80px 80px 120px 110px" }}
          >
            <span>#</span><span>Topic</span><span>Difficulty</span>
            <span>Hours</span><span>Score</span><span>Urgency</span>
          </div>

          {loading ? (
            <div className="flex items-center justify-center py-20 text-green-400">
              <RefreshCw size={20} className="animate-spin mr-2" /> Loading...
            </div>
          ) : priorities.length === 0 ? (
            <div className="text-center py-20">
              <BarChart2 size={40} className="mx-auto mb-4 text-green-300" />
              <h3 className="text-[16px] font-bold mb-2 text-green-900">No priority data yet</h3>
              <p className="text-green-400 text-[13px]">Run the pipeline first.</p>
            </div>
          ) : (
            priorities.map((p, i) => (
              <PriorityRow key={p.topic} item={p} rank={i + 1} maxScore={maxScore} />
            ))
          )}
        </div>
      </div>
    </div>
  );
}