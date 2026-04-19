import { Outlet } from "react-router-dom";
import Sidebar from "./Sidebar";

export default function Layout({ ollamaStatus }) {
  return (
    <div className="flex min-h-screen bg-stone-100">
      <Sidebar ollamaStatus={ollamaStatus} />
      <main className="ml-60 flex-1 min-h-screen">
        <Outlet />
      </main>
    </div>
  );
}