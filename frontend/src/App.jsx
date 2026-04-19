import { Routes, Route } from "react-router-dom";
import { Toaster } from "react-hot-toast";
import Layout from "./components/Layout.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import Schedule from "./pages/Schedule.jsx";
import Priorities from "./pages/Priorities.jsx";
import Topics from "./pages/Topics.jsx";
import AgentTrace from "./pages/AgentTrace.jsx";
import Conflicts from "./pages/Conflicts.jsx";

export default function App() {
  return (
    <>
      <Toaster position="top-right" toastOptions={{ style: { fontFamily:"'DM Sans',sans-serif", fontSize:"13px", background:"#0d0d0d", color:"#f5f2eb", border:"1px solid #2a2a2a", borderRadius:"10px" } }} />
      <Routes>
        <Route element={<Layout />}>
          <Route path="/"           element={<Dashboard />} />
          <Route path="/schedule"   element={<Schedule />} />
          <Route path="/priorities" element={<Priorities />} />
          <Route path="/topics"     element={<Topics />} />
          <Route path="/trace"      element={<AgentTrace />} />
          <Route path="/conflicts"  element={<Conflicts />} />
        </Route>
      </Routes>
    </>
  );
}