import { Link, useNavigate } from "react-router-dom";
import { useState, useRef } from "react";
import useToastStore from "../store/useToastStore";
import { Lock, Mail, Shield } from "lucide-react";

export default function Login() {
  const navigate = useNavigate();
  const addToast = useToastStore((s) => s.addToast);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const isSubmittingRef = useRef(false);

  const handleLogin = async (e) => {
    e.preventDefault();

    if (isSubmittingRef.current) return;

    isSubmittingRef.current = true;
    setLoading(true);

    try {
      if (!email.trim() || !password.trim()) {
        addToast("Please fill in all fields", "error");
        isSubmittingRef.current = false;
        setLoading(false);
        return;
      }

      const res = await fetch("http://localhost:8000/api/auth/login", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ email, password }),
      });

      const data = await res.json();

      if (res.ok) {
        addToast("Access Granted", "success", 2000);

        localStorage.setItem("access_token", data.access_token);
        localStorage.setItem("refresh_token", data.refresh_token);
        localStorage.setItem("user_id", data.user_id);
        localStorage.setItem("email", data.email);
        
        window.dispatchEvent(new Event("auth-changed"));

        setTimeout(() => navigate("/"), 2100);
      } else {
        addToast(data.message || data.detail || "Authentication Failed", "error");
      }
    } catch (err) {
      console.error(err);
      addToast("System Error", "error");
    } finally {
      isSubmittingRef.current = false;
      setLoading(false);
    }
  };

  return (
    <div className="relative min-h-screen flex items-center justify-center bg-black text-white overflow-hidden">
      
      {/* Tactical Grid */}
      <div className="tactical-grid opacity-10"></div>

      {/* Gold Ambient Glow */}
      <div className="absolute top-[-200px] left-[-200px] w-[600px] h-[600px] bg-[#D4AF37] opacity-5 blur-[150px] rounded-full"></div>
      <div className="absolute bottom-[-200px] right-[-200px] w-[600px] h-[600px] bg-[#D4AF37] opacity-5 blur-[150px] rounded-full"></div>

      {/* Login Card */}
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
            <p className="text-xs text-[#8B7355] uppercase tracking-[0.2em]">Tactical Access Portal</p>
          </div>

          {/* Form */}
          <form onSubmit={handleLogin} className="space-y-6">
            
            {/* Email Input */}
            <div className="flex flex-col gap-2">
              <label className="text-[10px] sm:text-xs font-bold text-[#D4AF37] uppercase tracking-widest pl-1">
                Operator ID (Email)
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
                  className="w-full pl-11 pr-4 py-3.5 bg-black border border-[#8B7355] text-white text-sm outline-none focus:border-[#D4AF37] focus:ring-1 focus:ring-[#D4AF37]/30 transition-all placeholder:text-gray-600"
                />
              </div>
            </div>

            {/* Password Input */}
            <div className="flex flex-col gap-2">
              <label className="text-[10px] sm:text-xs font-bold text-[#D4AF37] uppercase tracking-widest pl-1">
                Access Code
              </label>
              <div className="relative group">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <Lock size={18} className="text-[#8B7355] group-focus-within:text-[#D4AF37] transition-colors" />
                </div>
                <input
                  type="password"
                  placeholder="Enter secure code"
                  value={password}
                  required
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full pl-11 pr-4 py-3.5 bg-black border border-[#8B7355] text-white text-sm outline-none focus:border-[#D4AF37] focus:ring-1 focus:ring-[#D4AF37]/30 transition-all placeholder:text-gray-600"
                />
              </div>
            </div>

            {/* Forgot Password */}
            <div className="flex justify-end p-1">
              <button type="button" className="text-[10px] text-[#8B7355] hover:text-[#D4AF37] transition-colors uppercase tracking-widest font-semibold">
                Forgot Access Code?
              </button>
            </div>

            {/* Submit Button */}
            <button
              type="submit"
              disabled={loading}
              className={`w-full py-4 bg-gradient-to-r from-[#D4AF37] via-[#F4D03F] to-[#B8962E] text-black font-bold uppercase tracking-widest text-sm relative overflow-hidden group shadow-lg shadow-yellow-500/10 hover:shadow-yellow-500/20 active:scale-[0.98] transition-all ${loading ? "opacity-50 cursor-not-allowed" : ""}`}
            >
              <span className="relative z-10">{loading ? "Authenticating..." : "Grant Access"}</span>
              <div className="absolute inset-0 bg-white/20 translate-x-[-100%] group-hover:translate-x-[100%] transition-transform duration-500"></div>
            </button>
          </form>

          {/* Divider */}
          <div className="divider-gold"></div>

          {/* Sign Up Link */}
          <p className="text-center text-sm text-gray-400">
            New Operator?
            <Link to="/signup" className="ml-2 text-[#D4AF37] hover:text-[#F4D03F] font-semibold transition-colors uppercase tracking-wide">
              Register System
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
