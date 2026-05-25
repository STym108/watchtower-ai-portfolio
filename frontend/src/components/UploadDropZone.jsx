import { useState, useRef } from "react";
import axios from "axios";
import { useNavigate } from "react-router-dom";
import useAppStore from "../store/useAppStore";

export default function UploadDropzone() {
    const [dragging, setDragging] = useState(false);
    const [loading, setLoading] = useState(false);
    const [message, setMessage] = useState("");

    const fileInputRef = useRef(null);
    const navigate = useNavigate();

    const setVideoUrl = useAppStore((state) => state.setVideoUrl);

    const checkLoginAndUpload = () => {
        const token = localStorage.getItem("access_token");

        if (!token) {
            setMessage("🔒 Redirecting to login...");
            setTimeout(() => {
                navigate("/login");
            }, 800);
            return;
        }

        fileInputRef.current?.click();
    };

    const uploadFile = async (file) => {
        if (!file.type.startsWith("video/")) {
            setMessage("⚠️ Only video files are allowed");
            return;
        }

        const formData = new FormData();
        formData.append("file", file);

        try {
            setLoading(true);
            setMessage("Uploading video... 🚀");

            await axios.post("http://localhost:8000/api/media/upload", formData);

            const localUrl = URL.createObjectURL(file);
            setVideoUrl(localUrl);

            pollStatus();
        } catch (err) {
            console.error(err);
            setMessage("❌ Upload failed. Try again.");
            setLoading(false);
        }
    };

    const handleDrop = (e) => {
        e.preventDefault();
        setDragging(false);

        const token = localStorage.getItem("access_token");
        if (!token) {
            navigate("/login");
            return;
        }

        const file = e.dataTransfer.files[0];
        if (!file) return;

        uploadFile(file);
    };

    const handleFileChange = (e) => {
        const file = e.target.files?.[0];
        if (!file) return;

        uploadFile(file);
    };

    const pollStatus = async () => {
        const interval = setInterval(async () => {
            try {
                const res = await axios.get("http://localhost:8000/api/media/status");

                if (res.data.status === "completed") {
                    console.log(res);
                    clearInterval(interval);
                    setLoading(false);
                    setMessage("✅ Video processed successfully!");
                } else if (res.data.status?.startsWith("error")) {
                    clearInterval(interval);
                    setLoading(false);
                    setMessage(`❌ ${res.data.status}`);
                }
            } catch (err) {
                console.error(err);
            }
        }, 3000);
    };

    return (
        <div className="w-full h-full flex items-center justify-center p-6 pt-10 bg-gradient-to-br from-black via-zinc-900 to-black text-white overflow-hidden relative">
            {/* Glow */}
            <div className="absolute top-[-80px] left-[-80px] w-64 h-64 bg-[#D4AF37]/15 rounded-full blur-3xl pointer-events-none"></div>
            <div className="absolute bottom-[-80px] right-[-80px] w-64 h-64 bg-[#B8962E]/15 rounded-full blur-3xl pointer-events-none"></div>

            <div
                onDragOver={(e) => {
                    e.preventDefault();
                    setDragging(true);
                }}
                onDragLeave={() => setDragging(false)}
                onDrop={handleDrop}
                className={`relative z-10 w-full max-w-xl rounded-3xl p-[1.5px] transition-all duration-300 bg-gradient-to-r from-[#D4AF37] to-[#B8962E] shadow-2xl ${dragging ? "scale-[1.01]" : ""
                    }`}
            >
                <div className="rounded-3xl bg-black/95 backdrop-blur-xl border border-white/10 px-8 py-10 text-center">
                    <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-[#D4AF37]/40 bg-[#D4AF37]/10 px-4 py-1 text-sm text-[#F4D03F]">
                        <span className="inline-block h-2 w-2 rounded-full bg-[#D4AF37] animate-pulse"></span>
                        Media Mode
                    </div>

                    <h2 className="text-3xl font-bold bg-gradient-to-r from-[#D4AF37] via-[#F4D03F] to-[#B8962E] bg-clip-text text-transparent">
                        Upload Video
                    </h2>

                    <p className="mt-3 text-sm text-gray-400">
                        Drag & drop your MP4 or click to choose a file
                    </p>

                    <input
                        type="file"
                        accept="video/*"
                        ref={fileInputRef}
                        onChange={handleFileChange}
                        className="hidden"
                    />

                    <div
                        className={`mt-8 rounded-2xl border-2 border-dashed px-6 py-10 transition-all duration-300 ${dragging
                            ? "border-[#D4AF37] bg-[#D4AF37]/10"
                            : "border-white/10 bg-white/[0.03]"
                            }`}
                    >
                        <div className="text-5xl">🎬</div>

                        {loading ? (
                            <div className="mt-6">
                                <p className="text-[#D4AF37] text-lg font-medium animate-pulse">
                                    Processing video...
                                </p>
                                <p className="mt-2 text-sm text-gray-400">
                                    The backend is indexing your upload right now.
                                </p>
                            </div>
                        ) : (
                            <>
                                <button
                                    onClick={checkLoginAndUpload}
                                    className="mt-6 px-6 py-3 rounded-xl bg-gradient-to-r from-[#D4AF37] via-[#F4D03F] to-[#B8962E] text-black font-semibold shadow-lg shadow-yellow-500/20 hover:scale-105 transition"
                                >
                                    Upload Video
                                </button>

                                <p className="mt-4 text-sm text-gray-400">
                                    Secure upload with login required
                                </p>
                            </>
                        )}
                    </div>

                    {message && (
                        <div className="mt-6 rounded-xl border border-white/10 bg-white/[0.04] px-4 py-3 text-sm text-gray-300">
                            {message}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}