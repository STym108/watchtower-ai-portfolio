import { useState, useEffect } from "react";
import axios from "axios";
import Navbar from "../components/Navbar";
import useToastStore from "../store/useToastStore";

export default function LiveStream() {
  const [streamCount, setStreamCount] = useState(1);
  const [streamConfigs, setStreamConfigs] = useState([
    { url: "", name: "cam_1" },
    { url: "", name: "cam_2" },
    { url: "", name: "cam_3" }
  ]);
  const [activeStreams, setActiveStreams] = useState([]); 
  const [isStreaming, setIsStreaming] = useState(false);
  const [loading, setLoading] = useState(false);
  const [orientations, setOrientations] = useState({}); 
  const addToast = useToastStore((s) => s.addToast);

  useEffect(() => {
    if (isStreaming) {
      // Periodically check orientation for each active stream
      const checkOrientations = async () => {
        const newOrientations = { ...orientations };
        try {
          await Promise.all(activeStreams.map(async (stream) => {
            const res = await axios.get(`http://localhost:8000/api/media/orientation/${stream.name}`);
            newOrientations[stream.name] = res.data.orientation;
          }));
          setOrientations(newOrientations);
        } catch (err) {
          console.error("Orientation update failed:", err);
        }
      };
      
      const interval = setInterval(checkOrientations, 3000);
      return () => clearInterval(interval);
    }
  }, [isStreaming, activeStreams]);

  const handleStartStream = async (e) => {
    e.preventDefault();
    const currentStreams = streamConfigs.slice(0, streamCount);
    
    if (currentStreams.some(s => !s.url.trim())) {
      addToast("Please enter all stream URLs", "error");
      return;
    }

    setLoading(true);
    try {
      const res = await axios.post("http://localhost:8000/api/media/livestream", {
        streams: currentStreams.map(s => ({ stream_url: s.url, source_name: s.name }))
      });

      if (res.data.status === "success") {
        addToast(res.data.message, "success");
        setActiveStreams(currentStreams);
        setIsStreaming(true);
      } else {
        addToast("Failed to start stream", "error");
      }
    } catch (err) {
      console.error(err);
      addToast("Server error occurred while starting stream", "error");
    } finally {
      setLoading(false);
    }
  };

  const updateConfig = (idx, field, val) => {
    const newConfigs = [...streamConfigs];
    newConfigs[idx][field] = val;
    setStreamConfigs(newConfigs);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-[#000000] via-[#020617] to-[#000000] text-white overflow-x-hidden relative">
      {/* 🌌 Glow Background */}
      <div className="fixed top-[-120px] left-[-120px] w-[500px] h-[500px] bg-[#D4AF37] opacity-15 blur-[200px] rounded-full"></div>
      <div className="fixed bottom-[-120px] right-[-120px] w-[500px] h-[500px] bg-[#B8962E] opacity-15 blur-[200px] rounded-full"></div>

      <Navbar />

      <div className="relative z-10 max-w-4xl mx-auto pt-32 sm:pt-40 px-6">
        <div className="p-[1.5px] rounded-2xl bg-gradient-to-r from-[#D4AF37] to-[#B8962E] shadow-2xl">
          <div className="bg-black/90 backdrop-blur-xl rounded-2xl p-8 md:p-12">
            <div className="mb-8 text-center">
              <h1 className="text-4xl font-bold bg-gradient-to-r from-[#D4AF37] via-[#F4D03F] to-[#B8962E] bg-clip-text text-transparent">
                Live CCTV Stream
              </h1>
              <p className="text-gray-400 mt-3 text-lg">
                Connect your local or remote CCTV server URL to activate God's Eye mode.
              </p>
            </div>

            <form onSubmit={handleStartStream} className="space-y-6">
              <div className="space-y-4">
                <label className="text-sm font-medium text-gray-300 ml-1">Number of Parallel Streams</label>
                <select 
                  value={streamCount} 
                  onChange={(e) => setStreamCount(Number(e.target.value))}
                  className="w-full p-4 bg-white/[0.05] border border-white/10 rounded-xl outline-none focus:border-[#D4AF37] transition-all text-white"
                >
                  <option value={1} className="bg-zinc-900">1 Stream (Solo View)</option>
                  <option value={2} className="bg-zinc-900">2 Streams (Double Pulse)</option>
                  <option value={3} className="bg-zinc-900">3 Streams (Tri-Monitor)</option>
                </select>
                <p className="text-[10px] text-gray-500 mt-1 italic">
                  💡 Tip: Ensure each source has a unique name (e.g. cam_1, cam_2) to prevent feed cross-talk.
                </p>
              </div>

              <div className="space-y-6">
                {streamConfigs.slice(0, streamCount).map((cfg, i) => (
                  <div key={i} className="grid grid-cols-1 md:grid-cols-2 gap-4 p-4 rounded-xl bg-white/[0.02] border border-white/5">
                    <div className="space-y-2">
                       <label className="text-xs font-semibold text-gray-500 uppercase tracking-widest">Source {i+1} Name</label>
                       <input
                        type="text"
                        value={cfg.name}
                        onChange={(e) => updateConfig(i, "name", e.target.value)}
                        className="w-full p-3 bg-black border border-white/10 rounded-lg outline-none focus:border-[#D4AF37] transition-all font-mono text-[#F4D03F] text-sm"
                      />
                    </div>
                    <div className="space-y-2">
                       <label className="text-xs font-semibold text-gray-500 uppercase tracking-widest">URL / IP</label>
                       <input
                        type="text"
                        value={cfg.url}
                        onChange={(e) => updateConfig(i, "url", e.target.value)}
                        placeholder="rtsp://... or http://..."
                        className="w-full p-3 bg-black border border-white/10 rounded-lg outline-none focus:border-[#D4AF37] transition-all font-mono text-[#F4D03F] text-sm"
                      />
                    </div>
                  </div>
                ))}
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full py-4 rounded-xl bg-gradient-to-r from-[#D4AF37] via-[#F4D03F] to-[#B8962E] text-black font-bold text-lg shadow-lg shadow-yellow-500/20 hover:scale-[1.02] active:scale-[0.98] transition-all disabled:opacity-50"
              >
                {loading ? "Initializing Stream..." : "🚀 Activate Live Stream Trace"}
              </button>
            </form>

            <div className="mt-12 p-6 rounded-xl border border-white/5 bg-white/[0.02]">
              <h3 className="text-white font-semibold flex items-center gap-2 mb-4">
                <span className="w-2 h-2 rounded-full bg-[#D4AF37] animate-pulse"></span>
                Tiled Multi-Monitor View
              </h3>

              <div className={`mt-4 grid gap-3 min-h-[400px] ${
                activeStreams.length === 1 ? "grid-cols-1" : 
                activeStreams.length === 2 ? "grid-cols-2" : 
                "grid-cols-2 grid-rows-2"
              }`}>
                {isStreaming ? (
                  activeStreams.map((stream, i) => {
                    const isPortrait = orientations[stream.name] === "portrait";
                    const isTiledThird = activeStreams.length === 3 && i === 0;
                    
                    return (
                      <div 
                        key={i} 
                        className={`relative rounded-lg bg-zinc-900 border border-white/10 overflow-hidden flex items-center justify-center transition-all duration-700
                          ${isTiledThird ? "row-span-2 col-span-1" : ""}
                        `}
                      >
                        <img 
                          src={`http://localhost:8000/api/media/stream/${stream.name}`} 
                          alt={stream.name}
                          className={`w-full h-full ${isPortrait ? "object-contain" : "object-cover"}`}
                        />
                        <div className="absolute top-2 left-2 px-2 py-0.5 bg-red-600/80 text-[8px] font-bold rounded flex items-center gap-1 backdrop-blur-md">
                          <span className="w-1 h-1 bg-white rounded-full animate-pulse"></span> {stream.name.toUpperCase()}
                        </div>
                      </div>
                    );
                  })
                ) : (
                    <div className="col-span-full h-64 flex flex-col items-center justify-center text-gray-500 bg-white/[0.01] rounded-xl border border-dashed border-white/10">
                        <div className="text-4xl mb-4 opacity-20">📡</div>
                        <p>Awaiting parallel stream activation...</p>
                    </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
