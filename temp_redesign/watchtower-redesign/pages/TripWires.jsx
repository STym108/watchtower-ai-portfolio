import { useState, useEffect } from "react";
import Navbar from "../components/Navbar";
import TripwireTable from "../components/TripWireTable";
import useToastStore from "../store/useToastStore"; // 🔥 Use Global Toasts!

export default function TripWires() {
  const [input, setInput] = useState("");
  const [alerts, setAlerts] = useState([]);

  const telegramHandle = "@your_handle"; // later from backend
  const { addToast } = useToastStore(); // 🔥 Access Global Toast System
  
  // 🔌 WEBSOCKET CONNECTION: Listen for live AI alerts from the backend
  useEffect(() => {
    console.log("Connecting to WatchTower WebSocket...");
    const socket = new WebSocket("ws://localhost:8000/ws/alerts");

    socket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      console.log("AI Alert Received via WebSocket:", data);

      if (data.type === "NEW_ALERT") {
        // 🎉 Show the Professional Global Toast
        addToast(
          `🚨 AI ALERT: ${data.rule} - ${data.ai_analysis}`, 
          "success", 
          8000
        );
      }
    };

    socket.onerror = (error) => console.error("WebSocket Error:", error);
    socket.onclose = () => console.log("WebSocket Connection Closed.");

    return () => socket.close();
  }, []);

  const handleAdd = async () => {
    if (!input.trim()) return;

    try {
      // 🔥 POST request to backend
      const res = await fetch("http://localhost:8000/api/alerts/setup", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          condition: input,
        })
      });

      const data = await res.json();

      if (!res.ok) throw new Error(data.message || "Failed");

      // ✅ Add alert to UI
      const newAlert = {
        id: Date.now(),
        text: input,
        status: "active",
      };

      setAlerts((prev) => [newAlert, ...prev]);
      setInput("");

      // 🎉 Success message using Global Store
      addToast("🚀 Alert added successfully!", "success");

    } catch (err) {
      console.error(err);

      // ❌ Error message
      addToast("❌ Failed to add alert", "error");
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-[#000000] via-[#020617] to-[#000000] text-white overflow-x-hidden relative">

      {/* Glow Background */}
      <div className="fixed top-[-120px] left-[-120px] w-[500px] h-[500px] bg-cyan-400 opacity-15 blur-[200px] rounded-full"></div>
      <div className="fixed bottom-[-120px] right-[-120px] w-[500px] h-[500px] bg-purple-500 opacity-15 blur-[200px] rounded-full"></div>
      <div className="fixed top-[40%] left-[30%] w-[300px] h-[300px] bg-indigo-500 opacity-10 blur-[180px] rounded-full"></div>

      {/* Navbar */}
      <Navbar />

      <div className="relative z-10 max-w-5xl mx-auto pt-24 px-4">

        {/* Heading */}
        <h2 className="text-4xl font-bold mb-8 bg-gradient-to-r from-cyan-400 to-purple-500 bg-clip-text text-transparent">
          🚨 Tripwire Alerts
        </h2>

        {/* Input Section */}
        <div className="p-[1.5px] rounded-xl bg-gradient-to-r from-cyan-400 to-purple-500 mb-8">
          <div className="bg-black rounded-xl p-6 flex gap-4">

            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="What should we watch out for?"
              className="flex-1 p-3 rounded-lg bg-white/[0.05] border border-white/10 outline-none focus:border-cyan-400"
            />

            <button
              onClick={handleAdd}
              className="px-6 py-3 rounded-lg bg-gradient-to-r from-cyan-400 to-purple-500 text-black font-semibold hover:scale-105 transition"
            >
              Add
            </button>

          </div>
        </div>

        {/* Alerts Table */}
        <TripwireTable
          alerts={alerts}
          telegramHandle={telegramHandle}
        />

      </div>
    </div>
  );
}