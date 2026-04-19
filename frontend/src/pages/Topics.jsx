// src/pages/Topics.jsx
import { useState, useEffect } from "react";
import { RefreshCw, FileText } from "lucide-react";
import * as api from "../api.js";

const FILTERS = ["all", "high", "medium", "low"];

const DIFF_BORDER = {
  high:   "border-l-red-500",
  medium: "border-l-blue-500",
  low:    "border-l-green-500",
};

const DIFF_BADGE = {
  high:   "bg-red-100 text-red-700",
  medium: "bg-blue-100 text-blue-700",
  low:    "bg-green-100 text-green-700",
};

function TopicCard({ topic, index }) {
  const borderColor = DIFF_BORDER[topic.difficulty] || DIFF_BORDER.low;
  return (
    <div
      className={`bg-white border border-green-100 border-l-4 ${borderColor} rounded-[14px] p-4 hover:shadow-md transition-shadow`}
      style={{ animationDelay: `${index * 0.05}s` }}
    >
      <div className="flex items-start justify-between gap-2 mb-3">
        <h3 className="text-[14px] font-bold leading-snug text-green-900">{topic.topic}</h3>
        <span className={`text-[10px] font-bold px-2.5 py-0.5 rounded-full uppercase tracking-wide flex-shrink-0 ${DIFF_BADGE[topic.difficulty] || DIFF_BADGE.low}`}>
          {topic.difficulty}
        </span>
      </div>
      <div className="grid grid-cols-2 gap-2">
        {[
          ["Est. Hours", `${topic.estimated_hours}h`],
          ["Words", topic.word_count],
        ].map(([l, v]) => (
          <div key={l} className="bg-green-50 rounded-lg p-2.5">
            <div className="text-[10px] text-green-400 uppercase tracking-wider mb-0.5">{l}</div>
            <div className="text-[16px] font-extrabold text-green-900">{v}</div>
          </div>
        ))}
      </div>
      <div className="flex items-center justify-between mt-3">
        <span className="text-[11px] text-green-400">Pages {topic.page_range}</span>
        <span className="text-[11px] text-green-400">{topic.subject || ""}</span>
      </div>
    </div>
  );
}

export default function Topics() {
  const [topics,  setTopics]  = useState([]);
  const [filter,  setFilter]  = useState("all");
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await api.getTopics();
      setTopics(data.topics || []);
    } catch { setTopics([]); }
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const filtered = filter === "all" ? topics : topics.filter(t => t.difficulty === filter);

  return (
    <div className="flex flex-col min-h-screen">
      <header className="bg-white border-b border-green-100 h-[60px] px-8 flex items-center justify-between sticky top-0 z-40">
        <span className="text-[16px] font-bold text-green-900">Extracted Topics</span>
        <button
          onClick={load}
          className="flex items-center gap-1.5 text-[12px] font-semibold border border-green-200 text-green-700 rounded-lg px-3 py-2 hover:bg-green-50 transition-colors"
        >
          <RefreshCw size={13} /> Refresh
        </button>
      </header>

      <div className="p-8 flex-1">
        {/* Filters */}
        <div className="flex gap-2 mb-6 flex-wrap">
          {FILTERS.map(f => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-4 py-1.5 rounded-lg text-[12px] font-semibold transition-all border ${
                filter === f
                  ? "bg-green-800 text-white border-green-800"
                  : "bg-white text-green-500 border-green-200 hover:bg-green-50"
              }`}
            >
              {f.charAt(0).toUpperCase() + f.slice(1)}
              {f !== "all" && !loading && (
                <span className="ml-1.5 opacity-60">
                  ({topics.filter(t => t.difficulty === f).length})
                </span>
              )}
            </button>
          ))}
          <span className="ml-auto text-[12px] text-green-400 self-center">
            {filtered.length} topic{filtered.length !== 1 ? "s" : ""}
          </span>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-20 text-green-400">
            <RefreshCw size={20} className="animate-spin mr-2" /> Loading...
          </div>
        ) : topics.length === 0 ? (
          <div className="text-center py-20">
            <FileText size={40} className="mx-auto mb-4 text-green-300" />
            <h3 className="text-[16px] font-bold mb-2 text-green-900">No topics yet</h3>
            <p className="text-green-400 text-[13px]">Run the pipeline to extract topics from your PDFs.</p>
          </div>
        ) : (
          <div className="grid gap-4" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))" }}>
            {filtered.map((t, i) => <TopicCard key={t.topic + i} topic={t} index={i} />)}
          </div>
        )}
      </div>
    </div>
  );
}