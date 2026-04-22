// src/api.js
// Centralised API layer — all backend calls live here.

import axios from "axios";

export const BASE = "http://localhost:8000";

const client = axios.create({ baseURL: BASE });

// ── PDF management ────────────────────────────────────────────────────────────
export const uploadPdf       = (file) => {
  const form = new FormData();
  form.append("file", file);
  return client.post("/upload-pdf", form);
};
export const getUploadedPdfs = () => client.get("/uploaded-pdfs");
export const deletePdf       = (filename) =>
  client.delete(`/uploaded-pdfs/${encodeURIComponent(filename)}`);

// ── Colour map ────────────────────────────────────────────────────────────────
// Returns { colors: { "file.pdf": 0, ... }, color_names: ["indigo", ...] }
export const getPdfColors = () => client.get("/pdf-colors");

// ── Ollama status (routed through backend to avoid CORS) ──────────────────────
export const getOllamaStatus = () => client.get("/ollama-status");

// ── Pipeline ──────────────────────────────────────────────────────────────────
export const runPipeline = (selectedPdfs, deadlines, hours, startDate) => {
  const form = new FormData();
  form.append("selected_pdfs",    JSON.stringify(selectedPdfs));
  form.append("deadlines",        JSON.stringify(deadlines));
  form.append("available_hours",  String(hours));
  form.append("start_date",       startDate);
  return client.post("/run-pipeline", form);
};
export const getPipelineStatus = () => client.get("/pipeline-status");

// ── Results ───────────────────────────────────────────────────────────────────
export const getSchedule     = () => client.get("/results/schedule");
export const getPriorities   = () => client.get("/results/priorities");
export const getTopics       = () => client.get("/results/topics");
export const getConflicts    = () => client.get("/results/conflicts");
export const getTrace        = () => client.get("/results/trace");
export const getOptimizerLog = () => client.get("/results/optimizer-log");
export const downloadIcs     = () => `${BASE}/results/download-ics`;

// ── SSE log stream ─────────────────────────────────────────────────────────────
export const createLogStream = () => new EventSource(`${BASE}/logs`);