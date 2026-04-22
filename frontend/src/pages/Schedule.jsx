// src/pages/Schedule.jsx
import { useState, useEffect } from "react";
import { RefreshCw, Download, Calendar } from "lucide-react";
import * as api from "../api.js";

// ── Colour system ─────────────────────────────────────────────────────────────
// Must match PDF_COLORS in backend/tools/pdf_extractor.py and api.py
const PDF_COLORS = ["indigo","rose","amber","teal","violet","orange","cyan","pink"];

// Tailwind border-left colour classes per index
const COLOR_BORDER_LEFT = [
  "border-l-indigo-500",
  "border-l-rose-500",
  "border-l-amber-500",
  "border-l-teal-500",
  "border-l-violet-500",
  "border-l-orange-500",
  "border-l-cyan-500",
  "border-l-pink-500",
];

// Softer background tints for the card body
const COLOR_BG = [
  "bg-indigo-50  border-indigo-200",
  "bg-rose-50    border-rose-200",
  "bg-amber-50   border-amber-200",
  "bg-teal-50    border-teal-200",
  "bg-violet-50  border-violet-200",
  "bg-orange-50  border-orange-200",
  "bg-cyan-50    border-cyan-200",
  "bg-pink-50    border-pink-200",
];

// Solid dot colours for the legend
const COLOR_DOT = [
  "bg-indigo-500","bg-rose-500","bg-amber-500","bg-teal-500",
  "bg-violet-500","bg-orange-500","bg-cyan-500","bg-pink-500",
];

const DIFF_BADGE = {
  high:   "bg-red-100 text-red-700",
  medium: "bg-blue-100 text-blue-700",
  low:    "bg-green-100 text-green-700",
};

// ── Task card ─────────────────────────────────────────────────────────────────
function TaskBlock({ task }) {
  const ci = task.color_index ?? 0;
  const bodyClass = COLOR_BG[ci % COLOR_BG.length];

  return (
    <div className={`${bodyClass} border rounded-xl p-3 mb-2 border-l-4 ${COLOR_BORDER_LEFT[ci % COLOR_BORDER_LEFT.length]}`}>
      <div className="text-[12px] font-semibold mb-1.5 text-green-900">{task.topic}</div>
      <div className="flex items-center gap-2 flex-wrap">
        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wide ${DIFF_BADGE[task.difficulty] || DIFF_BADGE.low}`}>
          {task.difficulty}
        </span>
        <span className="text-[11px] text-green-500">{task.duration_hours}h</span>
        {task.locked && (
          <span className="bg-green-100 text-green-600 text-[10px] font-bold px-2 py-0.5 rounded-full uppercase">
            Locked
          </span>
        )}
      </div>
      <div className="text-[10px] text-green-400 mt-1.5">Priority: {task.priority_score}</div>
      {task.pdf_filename && (
        <div className="text-[10px] text-green-400 mt-0.5 truncate" title={task.pdf_filename}>
          📄 {task.pdf_filename}
        </div>
      )}
    </div>
  );
}

// ── Day column ────────────────────────────────────────────────────────────────
function DayColumn({ day, index }) {
  return (
    <div
      className="bg-white border border-green-100 rounded-[14px] overflow-hidden flex-shrink-0 w-[220px] shadow-sm flex flex-col"
      style={{ animationDelay: `${index * 0.05}s` }}
    >
      <div className="px-4 py-3 border-b border-green-100 bg-green-50">
        <div className="text-[13px] font-bold text-green-900">{day.day.split(" ")[0]}</div>
        <div className="text-[11px] text-green-500 mt-0.5">
          {new Date(day.date).toLocaleDateString("en-GB", { day: "numeric", month: "short" })}
        </div>
        <div className="text-[11px] text-green-400 mt-1">
          {day.total_hours}h study · {day.buffer_hours}h buffer
        </div>
      </div>
      <div className="p-2 flex-1">
        {day.tasks.map((t, i) => <TaskBlock key={i} task={t} />)}
        <div className="rounded-lg px-3 py-2 bg-green-50 border border-dashed border-green-200">
          <div className="text-[10px] text-green-400">Buffer: {day.buffer_hours}h</div>
        </div>
      </div>
    </div>
  );
}

// ── PDF colour legend ─────────────────────────────────────────────────────────
function ColorLegend({ colorMap }) {
  const entries = Object.entries(colorMap);
  if (!entries.length) return null;

  return (
    <div className="flex flex-wrap gap-3 mb-4">
      {entries.map(([filename, ci]) => (
        <div key={filename} className="flex items-center gap-1.5 text-[11px] text-green-700">
          <span className={`w-3 h-3 rounded-sm flex-shrink-0 ${COLOR_DOT[ci % COLOR_DOT.length]}`} />
          <span className="truncate max-w-[160px]" title={filename}>{filename}</span>
        </div>
      ))}
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────
export default function Schedule() {
  const [schedule,  setSchedule]  = useState([]);
  const [colorMap,  setColorMap]  = useState({});   // { "file.pdf": colorIndex }
  const [loading,   setLoading]   = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const [schedRes, colorRes] = await Promise.all([
        api.getSchedule(),
        api.getPdfColors(),
      ]);
      setSchedule(schedRes.data.schedule   || []);
      setColorMap(colorRes.data.colors     || {});
    } catch {
      setSchedule([]);
    }
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const totalTasks = schedule.reduce((a, d) => a + d.tasks.length, 0);
  const totalHours = schedule.reduce((a, d) => a + d.total_hours, 0);
  const highCount  = schedule.reduce(
    (a, d) => a + d.tasks.filter(t => t.difficulty === "high").length, 0
  );

  return (
    <div className="flex flex-col h-screen">
      {/* Topbar */}
      <header className="bg-white border-b border-green-100 h-[60px] px-8 flex items-center justify-between flex-shrink-0 z-40">
        <span className="text-[16px] font-bold text-green-900">Study Schedule</span>
        <div className="flex gap-2">
          <button
            onClick={load}
            className="flex items-center gap-1.5 text-[12px] font-semibold border border-green-200 text-green-700 rounded-lg px-3 py-2 hover:bg-green-50 transition-colors"
          >
            <RefreshCw size={13} /> Refresh
          </button>
          <button
            onClick={() => window.open(api.downloadIcs(), "_blank")}
            className="flex items-center gap-1.5 text-[12px] font-semibold bg-green-700 text-white rounded-lg px-3 py-2 hover:bg-green-800 transition-colors"
          >
            <Download size={13} /> Download .ics
          </button>
        </div>
      </header>

      {/* Body */}
      <div className="flex flex-col flex-1 min-h-0 p-8 gap-5">

        {/* Summary stats */}
        {schedule.length > 0 && (
          <div className="flex gap-4 flex-wrap flex-shrink-0">
            {[
              [schedule.length,             "Study Days"],
              [totalTasks,                  "Total Tasks"],
              [`${totalHours.toFixed(1)}h`, "Total Hours"],
              [highCount,                   "High Priority"],
            ].map(([v, l]) => (
              <div key={l} className="bg-white border border-green-100 rounded-xl px-5 py-3 text-center min-w-[120px] shadow-sm">
                <div className="text-2xl font-extrabold text-green-900">{v}</div>
                <div className="text-[11px] text-green-400 mt-1 uppercase tracking-wider">{l}</div>
              </div>
            ))}
          </div>
        )}

        {/* Weekly plan card */}
        <div className="bg-white border border-green-100 rounded-2xl shadow-sm flex flex-col flex-1 min-h-0">

          {/* Card header */}
          <div className="flex items-center gap-4 px-5 py-4 border-b border-green-100 flex-shrink-0">
            <h2 className="text-[15px] font-bold text-green-900">Weekly Plan</h2>
            {/* Difficulty legend */}
            <div className="flex items-center gap-3 ml-auto text-[11px]">
              {[["#ef4444","High"],["#3b82f6","Medium"],["#22c55e","Low"]].map(([c, l]) => (
                <span key={l} className="flex items-center gap-1.5 text-green-600">
                  <span className="w-2.5 h-2.5 rounded-sm inline-block" style={{ background: c }} />
                  {l}
                </span>
              ))}
            </div>
          </div>

          {/* PDF colour legend */}
          {Object.keys(colorMap).length > 0 && (
            <div className="px-5 pt-3 flex-shrink-0">
              <div className="text-[10px] text-green-400 uppercase tracking-wider mb-2">
                Card border colour = source PDF
              </div>
              <ColorLegend colorMap={colorMap} />
            </div>
          )}

          {/* Scrollable calendar — both axes */}
          <div className="flex-1 min-h-0 max-w-[1200px] overflow-x-auto overflow-y-auto">
            {loading ? (
              <div className="flex items-center justify-center h-full text-green-400">
                <RefreshCw size={20} className="animate-spin mr-2" /> Loading...
              </div>
            ) : schedule.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full">
                <Calendar size={40} className="mb-4 text-green-300" />
                <h3 className="text-[16px] font-bold mb-2 text-green-900">No schedule yet</h3>
                <p className="text-green-400 text-[13px] mb-5">Run the pipeline from the Dashboard first.</p>
                <a
                  href="/"
                  className="text-[12px] font-semibold bg-green-700 text-white px-4 py-2 rounded-lg no-underline hover:bg-green-800 transition-colors"
                >
                  Go to Dashboard
                </a>
              </div>
            ) : (
              <div className="flex gap-3 p-5 pb-4 items-start w-max min-w-full">
                {schedule.map((day, i) => <DayColumn key={day.date} day={day} index={i} />)}
              </div>
            )}
          </div>

        </div>
      </div>
    </div>
  );
}