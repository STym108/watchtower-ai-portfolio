import { useState, useEffect } from "react";
import Navbar from "../components/Navbar";
import { useNavigate } from "react-router-dom";
import axios from "axios";

export default function MyProfile() {
    const navigate = useNavigate();
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchProfile = async () => {
            const token = localStorage.getItem("access_token");
            if (!token) {
                navigate("/login");
                return;
            }

            try {
                const res = await axios.get("http://localhost:8000/api/auth/profile", {
                    headers: { Authorization: `Bearer ${token}` }
                });
                setUser(res.data);
            } catch (err) {
                console.error("Failed to fetch profile:", err);
            } finally {
                setLoading(false);
            }
        };

        fetchProfile();
    }, [navigate]);

    if (loading) return <div className="min-h-screen bg-black flex items-center justify-center text-cyan-400">Loading Profile...</div>;
    if (!user) return <div className="min-h-screen bg-black flex items-center justify-center text-red-400">User not found.</div>;

    return (
        <div className="min-h-screen bg-gradient-to-br from-black via-zinc-900 to-black text-white relative overflow-hidden">

            <Navbar />

            {/* 🌌 Glow Background */}
            <div className="absolute top-[-120px] left-[-120px] w-[500px] h-[500px] bg-cyan-500 opacity-10 blur-[150px] rounded-full"></div>
            <div className="absolute bottom-[-120px] right-[-120px] w-[500px] h-[500px] bg-purple-500 opacity-10 blur-[150px] rounded-full"></div>

            <div className="relative z-10 max-w-4xl mx-auto pt-28 px-4">

                {/* 🔥 Heading */}
                <h2 className="text-4xl font-bold text-center mb-10 pb-5 bg-gradient-to-r from-cyan-400 via-blue-500 to-purple-500 bg-clip-text text-transparent">
                    My Profile
                </h2>

                {/* 📊 Profile Card */}
                <div className="p-[1.5px] rounded-2xl bg-gradient-to-r from-cyan-400 to-purple-500">
                    <div className="bg-black rounded-2xl p-8 space-y-6">

                        {/* Profile Pic & Name */}
                        <div className="flex flex-col items-center border-b border-white/10 pb-6">
                            {user.profile_picture ? (
                                <img src={user.profile_picture} alt="profile" className="w-24 h-24 rounded-full object-cover border-2 border-cyan-400 shadow-lg shadow-cyan-400/20" />
                            ) : (
                                <div className="w-24 h-24 rounded-full bg-black border-2 border-cyan-400 flex items-center justify-center text-4xl font-bold text-cyan-400">
                                    {user.full_name ? user.full_name[0].toUpperCase() : "U"}
                                </div>
                            )}
                            <h3 className="mt-4 text-2xl font-semibold text-white">{user.full_name}</h3>
                            <p className="text-gray-400">Guardian of the Watchtower</p>
                        </div>

                        {/* Email */}
                        <div className="flex justify-between border-b border-white/10 pb-4">
                            <span className="text-gray-400">Email</span>
                            <span className="text-white">{user.email}</span>
                        </div>

                        {/* Telegram */}
                        <div className="flex justify-between border-b border-white/10 pb-4">
                            <span className="text-gray-400">Telegram</span>
                            <span className="text-cyan-400">{user.telegram_handle || "@your_handle"}</span>
                        </div>

                        {/* 📈 Stats */}
                        <div className="grid grid-cols-2 gap-4 pt-4">

                            <div className="p-5 rounded-xl bg-white/[0.03] border border-white/10 text-center">
                                <p className="text-gray-400 text-sm">Account Status</p>
                                <p className="text-2xl font-bold text-cyan-400">
                                    {user.is_active ? "Active" : "Inactive"}
                                </p>
                            </div>

                            <div className="p-5 rounded-xl bg-white/[0.03] border border-white/10 text-center">
                                <p className="text-gray-400 text-sm">Member Since</p>
                                <p className="text-lg font-semibold text-purple-400">
                                    {new Date(user.created_at).toLocaleDateString()}
                                </p>
                            </div>

                            <div className="p-5 rounded-xl bg-white/[0.03] border border-white/10 text-center">
                                <p className="text-gray-400 text-sm">Last Upload</p>
                                <p className="text-lg font-semibold text-purple-400">
                                    {user.lastUpload}
                                </p>
                            </div>

                        </div>

                        {/* 🔘 Buttons Section */}
                        <div className="flex gap-4 mt-6">

                            {/* Update Profile */}
                            <button
                                onClick={() => navigate("/me/edit")}
                                className="flex-1 py-3 rounded-lg bg-gradient-to-r from-cyan-400 to-purple-500 text-black font-semibold hover:scale-105 transition"
                            >
                                Update Profile
                            </button>

                            {/* 🔥 Create Alert */}
                            <button
                                onClick={() => navigate("/alerts/create")}
                                className="flex-1 py-3 rounded-lg border border-cyan-400/40 text-cyan-400 font-semibold hover:bg-cyan-400/10 transition"
                            >
                                + Create Alert
                            </button>

                        </div>

                    </div>
                </div>

            </div>
        </div>
    );
}