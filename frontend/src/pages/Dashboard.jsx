// src/pages/Dashboard.jsx
import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import toast from "react-hot-toast";
import {
  Upload, Trash2, Play, Download, X, Plus,
  CheckCircle, Circle, Loader,
} from "lucide-react";
import * as api from "../api.js";

// ── Sub-components ────────────────────────────────────────────────────────────

function StatCard({ value, label }) {
  return (
    <div className="bg-white border border-green-200 rounded-xl p-4 text-center shadow-sm">
      <div className="text-3xl font-extrabold text-green-900">{value}</div>
      <div className="text-[11px] text-green-600 mt-1 uppercase tracking-wider">{label}</div>
    </div>
  );
}

function StepIcon({ state, num }) {
  const base = "w-9 h-9 rounded-full flex items-center justify-center text-[13px] font-bold transition-all duration-300";
  if (state === "done")    return <div className={`${base} bg-green-100 text-green-700`}><CheckCircle size={16} /></div>;
  if (state === "running") return <div className={`${base} bg-amber-100 text-amber-700 animate-pulse`}><Loader size={16} /></div>;
  return <div className={`${base} bg-green-50 text-green-400 border border-green-200`}>{num}</div>;
}

function PipelineSteps({ steps }) {
  const labels = [
    { label: "Document Analyzer",  sub: "Extracts topics from PDFs" },
    { label: "Priority Planner",   sub: "Ranks tasks by urgency" },
    { label: "Schedule Generator", sub: "Builds calendar plan" },
    { label: "Workload Optimizer", sub: "Fixes overloads & conflicts" },
  ];
  return (
    <div className="flex flex-col">
      {labels.map((l, i) => (
        <div key={i}>
          <div className="flex items-start gap-3">
            <StepIcon state={steps[i]} num={i + 1} />
            <div className="pt-2">
              <div className="text-[13px] font-semibold text-green-900">{l.label}</div>
              <div className="text-[11px] text-green-500 mt-0.5">{l.sub}</div>
            </div>
          </div>
          {i < 3 && (
            <div className={`w-0.5 h-6 ml-[17px] my-1 transition-colors duration-500 ${steps[i] === "done" ? "bg-green-400" : "bg-green-100"}`} />
          )}
        </div>
      ))}
    </div>
  );
}

// ── Main Dashboard ─────────────────────────────────────────────────────────────
export default function Dashboard() {
  const navigate = useNavigate();

  const [uploadedPdfs, setUploadedPdfs]     = useState([]);
  const [selectedPdfs, setSelectedPdfs]     = useState(new Set());
  const [deadlines, setDeadlines]           = useState([]);
  const [hours, setHours]                   = useState(4);
  const [startDate, setStartDate]           = useState(() => new Date().toISOString().split("T")[0]);
  const [pipelineStatus, setPipelineStatus] = useState("idle");
  const [steps, setSteps]                   = useState(["pending","pending","pending","pending"]);
  const [logs, setLogs]                     = useState([{ text: "Waiting for pipeline...", type: "" }]);
  const [stats, setStats]                   = useState({ topics: "—", days: "—", conflicts: "—" });
  const [dragOver, setDragOver]             = useState(false);

  const logRef  = useRef(null);
  const esRef   = useRef(null);
  const fileRef = useRef(null);

  useEffect(() => { loadPdfs(); }, []);

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [logs]);

  const loadPdfs = async () => {
    try {
      const { data } = await api.getUploadedPdfs();
      setUploadedPdfs(data.pdfs || []);
    } catch {}
  };

  const addLog = (text, type = "") => setLogs(prev => [...prev, { text, type }]);

  const classifyLog = (msg) => {
    if (msg.includes("[Agent"))                          return "log-agent";
    if (msg.includes("✓") || msg.includes("Tool"))      return "log-tool";
    if (msg.includes("✅"))                              return "log-done";
    if (msg.includes("✗") || msg.includes("Error"))     return "log-error";
    if (msg.includes("⚠") || msg.includes("conflict"))  return "log-warn";
    return "";
  };

  const updateStepFromLog = (msg) => {
    setSteps(prev => {
      const s = [...prev];
      if (msg.includes("[Agent 1]")) { s[0] = "running"; }
      if (msg.includes("[Agent 2]")) { s[0] = "done"; s[1] = "running"; }
      if (msg.includes("[Agent 3]")) { s[1] = "done"; s[2] = "running"; }
      if (msg.includes("[Agent 4]")) { s[2] = "done"; s[3] = "running"; }
      return s;
    });
  };

  const handleFiles = async (files) => {
    const pdfs = Array.from(files).filter(f => f.name.endsWith(".pdf"));
    if (!pdfs.length) { toast.error("Only PDF files are accepted."); return; }
    for (const file of pdfs) {
      try {
        await api.uploadPdf(file);
        toast.success(`Uploaded: ${file.name}`);
        addLog(`✓ Uploaded: ${file.name}`, "log-tool");
        setSelectedPdfs(prev => new Set([...prev, file.name]));
      } catch {
        toast.error(`Failed: ${file.name}`);
        addLog(`✗ Upload failed: ${file.name}`, "log-error");
      }
    }
    loadPdfs();
  };

  const handleDrop = (e) => {
    e.preventDefault(); setDragOver(false);
    handleFiles(e.dataTransfer.files);
  };

  const deletePdf = async (filename) => {
    try {
      await api.deletePdf(filename);
      setSelectedPdfs(prev => { const s = new Set(prev); s.delete(filename); return s; });
      loadPdfs();
      toast.success("Removed.");
    } catch { toast.error("Could not delete file."); }
  };

  const toggleSelect = (filename) => {
    setSelectedPdfs(prev => {
      const s = new Set(prev);
      s.has(filename) ? s.delete(filename) : s.add(filename);
      return s;
    });
  };

  const addDeadline    = () => setDeadlines(prev => [...prev, { topic: "", due_date: "" }]);
  const updateDeadline = (i, field, value) =>
    setDeadlines(prev => prev.map((d, idx) => idx === i ? { ...d, [field]: value } : d));
  const removeDeadline = (i) => setDeadlines(prev => prev.filter((_, idx) => idx !== i));

  const runPipeline = async () => {
    if (!selectedPdfs.size) { toast.error("Select at least one PDF."); return; }
    setLogs([{ text: "Starting AI pipeline...", type: "log-agent" }]);
    setSteps(["pending","pending","pending","pending"]);
    setPipelineStatus("running");
    const validDeadlines = deadlines.filter(d => d.topic && d.due_date);
    try {
      await api.runPipeline([...selectedPdfs], validDeadlines, hours, startDate);
    } catch {
      setPipelineStatus("error");
      addLog("✗ Cannot connect to backend. Is it running on port 8000?", "log-error");
      return;
    }
    if (esRef.current) esRef.current.close();
    esRef.current = api.createLogStream();
    esRef.current.onmessage = (e) => {
      const data = JSON.parse(e.data);
      if (data.message === "__DONE__") {
        esRef.current.close();
        setSteps(["done","done","done","done"]);
        setPipelineStatus("done");
        addLog("✅ Pipeline complete!", "log-done");
        toast.success("Pipeline complete! Results are ready.");
        loadStats();
        return;
      }
      addLog(data.message, classifyLog(data.message));
      updateStepFromLog(data.message);
    };
    esRef.current.onerror = () => {
      esRef.current?.close();
      setPipelineStatus("error");
    };
  };

  const loadStats = async () => {
    try {
      const [sched, topics, conflicts] = await Promise.all([
        api.getSchedule(), api.getTopics(), api.getConflicts(),
      ]);
      setStats({
        topics:    topics.data.topics?.length      ?? "—",
        days:      sched.data.schedule?.length     ?? "—",
        conflicts: conflicts.data.resolved?.length ?? "0",
      });
    } catch {}
  };

  useEffect(() => () => esRef.current?.close(), []);

  const logLineColor = (type) => {
    if (type === "log-agent") return "text-sky-400";
    if (type === "log-tool")  return "text-green-400";
    if (type === "log-done")  return "text-emerald-400";
    if (type === "log-error") return "text-red-400";
    if (type === "log-warn")  return "text-yellow-400";
    return "text-neutral-400";
  };

  const badgeColor = {
    idle:    "bg-green-50 text-green-500",
    running: "bg-amber-100 text-amber-700",
    done:    "bg-green-100 text-green-700",
    error:   "bg-red-100 text-red-700",
  }[pipelineStatus];

  return (
    <div className="flex flex-col min-h-screen">
      {/* Topbar */}
      <header className="bg-white border-b border-green-100 h-[60px] px-8 flex items-center justify-between sticky top-0 z-40">
        <span className="text-[16px] font-bold text-green-900">Dashboard</span>
        <div className="flex items-center gap-3">
          <span className={`flex items-center gap-2 text-[12px] font-medium px-3 py-1.5 rounded-full ${badgeColor}`}>
            <span className={`w-1.5 h-1.5 rounded-full ${pipelineStatus === "running" ? "animate-pulse bg-amber-500" : pipelineStatus === "done" ? "bg-green-500" : "bg-green-300"}`} />
            {pipelineStatus.charAt(0).toUpperCase() + pipelineStatus.slice(1)}
          </span>
          <button
            onClick={() => navigate("/schedule")}
            className="text-[12px] font-semibold bg-green-800 text-white px-4 py-2 rounded-lg hover:bg-green-900 transition-colors"
          >
            View Schedule →
          </button>
        </div>
      </header>

      <div className="p-8 flex-1">
        {/* Stats */}
        <div className="grid grid-cols-4 gap-4 mb-7">
          <StatCard value={uploadedPdfs.length} label="PDFs Uploaded" />
          <StatCard value={stats.topics}        label="Topics Found" />
          <StatCard value={stats.days}          label="Study Days" />
          <StatCard value={stats.conflicts}     label="Conflicts Resolved" />
        </div>

        <div className="grid grid-cols-[1fr_340px] gap-6">
          {/* Left */}
          <div className="flex flex-col gap-5">

            {/* Upload */}
            <div className="bg-white border border-green-100 rounded-2xl p-6 shadow-sm">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-[15px] font-bold text-green-900">Upload PDF Notes</h2>
                <span className="text-[12px] text-green-500">{uploadedPdfs.length} file{uploadedPdfs.length !== 1 ? "s" : ""}</span>
              </div>

              <div
                className={`border-2 border-dashed rounded-[14px] p-10 text-center cursor-pointer transition-all bg-green-50 ${dragOver ? "border-green-500 bg-green-100" : "border-green-200 hover:border-green-400 hover:bg-green-50"}`}
                onClick={() => fileRef.current?.click()}
                onDragOver={e => { e.preventDefault(); setDragOver(true); }}
                onDragLeave={() => setDragOver(false)}
                onDrop={handleDrop}
              >
                <input
                  ref={fileRef} type="file" multiple accept=".pdf"
                  className="hidden"
                  onChange={e => { handleFiles(e.target.files); e.target.value = ""; }}
                />
                <div className="w-12 h-12 bg-green-100 rounded-xl flex items-center justify-center mx-auto mb-4">
                  <Upload size={22} className="text-green-600" />
                </div>
                <p className="font-semibold text-[14px] mb-1 text-green-900">Drop PDFs here or click to browse</p>
                <p className="text-[12px] text-green-500">Stored in backend/pdfs/ automatically</p>
              </div>

              {uploadedPdfs.length > 0 && (
                <div className="flex flex-col gap-2 mt-4">
                  {uploadedPdfs.map(pdf => (
                    <div
                      key={pdf.filename}
                      className={`flex items-center gap-3 p-3 rounded-xl border transition-all cursor-pointer ${selectedPdfs.has(pdf.filename) ? "border-green-500 bg-green-50" : "border-green-100 bg-stone-50 hover:border-green-300"}`}
                      onClick={() => toggleSelect(pdf.filename)}
                    >
                      <input
                        type="checkbox" readOnly
                        checked={selectedPdfs.has(pdf.filename)}
                        className="accent-green-600 w-4 h-4 flex-shrink-0 cursor-pointer"
                      />
                      <div className="w-8 h-8 bg-green-100 rounded-lg flex items-center justify-center flex-shrink-0">
                        <span className="text-green-700 text-[10px] font-bold">PDF</span>
                      </div>
                      <span className="text-[13px] font-medium flex-1 truncate text-green-900">{pdf.filename}</span>
                      <span className="text-[11px] text-green-400 flex-shrink-0">{pdf.size_kb} KB</span>
                      <button
                        onClick={e => { e.stopPropagation(); deletePdf(pdf.filename); }}
                        className="w-6 h-6 rounded-md flex items-center justify-center text-green-400 hover:bg-red-100 hover:text-red-500 transition-all"
                      >
                        <Trash2 size={12} />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Deadlines */}
            <div className="bg-white border border-green-100 rounded-2xl p-6 shadow-sm">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-[15px] font-bold text-green-900">
                  Deadlines <span className="text-[12px] text-green-400 font-normal">(optional)</span>
                </h2>
                <button
                  onClick={addDeadline}
                  className="flex items-center gap-1.5 text-[12px] font-semibold border border-green-200 rounded-lg px-3 py-1.5 hover:bg-green-50 text-green-700 transition-colors"
                >
                  <Plus size={13} /> Add
                </button>
              </div>

              {deadlines.length === 0 ? (
                <p className="text-[12px] text-green-400 py-2">No deadlines added — system will use difficulty-based priority.</p>
              ) : (
                <div className="flex flex-col gap-2">
                  {deadlines.map((d, i) => (
                    <div key={i} className="grid grid-cols-[1fr_160px_34px] gap-2 items-center">
                      <input
                        type="text"
                        placeholder="Topic name (e.g. SQL Joins)"
                        value={d.topic}
                        onChange={e => updateDeadline(i, "topic", e.target.value)}
                        className="border border-green-200 rounded-lg px-3 py-2 text-[13px] bg-green-50 outline-none focus:border-green-500 transition-colors"
                      />
                      <input
                        type="date"
                        value={d.due_date}
                        onChange={e => updateDeadline(i, "due_date", e.target.value)}
                        className="border border-green-200 rounded-lg px-3 py-2 text-[13px] bg-green-50 outline-none focus:border-green-500 transition-colors"
                      />
                      <button
                        onClick={() => removeDeadline(i)}
                        className="w-[34px] h-[34px] flex items-center justify-center border border-green-200 rounded-lg text-green-400 hover:bg-red-50 hover:text-red-500 transition-all"
                      >
                        <X size={13} />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Settings */}
            <div className="bg-white border border-green-100 rounded-2xl p-6 shadow-sm">
              <h2 className="text-[15px] font-bold text-green-900 mb-4">Schedule Settings</h2>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-[12px] font-semibold block mb-1.5 text-green-800">Daily Study Hours</label>
                  <input
                    type="number" min="1" max="12" step="0.5"
                    value={hours}
                    onChange={e => setHours(parseFloat(e.target.value))}
                    className="w-full border border-green-200 rounded-lg px-3 py-2 text-[13px] bg-green-50 outline-none focus:border-green-500 transition-colors"
                  />
                </div>
                <div>
                  <label className="text-[12px] font-semibold block mb-1.5 text-green-800">Start Date</label>
                  <input
                    type="date"
                    value={startDate}
                    onChange={e => setStartDate(e.target.value)}
                    className="w-full border border-green-200 rounded-lg px-3 py-2 text-[13px] bg-green-50 outline-none focus:border-green-500 transition-colors"
                  />
                </div>
              </div>
            </div>

            {/* Run button */}
            <button
              onClick={runPipeline}
              disabled={pipelineStatus === "running"}
              className="w-full flex items-center justify-center gap-3 font-bold text-[15px] bg-green-700 text-white py-4 rounded-xl hover:bg-green-800 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {pipelineStatus === "running" ? <Loader size={18} className="animate-spin" /> : <Play size={18} />}
              {pipelineStatus === "running" ? "Pipeline Running..." : "Run AI Pipeline"}
            </button>
          </div>

          {/* Right */}
          <div className="flex flex-col gap-5">

            {/* Steps */}
            <div className="bg-white border border-green-100 rounded-2xl p-6 shadow-sm">
              <h2 className="text-[15px] font-bold text-green-900 mb-5">Agent Pipeline</h2>
              <PipelineSteps steps={steps} />
              <div className="mt-5 pt-4 border-t border-green-100">
                <button
                  onClick={() => window.open(api.downloadIcs(), "_blank")}
                  disabled={pipelineStatus !== "done"}
                  className="w-full flex items-center justify-center gap-2 text-[12px] font-semibold border border-green-200 text-green-700 rounded-lg py-2.5 hover:bg-green-50 transition-all disabled:opacity-30 disabled:cursor-not-allowed"
                >
                  <Download size={14} /> Download .ics Calendar
                </button>
              </div>
            </div>

            {/* Live logs */}
            <div className="bg-white border border-green-100 rounded-2xl p-5 shadow-sm">
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-[15px] font-bold text-green-900">Live Agent Logs</h2>
                <button
                  onClick={() => setLogs([])}
                  className="text-[11px] text-green-400 hover:text-green-900 transition-colors border border-green-200 px-2.5 py-1 rounded-lg"
                >
                  Clear
                </button>
              </div>
              <div
                ref={logRef}
                className="bg-gray-950 rounded-xl p-4 font-mono text-[12px] leading-relaxed h-[280px] overflow-y-auto text-neutral-300"
              >
                {logs.map((l, i) => (
                  <div key={i} className={logLineColor(l.type)}>
                    <span className="text-neutral-600 mr-2">›</span>
                    {l.text}
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