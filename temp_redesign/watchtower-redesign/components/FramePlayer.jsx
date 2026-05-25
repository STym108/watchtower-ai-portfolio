import { useEffect } from "react";
import useAppStore from "../store/useAppStore";

export default function FramePlayer() {
    const {
        frameBasePath,
        clipStart,
        clipEnd,
        currentFrameTime,
        setCurrentFrame,
        isEventPlaying,
        stopClip,
        clearResult,
    } = useAppStore();

    // 🎬 Frame playback loop
    useEffect(() => {
        if (!isEventPlaying || clipStart === null) return;

        let t = clipStart;

        const interval = setInterval(() => {
            setCurrentFrame(t);
            t += 1;

            if (t > clipEnd) {
                stopClip(); // stop after clip ends
                clearInterval(interval);
            }
        }, 500); // 500ms = 2 frames per second (Slow Motion)

        return () => clearInterval(interval);
    }, [clipStart, clipEnd, isEventPlaying]);

    if (!frameBasePath || currentFrameTime === null) return null;

    // ⚠️ adjust based on your frame naming
    const frameUrl = `${frameBasePath}/t_${currentFrameTime}.0.jpg`;

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

                {/* 🗑️ Remove Result Button */}
                {!isEventPlaying && (
                    <button
                        onClick={clearResult}
                        className="absolute top-3 right-3 px-3 py-1 text-xs rounded-lg bg-black/70 border border-white/20 hover:border-red-400 transition flex items-center gap-2"
                    >
                        <span>✖</span> Remove Results
                    </button>
                )}

                {/* ❌ Exit Event Button (During Playback) */}
                {isEventPlaying && (
                    <button
                        onClick={stopClip}
                        className="absolute top-3 right-3 px-3 py-1 text-xs rounded-lg bg-black/70 border border-white/20 hover:border-red-400 transition"
                    >
                        Stop Playback
                    </button>
                )}

                {/* 🖼️ Frame instead of video */}
                <img
                    src={frameUrl}
                    alt="frame"
                    className="w-full h-full object-cover"
                />

                {/* 🎬 Overlay */}
                <div className="pointer-events-none absolute inset-0 bg-gradient-to-t from-black/40 via-transparent to-black/20"></div>
            </div>
        </div>
    );
}