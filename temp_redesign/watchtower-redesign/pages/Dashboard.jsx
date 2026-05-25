import { useState, useEffect, useRef } from "react";
import axios from "axios";
import ChatPanel from "../components/ChatPanel";
import VideoPlayer from "../components/VideoPlayer";
import UploadDropzone from "../components/UploadDropZone";
import Navbar from "../components/Navbar";
import useAlertStore from "../store/useAlertStore";
import FramePlayer from "../components/FramePlayer";
import useAppStore from "../store/useAppStore";
import { Video, Upload, Eye, Target } from "lucide-react";

export default function Dashboard() {
  const [mediaMode, setMediaMode] = useState(false);
  const frameBasePath = useAppStore((state) => state.frameBasePath);

  const addNotification = useAlertStore((s) => s.addNotification);

  // 🔥 Prevent duplicate alerts
  const lastAlertRef = useRef(null);

  return (
    <div className="min-h-screen bg-black text-white overflow-x-hidden relative">

      {/* Tactical Grid Overlay */}
      <div className="tactical-grid opacity-20"></div>

      {/* Gold Ambient Glow */}
      <div className="fixed top-[-200px] left-[-200px] w-[600px] h-[600px] bg-[#D4AF37] opacity-5 blur-[150px] rounded-full pointer-events-none"></div>
      <div className="fixed bottom-[-200px] right-[-200px] w-[600px] h-[600px] bg-[#D4AF37] opacity-5 blur-[150px] rounded-full pointer-events-none"></div>

      {/* Navbar */}
      <Navbar />

      {/* Main Layout */}
      <div className="relative z-10 flex flex-col lg:flex-row h-[calc(100vh-80px)] px-3 sm:px-4 md:px-6 pt-20 sm:pt-24 gap-3 sm:gap-4 pb-3 sm:pb-4">

        {/* LEFT PANEL - Query Interface */}
        <div className={`transition-all duration-500 ${frameBasePath ? "lg:flex-1" : "w-full max-w-4xl mx-auto"} min-w-0 flex flex-col`}>
          
          {/* Panel Container */}
          <div className="h-full border border-[#8B7355] bg-[#0D0D0D] flex flex-col scan-line">
            
            {/* Header Bar with Tactical Corners */}
            <div className="relative px-4 sm:px-6 py-3 sm:py-4 border-b border-[#8B7355] flex flex-col sm:flex-row sm:justify-between sm:items-center gap-2 sm:gap-0 tactical-corners">
              
              {/* Title Section */}
              <div className="flex items-center gap-3">
                <div className="w-2 h-8 bg-gradient-to-b from-[#D4AF37] to-[#B8962E]"></div>
                <div>
                  <div className="flex items-center gap-2">
                    <Target size={16} className="text-[#D4AF37]" />
                    <span className="text-xs font-semibold tracking-[0.2em] text-[#D4AF37] uppercase">AI QUERY</span>
                  </div>
                  <span className="text-sm text-gray-400">Neural Language Interface</span>
                </div>
              </div>

              {/* Mode Toggle */}
              <button
                onClick={() => setMediaMode(!mediaMode)}
                className="flex items-center gap-2 px-4 py-2 bg-[#141414] border border-[#8B7355] text-[#D4AF37] hover:border-[#D4AF37] hover:bg-[#D4AF37] hover:text-black transition-all text-xs font-semibold tracking-wide uppercase"
              >
                {mediaMode ? (
                  <>
                    <Video size={14} />
                    <span>CCTV Mode</span>
                  </>
                ) : (
                  <>
                    <Upload size={14} />
                    <span>Media Mode</span>
                  </>
                )}
              </button>
            </div>

            {/* Loading Scanner */}
            <div className="loading-scanner"></div>

            {/* Content */}
            <div className="flex-1 overflow-hidden">
              {mediaMode ? <UploadDropzone /> : <ChatPanel />}
            </div>

          </div>
        </div>

        {/* RIGHT PANEL - Video Feed */}
        {frameBasePath && (
          <div className="lg:flex-1 min-w-0 flex flex-col h-1/2 lg:h-full">
            
            {/* Panel Container */}
            <div className="h-full border border-[#8B7355] bg-[#0D0D0D] flex flex-col">
              
              {/* Header Bar */}
              <div className="relative px-4 sm:px-6 py-3 sm:py-4 border-b border-[#8B7355] flex flex-col sm:flex-row sm:justify-between sm:items-center gap-2 sm:gap-0 tactical-corners">
                
                {/* Title Section */}
                <div className="flex items-center gap-3">
                  <div className="w-2 h-8 bg-gradient-to-b from-[#D4AF37] to-[#B8962E]"></div>
                  <div>
                    <div className="flex items-center gap-2">
                      <Eye size={16} className="text-[#D4AF37]" />
                      <span className="text-xs font-semibold tracking-[0.2em] text-[#D4AF37] uppercase">VISUAL FEED</span>
                    </div>
                    <span className="text-sm text-gray-400">
                      {mediaMode ? "Uploaded Video" : "Smart Detection Stream"}
                    </span>
                  </div>
                </div>

                {/* Live Indicator */}
                <div className="status-active">
                  LIVE
                </div>
              </div>

              {/* Loading Scanner */}
              <div className="loading-scanner"></div>

              {/* Video Container */}
              <div className="flex-1 flex items-center justify-center overflow-hidden bg-black/50 relative">
                {/* Tactical crosshair overlay */}
                <div className="absolute inset-0 pointer-events-none">
                  <div className="absolute top-1/2 left-0 right-0 h-px bg-[#D4AF37] opacity-20"></div>
                  <div className="absolute left-1/2 top-0 bottom-0 w-px bg-[#D4AF37] opacity-20"></div>
                </div>
                <FramePlayer />
              </div>

            </div>
          </div>
        )}

      </div>
    </div>
  );
}
