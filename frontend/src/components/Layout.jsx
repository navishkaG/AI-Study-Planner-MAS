// src/components/Layout.jsx
import { Outlet } from "react-router-dom";
import Sidebar from "./Sidebar.jsx";
import { useEffect, useState } from "react";
import { getOllamaStatus } from "../api.js";

export default function Layout() {
  const [ollamaStatus, setOllamaStatus] = useState("checking");

  useEffect(() => {
    const check = async () => {
      try {
        // Route through the backend — direct browser fetch to localhost:11434
        // is blocked by CORS, so the backend proxies the check for us.
        const { data } = await getOllamaStatus();
        setOllamaStatus(data.status); // "running" | "offline"
      } catch {
        // Backend itself is down
        setOllamaStatus("offline");
      }
    };
    check();
    const t = setInterval(check, 15000);
    return () => clearInterval(t);
  }, []);

  return (
    <div className="flex min-h-screen bg-green-50">
      <Sidebar ollamaStatus={ollamaStatus} />
      <div className="ml-60 flex-1 flex flex-col min-h-screen">
        <Outlet />
      </div>
    </div>
  );
}