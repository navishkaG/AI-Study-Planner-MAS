// src/pages/AgentTrace.jsx
import { useState, useEffect } from "react";
import { RefreshCw, Activity } from "lucide-react";
import * as api from "../api.js";

const AGENT_COLORS = [
  { dot: "bg-purple-100 text-purple-800", },
  { dot: "bg-sky-100 text-sky-800",       },
  { dot: "bg-amber-100 text-amber-800",   },
  { dot: "bg-green-100 text-green-800",   },
];

const AGENT_NUM = {
  "Document Analyzer": 0,
  "Priority Planner":  1,
  "Schedule Generator":2,
  "Workload Optimizer":3,
};

function TraceEntry({ entry, index }) {
  const num   = AGENT_NUM[entry.agent] ?? 0;
  const color = AGENT_COLORS[num];
  const time  = new Date(entry.timestamp).toLocaleTimeString("en-GB", {
    hour: "2-digit", minute: "2-digit", second: "2-digit",
  });

  return (
    <div
      className="flex gap-4 py-5 border-b border-green-100 last:border-0 animate-[fadeUp_0.4s_ease_forwards]"
      style={{ animationDelay: `${index * 0.08}s` }}
    >
      <div className="flex flex-col items-center w-9 flex-shrink-0">
        <div className={`w-9 h-9 rounded-full flex items-center justify-center text-[13px] font-bold ${color.dot}`}>
          {num + 1}
        </div>
      </div>

      <div className="flex-1 min-w-0">
        <div className="text-[14px] font-bold text-green-900 mb-1">{entry.agent}</div>
        <div className="font-mono text-[11px] text-green-600 mb-3 break-all">{entry.tool_called}</div>

        <div className="grid grid-cols-2 gap-3">
          <div className="bg-green-50 rounded-xl p-3">
            <div className="text-[10px] text-green-400 uppercase tracking-wider mb-1">Input</div>
            <div className="text-[12px] text-green-900 leading-relaxed">{entry.input_summary}</div>
          </div>
          <div className="bg-green-50 rounded-xl p-3">
            <div className="text-[10px] text-green-400 uppercase tracking-wider mb-1">Output</div>
            <div className="text-[12px] text-green-900 leading-relaxed">{entry.output_summary}</div>
          </div>
        </div>

        <div className="text-[11px] text-green-400 mt-2">{time}</div>
      </div>
    </div>
  );
}

function OptLog({ lines }) {
  const classify = (line) => {
    if (line.includes("✓") || line.includes("complete") || line.includes("resolved")) return "text-emerald-400";
    if (line.includes("cost") || line.includes("Moved"))    return "text-sky-400";
    if (line.includes("conflict") || line.includes("overload")) return "text-yellow-400";
    return "text-neutral-400";
  };

  return (
    <div className="bg-gray-950 rounded-xl p-4 font-mono text-[12px] leading-relaxed h-[280px] overflow-y-auto">
      {lines.length === 0 ? (
        <div className="text-neutral-600">No optimizer log yet.</div>
      ) : (
        lines.map((l, i) => (
          <div key={i} className={classify(l)}>
            <span className="text-neutral-600 mr-2">›</span>{l}
          </div>
        ))
      )}
    </div>
  );
}

export default function AgentTrace() {
  const [trace,   setTrace]   = useState([]);
  const [optLog,  setOptLog]  = useState([]);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const [t, o] = await Promise.all([api.getTrace(), api.getOptimizerLog()]);
      setTrace(t.data.trace  || []);
      setOptLog(o.data.log   || []);
    } catch { setTrace([]); setOptLog([]); }
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  return (
    <div className="flex flex-col min-h-screen">
      <header className="bg-white border-b border-green-100 h-[60px] px-8 flex items-center justify-between sticky top-0 z-40">
        <span className="text-[16px] font-bold text-green-900">Agent Trace</span>
        <button
          onClick={load}
          className="flex items-center gap-1.5 text-[12px] font-semibold border border-green-200 text-green-700 rounded-lg px-3 py-2 hover:bg-green-50 transition-colors"
        >
          <RefreshCw size={13} /> Refresh
        </button>
      </header>

      <div className="p-8 flex-1">
        <div className="grid grid-cols-[1fr_360px] gap-6">

          {/* Timeline */}
          <div className="bg-white border border-green-100 rounded-2xl overflow-hidden shadow-sm">
            <div className="px-6 py-4 border-b border-green-100">
              <h2 className="text-[15px] font-bold text-green-900">Execution Timeline</h2>
              <p className="text-[12px] text-green-500 mt-0.5">
                Inputs, tool calls and outputs for every agent
              </p>
            </div>

            <div className="px-6">
              {loading ? (
                <div className="flex items-center justify-center py-20 text-green-400">
                  <RefreshCw size={20} className="animate-spin mr-2" /> Loading...
                </div>
              ) : trace.length === 0 ? (
                <div className="text-center py-20">
                  <Activity size={40} className="mx-auto mb-4 text-green-300" />
                  <h3 className="text-[16px] font-bold mb-2 text-green-900">No trace data yet</h3>
                  <p className="text-green-400 text-[13px]">Run the pipeline to see execution details.</p>
                </div>
              ) : (
                trace.map((entry, i) => (
                  <TraceEntry key={i} entry={entry} index={i} />
                ))
              )}
            </div>
          </div>

          {/* Optimizer log + legend */}
          <div className="flex flex-col gap-5">
            <div className="bg-white border border-green-100 rounded-2xl p-5 shadow-sm">
              <h2 className="text-[15px] font-bold text-green-900 mb-4">Optimizer Change Log</h2>
              <OptLog lines={optLog} />
            </div>

            <div className="bg-white border border-green-100 rounded-2xl p-5 shadow-sm">
              <h2 className="text-[15px] font-bold text-green-900 mb-4">Agent Legend</h2>
              <div className="flex flex-col gap-3">
                {["Document Analyzer","Priority Planner","Schedule Generator","Workload Optimizer"].map((name, i) => (
                  <div key={name} className="flex items-center gap-3">
                    <div className={`w-7 h-7 rounded-full flex items-center justify-center text-[12px] font-bold ${AGENT_COLORS[i].dot}`}>
                      {i + 1}
                    </div>
                    <div>
                      <div className="text-[13px] font-semibold text-green-900">{name}</div>
                      <div className="text-[11px] text-green-400">Agent {i + 1}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

        </div>
      </div>
    </div>
  );
}