import { useEffect, useRef } from "react";
import useAppStore from "../store/useAppStore";

export default function VideoPlayer() {
  const videoRef = useRef(null);
  const loopCountRef = useRef(0);

  const {
    videoUrl,
    clipStart,
    clipEnd,
    isEventPlaying,
    stopClip,
  } = useAppStore();

  // ▶ Jump to clip start
  useEffect(() => {
    const video = videoRef.current;
    if (!video || clipStart === null) return;

    video.currentTime = clipStart;
    video.play();
    loopCountRef.current = 0; // reset loop counter
  }, [clipStart]);

  // 🔁 Loop clip (max 5 times then stop)
  useEffect(() => {
    const video = videoRef.current;
    if (!video || clipStart === null || clipEnd === null) return;

    const handleTimeUpdate = () => {
      if (video.currentTime >= clipEnd) {
        loopCountRef.current += 1;

        if (loopCountRef.current >= 5) {
          stopClip(); // 🔥 auto stop after loops
          return;
        }

        video.currentTime = clipStart;
      }
    };

    video.addEventListener("timeupdate", handleTimeUpdate);

    return () => {
      video.removeEventListener("timeupdate", handleTimeUpdate);
    };
  }, [clipStart, clipEnd, stopClip]);

  return (
    <div className="h-full flex items-center justify-center p-4">

      <div
        className={`relative w-full h-full rounded-xl overflow-hidden border transition-all duration-300 ${isEventPlaying
          ? "border-red-500 shadow-[0_0_25px_rgba(255,0,0,0.4)]"
          : "border-white/10"
          }`}
      >
        {/* 🚨 Event Badge */}
        {isEventPlaying && (
          <div className="absolute top-3 left-3 bg-red-500/90 backdrop-blur px-3 py-1 rounded-full text-xs font-semibold flex items-center gap-2 animate-pulse">
            <span className="w-2 h-2 bg-white rounded-full"></span>
            EVENT DETECTED
          </div>
        )}

        {/* ❌ Exit Event Button */}
        {isEventPlaying && (
          <button
            onClick={stopClip}
            className="absolute top-3 right-3 px-3 py-1 text-xs rounded-lg bg-black/70 border border-white/20 hover:border-red-400 transition"
          >
            Exit Event
          </button>
        )}

        {/* 🎥 Video */}
        <video
          ref={videoRef}
          src={videoUrl}
          controls
          className="w-full h-full object-cover"
        />

        {/* 🎬 Subtle Overlay Gradient */}
        <div className="pointer-events-none absolute inset-0 bg-gradient-to-t from-black/40 via-transparent to-black/20"></div>
      </div>

    </div>
  );
}