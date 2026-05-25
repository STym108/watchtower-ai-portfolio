import { create } from "zustand";

const useAppStore = create((set) => ({
  // 🎬 Clip info
  clipStart: null,
  clipEnd: null,
  isEventPlaying: false,

  // 🖼️ Frame playback
  frameBasePath: null,
  currentFrameTime: null,

  // 🎥 NEW: Video preview state (SAFE ADDITION)
  videoUrl: null,

  setVideoUrl: (url) =>
    set({
      videoUrl: url,
    }),

  // 🔥 Handle backend query response (FRAMES ONLY)
  playFromQuery: (data) =>
    set({
      frameBasePath: `http://localhost:8000/data/frames/${data.source_id}`,
      clipStart: Math.floor(data.clip_start),
      clipEnd: Math.ceil(data.clip_end),
      currentFrameTime: Math.floor(data.clip_start),
      isEventPlaying: true,
    }),

  // 🎬 Manual Playback Trigger
  playClip: (start, end) =>
    set({
      clipStart: Math.floor(start),
      clipEnd: Math.ceil(end),
      currentFrameTime: Math.floor(start),
      isEventPlaying: true,
    }),

  // 🔄 Update frame during playback
  setCurrentFrame: (time) =>
    set({
      currentFrameTime: time,
    }),

  // 🎬 Stop playback loop (but keep the frame visible)
  stopClip: () =>
    set({
      isEventPlaying: false,
    }),

  // 🗑️ Clear everything (triggered by 'Remove' button)
  clearResult: () =>
    set({
      clipStart: null,
      clipEnd: null,
      isEventPlaying: false,
      currentFrameTime: null,
      frameBasePath: null,
    }),
}));

export default useAppStore;