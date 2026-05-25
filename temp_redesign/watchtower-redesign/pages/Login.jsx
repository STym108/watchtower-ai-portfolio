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
          <form onSubmit={handleLogin} className="space-y-5">
            
            {/* Email Input */}
            <div>
              <label className="block text-xs font-semibold text-[#D4AF37] mb-2 uppercase tracking-wide">
                Email Address
              </label>
              <div className="relative">
                <Mail size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#8B7355]" />
                <input
                  type="email"
                  placeholder="operator@watchtower.ai"
                  value={email}
                  required
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full pl-11 pr-4 py-3 bg-black border border-[#8B7355] text-white text-sm outline-none focus:border-[#D4AF37] transition-colors"
                />
              </div>
            </div>

            {/* Password Input */}
            <div>
              <label className="block text-xs font-semibold text-[#D4AF37] mb-2 uppercase tracking-wide">
                Access Code
              </label>
              <div className="relative">
                <Lock size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#8B7355]" />
                <input
                  type="password"
                  placeholder="Enter secure code"
                  value={password}
                  required
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full pl-11 pr-4 py-3 bg-black border border-[#8B7355] text-white text-sm outline-none focus:border-[#D4AF37] transition-colors"
                />
              </div>
            </div>

            {/* Forgot Password */}
            <div className="text-right">
              <button type="button" className="text-xs text-[#8B7355] hover:text-[#D4AF37] transition-colors uppercase tracking-wide">
                Forgot Access Code?
              </button>
            </div>

            {/* Submit Button */}
            <button
              type="submit"
              disabled={loading}
              className={`w-full btn-tactical ${loading ? "opacity-50 cursor-not-allowed" : ""}`}
            >
              {loading ? "Authenticating..." : "Grant Access"}
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
