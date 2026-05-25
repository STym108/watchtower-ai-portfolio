import { useState, useRef } from "react";
import axios from "axios";
import LoadingScanner from "./LoadingScanner";
import useAppStore from "../store/useAppStore";
import { Search, ZoomIn, Image as ImageIcon, X, Mic, Play, Target } from "lucide-react";
import ReactMarkdown from "react-markdown";

export default function ChatPanel() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [searchMode, setSearchMode] = useState("normal"); // normal, deep, image
  const [selectedFile, setSelectedFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [speakingId, setSpeakingId] = useState(null);

  const fileInputRef = useRef(null);
  const playClip = useAppStore((state) => state.playClip);
  const { playFromQuery, clearResult } = useAppStore();

  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      setSelectedFile(file);
      setPreviewUrl(URL.createObjectURL(file));
    }
  };

  const clearFile = () => {
    setSelectedFile(null);
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const handleSpeak = async (text, id) => {
    try {
      setSpeakingId(id);
      await axios.post("http://localhost:8000/api/speak", { text });
      setTimeout(() => setSpeakingId(null), 2000);
    } catch (err) {
      console.error("Speech failed:", err);
      setSpeakingId(null);
    }
  };

  const handleSend = async () => {
    if (!input.trim() && !selectedFile) return;

    const userMsg = { 
      type: "user", 
      text: input || (selectedFile ? "Searching by image..." : ""),
      image: previewUrl 
    };
    setMessages((prev) => [...prev, userMsg]);

    setLoading(true);
    const currentInput = input;
    const currentFile = selectedFile;
    
    setInput("");
    clearFile();
    clearResult();

    try {
      let res;
      if (searchMode === "image" && currentFile) {
        const formData = new FormData();
        formData.append("file", currentFile);
        if (currentInput) formData.append("query", currentInput);
        
        res = await axios.post("http://localhost:8000/api/search-image", formData, {
          headers: { "Content-Type": "multipart/form-data" }
        });
      } else if (searchMode === "deep") {
        res = await axios.post("http://localhost:8000/api/trace", {
          query: currentInput,
        });
      } else {
        res = await axios.post("http://localhost:8000/api/query", {
          query: currentInput,
        });
      }

      const data = res.data;
      console.log(`${searchMode.toUpperCase()} result:`, data);

      const isMatch = data.match_found || data.status === "success";
      const rawResponse = data.response || data.incident_report || data.message || "No results found.";
      
      if (isMatch && data.clip_start !== undefined) {
        playFromQuery(data);
      } else {
        console.warn("Match not confirmed by AI or no timing data available.");
      }

      let displayResponse = rawResponse.replace(/\[MATCH:\s*(YES|NO)\]/gi, "").trim();

      const aiMsg = {
        type: "ai",
        text: displayResponse,
        clip_start: isMatch ? data.clip_start : null,
        clip_end: isMatch ? data.clip_end : null,
        mode: searchMode,
        id: Date.now()
      };

      setMessages((prev) => [...prev, aiMsg]);

    } catch (err) {
      console.error(err);
      setMessages((prev) => [
        ...prev,
        {
          type: "ai",
          text: "⚠️ System Error: Analysis Failed",
        },
      ]);
    }

    setLoading(false);
  };

  return (
    <div className="h-full flex flex-col bg-black">
      
      {/* Mode Selector */}
      <div className="flex p-3 gap-2 border-b border-[#8B7355] overflow-x-auto">
        {[
          { id: "normal", label: "Precision", icon: Search, desc: "Quick Query" },
          { id: "deep", label: "Deep Scan", icon: ZoomIn, desc: "Full Trace" },
          { id: "image", label: "Visual ID", icon: ImageIcon, desc: "Image Match" }
        ].map((mode) => (
          <button
            key={mode.id}
            onClick={() => setSearchMode(mode.id)}
            className={`flex-1 min-w-[90px] flex flex-col items-center py-3 px-3 border transition-all ${
              searchMode === mode.id
                ? "bg-[#D4AF37]/10 border-[#D4AF37] text-[#D4AF37]"
                : "bg-[#0D0D0D] border-[#8B7355] text-gray-400 hover:border-[#D4AF37]/50"
            }`}
          >
            <mode.icon size={18} className={searchMode === mode.id ? "text-[#D4AF37]" : "text-gray-500"} />
            <span className="text-xs font-bold mt-1.5 uppercase tracking-wider">{mode.label}</span>
            <span className="text-[10px] opacity-60 font-medium mt-0.5">{mode.desc}</span>
          </button>
        ))}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center px-4">
            <Target size={48} className="text-[#8B7355] mb-4" />
            <p className="text-sm text-gray-400 mb-2">TACTICAL QUERY INTERFACE READY</p>
            <p className="text-xs text-[#8B7355]">Enter natural language query to search surveillance footage</p>
          </div>
        )}

        {messages.map((msg, i) => (
          <div
            key={i}
            className={`max-w-[85%] px-4 py-3 relative ${
              msg.type === "user"
                ? "ml-auto bg-[#0D0D0D] border border-[#D4AF37] text-white"
                : "bg-[#141414] border border-[#8B7355] text-gray-200"
            }`}
          >
            {msg.image && (
              <img src={msg.image} alt="User upload" className="max-w-[150px] mb-2 border border-[#D4AF37]" />
            )}
            
            {msg.type === "ai" ? (
              <div className="text-sm leading-relaxed [&>p]:mb-2 [&>ul]:list-disc [&>ul]:ml-5 [&>ol]:list-decimal [&>ol]:ml-5 [&>h1]:text-base [&>h1]:font-bold [&>h1]:text-[#D4AF37] [&>h2]:text-sm [&>h2]:font-bold [&>h2]:text-[#D4AF37] [&>h3]:text-sm [&>h3]:font-semibold [&>strong]:text-white [&>em]:text-gray-300">
                <ReactMarkdown>{msg.text}</ReactMarkdown>
              </div>
            ) : (
              <p className="text-sm leading-relaxed">{msg.text}</p>
            )}

            {/* Action Buttons */}
            <div className="flex items-center gap-2 mt-3 flex-wrap">
              {msg.type === "ai" && msg.clip_start !== undefined && msg.clip_start !== null && (
                <button
                  className="flex items-center gap-1.5 text-[10px] font-bold bg-[#D4AF37] text-black py-1.5 px-3 hover:bg-[#F4D03F] transition-all uppercase tracking-wide"
                  onClick={() => playClip(msg.clip_start, msg.clip_end)}
                >
                  <Play size={10} fill="currentColor" />
                  <span>Play Event</span>
                </button>
              )}

              {msg.type === "ai" && (
                <button
                  className={`flex items-center gap-1.5 text-[10px] font-bold py-1.5 px-3 transition-all uppercase tracking-wide border ${
                    speakingId === msg.id 
                      ? "bg-[#D4AF37] text-black border-[#D4AF37] animate-pulse" 
                      : "bg-transparent border-[#8B7355] text-[#8B7355] hover:border-[#D4AF37] hover:text-[#D4AF37]"
                  }`}
                  onClick={() => handleSpeak(msg.text, msg.id)}
                  title="Audio Output"
                >
                  <Mic size={10} />
                  <span>{speakingId === msg.id ? "Speaking..." : "Audio"}</span>
                </button>
              )}
            </div>
          </div>
        ))}
        {loading && <LoadingScanner />}
      </div>

      {/* Image Preview */}
      {previewUrl && (
        <div className="px-4 py-3 border-t border-[#8B7355] flex items-center gap-3 bg-[#D4AF37]/5">
          <div className="relative">
            <img src={previewUrl} className="w-14 h-14 object-cover border border-[#D4AF37]" alt="preview" />
            <button 
              onClick={clearFile}
              className="absolute -top-1.5 -right-1.5 bg-red-600 text-white p-0.5 hover:bg-red-700 transition"
            >
              <X size={12} />
            </button>
          </div>
          <div className="flex-1">
            <p className="text-xs text-[#D4AF37] font-semibold uppercase tracking-wide">Visual Query Ready</p>
            <p className="text-[10px] text-gray-400 mt-0.5">Image uploaded for analysis</p>
          </div>
        </div>
      )}

      {/* Input Area */}
      <div className="p-4 border-t border-[#8B7355] bg-[#0D0D0D]">
        <div className="flex gap-2 bg-black p-1 border border-[#8B7355] focus-within:border-[#D4AF37] transition-all">
          
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSend()}
            placeholder={
              searchMode === "image" 
                ? "Additional context (optional)..." 
                : searchMode === "deep"
                ? "Detailed query for deep trace..."
                : "Describe event, person, or activity..."
            }
            className="flex-1 bg-transparent px-3 py-2.5 text-sm outline-none placeholder:text-[#8B7355] text-white"
          />

          <div className="flex items-center gap-1">
            {searchMode === "image" && (
              <button
                onClick={() => fileInputRef.current?.click()}
                className="p-2 text-[#8B7355] hover:text-[#D4AF37] hover:bg-[#D4AF37]/10 transition"
                title="Upload Image"
              >
                <ImageIcon size={20} />
              </button>
            )}
            
            <button
              onClick={handleSend}
              disabled={loading || (!input.trim() && !selectedFile)}
              className="p-2.5 bg-[#D4AF37] text-black hover:bg-[#F4D03F] transition disabled:opacity-40 disabled:cursor-not-allowed"
              title="Execute Query"
            >
              <Search size={18} />
            </button>
          </div>
        </div>
        
        <input
          type="file"
          ref={fileInputRef}
          onChange={handleFileChange}
          accept="image/*"
          className="hidden"
        />
      </div>
    </div>
  );
}
