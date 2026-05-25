import { Link, useNavigate } from "react-router-dom";
import { useState, useRef } from "react";
import useToastStore from "../store/useToastStore";
import { Lock, Mail, Shield, User, MessageCircle, Image } from "lucide-react";

export default function Signup() {

    const navigate = useNavigate();
    const addToast = useToastStore((s) => s.addToast);

    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [confirmPassword, setConfirmPassword] = useState("");
    const [name, setName] = useState("");
    const [telegram, setTelegram] = useState("");
    const [profilePic, setProfilePic] = useState("");
    const [loading, setLoading] = useState(false);
    const requestInProgressRef = useRef(false);

    const handleSignup = async (e) => {
        e.preventDefault();

        if (requestInProgressRef.current) return;
        requestInProgressRef.current = true;

        if (!name.trim() || !email.trim() || !telegram.trim() || !password.trim() || !confirmPassword.trim()) {
            requestInProgressRef.current = false;
            addToast("All fields required", "error");
            return;
        }

        if (password !== confirmPassword) {
            requestInProgressRef.current = false;
            addToast("Passwords do not match", "error");
            return;
        }

        setLoading(true);
        try {
            const res = await fetch("http://localhost:8000/api/auth/signup", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    full_name: name,
                    email: email,
                    password: password,
                    telegram_handle: telegram,
                    profile_picture: profilePic
                })
            });

            const data = await res.json();

            if (res.ok) {
                addToast("Operator Registered Successfully", "success", 2000);

                setTimeout(() => {
                    navigate("/login");
                }, 2100);
            } else {
                addToast(data.message || data.detail || "Registration Failed", "error");
            }

        } catch (err) {
            console.error(err);
            addToast("System Error", "error");
        } finally {
            requestInProgressRef.current = false;
            setLoading(false);
        }
    };

    return (
        <div className="relative min-h-screen flex items-center justify-center bg-black text-white overflow-hidden py-8">

            {/* Tactical Grid */}
            <div className="tactical-grid opacity-10"></div>

            {/* Gold Ambient Glow */}
            <div className="absolute top-[-200px] left-[-200px] w-[600px] h-[600px] bg-[#D4AF37] opacity-5 blur-[150px] rounded-full"></div>
            <div className="absolute bottom-[-200px] right-[-200px] w-[600px] h-[600px] bg-[#D4AF37] opacity-5 blur-[150px] rounded-full"></div>

            {/* Signup Card */}
            <div className="relative z-10 w-full max-w-md mx-4">
                
                {/* Main Container */}
                <div className="border border-[#8B7355] bg-[#0D0D0D] p-8 sm:p-10">
                    
                    {/* Header */}
                    <div className="text-center mb-8">
                        <div className="inline-flex items-center gap-2 mb-4">
                            <Shield size={24} className="text-[#D4AF37]" />
                            <h1 className="text-2xl font-bold text-white uppercase tracking-wider">WatchTower</h1>
                        </div>
                        <div className="h-px bg-gradient-to-r from-transparent via-[#D4AF37] to-transparent mb-4"></div>
                        <p className="text-xs text-[#8B7355] uppercase tracking-[0.2em]">Operator Registration</p>
                    </div>

                    {/* Form */}
                    <form onSubmit={handleSignup} className="space-y-4">
                        
                        {/* Full Name */}
                        <div className="flex flex-col gap-1.5">
                            <label className="text-[10px] font-bold text-[#D4AF37] uppercase tracking-widest pl-1">
                                Operator Name
                            </label>
                            <div className="relative group">
                                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                                    <User size={18} className="text-[#8B7355] group-focus-within:text-[#D4AF37] transition-colors" />
                                </div>
                                <input
                                    type="text"
                                    placeholder="John Operator"
                                    value={name}
                                    required
                                    onChange={(e) => setName(e.target.value)}
                                    className="w-full pl-11 pr-4 py-3 bg-black border border-[#8B7355] text-white text-sm outline-none focus:border-[#D4AF37] focus:ring-1 focus:ring-[#D4AF37]/30 transition-all placeholder:text-gray-700"
                                />
                            </div>
                        </div>

                        {/* Email */}
                        <div className="flex flex-col gap-1.5">
                            <label className="text-[10px] font-bold text-[#D4AF37] uppercase tracking-widest pl-1">
                                Email Address
                            </label>
                            <div className="relative group">
                                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                                    <Mail size={18} className="text-[#8B7355] group-focus-within:text-[#D4AF37] transition-colors" />
                                </div>
                                <input
                                    type="email"
                                    placeholder="operator@watchtower.ai"
                                    value={email}
                                    required
                                    onChange={(e) => setEmail(e.target.value)}
                                    className="w-full pl-11 pr-4 py-3 bg-black border border-[#8B7355] text-white text-sm outline-none focus:border-[#D4AF37] focus:ring-1 focus:ring-[#D4AF37]/30 transition-all placeholder:text-gray-700"
                                />
                            </div>
                        </div>

                        {/* Telegram Handle */}
                        <div className="flex flex-col gap-1.5">
                            <label className="text-[10px] font-bold text-[#D4AF37] uppercase tracking-widest pl-1">
                                Telegram Link
                            </label>
                            <div className="relative group">
                                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                                    <MessageCircle size={18} className="text-[#8B7355] group-focus-within:text-[#D4AF37] transition-colors" />
                                </div>
                                <input
                                    type="text"
                                    placeholder="@yourhandle"
                                    value={telegram}
                                    required
                                    onChange={(e) => setTelegram(e.target.value)}
                                    className="w-full pl-11 pr-4 py-3 bg-black border border-[#8B7355] text-white text-sm outline-none focus:border-[#D4AF37] focus:ring-1 focus:ring-[#D4AF37]/30 transition-all placeholder:text-gray-700"
                                />
                            </div>
                        </div>

                        {/* Profile Picture URL */}
                        <div className="flex flex-col gap-1.5">
                            <label className="text-[10px] font-bold text-[#8B7355] uppercase tracking-widest pl-1">
                                Avatar URL (Optional)
                            </label>
                            <div className="relative group">
                                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                                    <Image size={18} className="text-[#8B7355] group-focus-within:text-[#D4AF37] transition-colors" />
                                </div>
                                <input
                                    type="text"
                                    placeholder="https://..."
                                    value={profilePic}
                                    onChange={(e) => setProfilePic(e.target.value)}
                                    className="w-full pl-11 pr-4 py-3 bg-black border border-[#8B7355] text-white text-sm outline-none focus:border-[#D4AF37] focus:ring-1 focus:ring-[#D4AF37]/30 transition-all placeholder:text-gray-700"
                                />
                            </div>
                        </div>

                        {/* Password */}
                        <div className="flex flex-col gap-1.5">
                            <label className="text-[10px] font-bold text-[#D4AF37] uppercase tracking-widest pl-1">
                                Access Code
                            </label>
                            <div className="relative group">
                                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                                    <Lock size={18} className="text-[#8B7355] group-focus-within:text-[#D4AF37] transition-colors" />
                                </div>
                                <input
                                    type="password"
                                    placeholder="Create secure code"
                                    value={password}
                                    required
                                    onChange={(e) => setPassword(e.target.value)}
                                    className="w-full pl-11 pr-4 py-3 bg-black border border-[#8B7355] text-white text-sm outline-none focus:border-[#D4AF37] focus:ring-1 focus:ring-[#D4AF37]/30 transition-all placeholder:text-gray-700"
                                />
                            </div>
                        </div>

                        {/* Confirm Password */}
                        <div className="flex flex-col gap-1.5">
                            <label className="text-[10px] font-bold text-[#D4AF37] uppercase tracking-widest pl-1">
                                Verify Code
                            </label>
                            <div className="relative group">
                                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                                    <Lock size={18} className="text-[#8B7355] group-focus-within:text-[#D4AF37] transition-colors" />
                                </div>
                                <input
                                    type="password"
                                    placeholder="Confirm access code"
                                    value={confirmPassword}
                                    required
                                    onChange={(e) => setConfirmPassword(e.target.value)}
                                    className="w-full pl-11 pr-4 py-3 bg-black border border-[#8B7355] text-white text-sm outline-none focus:border-[#D4AF37] focus:ring-1 focus:ring-[#D4AF37]/30 transition-all placeholder:text-gray-700"
                                />
                            </div>
                        </div>

                        {/* Submit Button */}
                        <button
                            type="submit"
                            disabled={loading}
                            className={`w-full py-4 bg-gradient-to-r from-[#D4AF37] via-[#F4D03F] to-[#B8962E] text-black font-bold uppercase tracking-widest text-sm relative overflow-hidden group shadow-lg shadow-yellow-500/10 hover:shadow-yellow-500/20 active:scale-[0.98] transition-all mt-4 ${loading ? "opacity-50 cursor-not-allowed" : ""}`}
                        >
                            <span className="relative z-10">{loading ? "Registering Operator..." : "Register Operator"}</span>
                            <div className="absolute inset-0 bg-white/20 translate-x-[-100%] group-hover:translate-x-[100%] transition-transform duration-500"></div>
                        </button>
                    </form>

                    {/* Divider */}
                    <div className="divider-gold"></div>

                    {/* Login Link */}
                    <p className="text-center text-sm text-gray-400">
                        Already Registered?
                        <Link to="/login" className="ml-2 text-[#D4AF37] hover:text-[#F4D03F] font-semibold transition-colors uppercase tracking-wide">
                            Access Portal
                        </Link>
                    </p>

                </div>

                {/* Tactical Corner Markers */}
                <div className="absolute top-0 left-0 w-8 h-8 border-l-2 border-t-2 border-[#D4AF37] opacity-60"></div>
                <div className="absolute top-0 right-0 w-8 h-8 border-r-2 border-t-2 border-[#D4AF37] opacity-60"></div>
                <div className="absolute bottom-0 left-0 w-8 h-8 border-l-2 border-b-2 border-[#D4AF37] opacity-60"></div>
                <div className="absolute bottom-0 right-0 w-8 h-8 border-r-2 border-b-2 border-[#D4AF37] opacity-60"></div>
            </div>
        </div>
    );
}
