import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import Navbar from "../components/Navbar";
import useToastStore from "../store/useToastStore";

export default function Profile() {
  const navigate = useNavigate();
  const addToast = useToastStore((s) => s.addToast);

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [telegram, setTelegram] = useState("");
  const [phone, setPhone] = useState("");
  const [loading, setLoading] = useState(false);
  const [fetching, setFetching] = useState(true);

  // Load profile data on component mount
  useEffect(() => {
    const loadProfile = async () => {
      try {
        const token = localStorage.getItem("access_token");
        if (!token) {
          addToast("Please login first", "error");
          navigate("/login");
          return;
        }

        const res = await fetch("http://localhost:8000/api/auth/profile", {
          method: "GET",
          headers: {
            "Content-Type": "application/json",
            "Authorization": `Bearer ${token}`
          }
        });

        if (res.ok) {
          const data = await res.json();
          setFullName(data.full_name || "");
          setEmail(data.email || "");
          setTelegram(data.telegram_handle || "");
          setPhone(data.phone || "");
        } else if (res.status === 401) {
          addToast("Session expired. Please login again", "error");
          localStorage.removeItem("access_token");
          localStorage.removeItem("refresh_token");
          navigate("/login");
        } else {
          const errorData = await res.json();
          addToast(errorData.detail || "Failed to load profile", "error");
        }
      } catch (err) {
        console.error(err);
        addToast("Failed to load profile", "error");
      } finally {
        setFetching(false);
      }
    };

    loadProfile();
  }, []);

  const handleSave = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem("access_token");
      if (!token) {
        addToast("Please login first", "error");
        navigate("/login");
        return;
      }

      addToast("Saving profile...", "info", 1000);

      const res = await fetch("http://localhost:8000/api/auth/profile", {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`
        },
        body: JSON.stringify({
          full_name: fullName,
          telegram_handle: telegram,
          phone: phone
        })
      });

      if (res.ok) {
        addToast("Profile updated successfully!", "success");
        console.log("Profile updated:", { fullName, email, telegram, phone });
      } else if (res.status === 401) {
        addToast("Session expired. Please login again", "error");
        localStorage.removeItem("access_token");
        localStorage.removeItem("refresh_token");
        navigate("/login");
      } else {
        const errorData = await res.json();
        addToast(errorData.detail || "Failed to save profile", "error");
      }
    } catch (err) {
      console.error(err);
      addToast("Failed to save profile", "error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="relative min-h-screen bg-gradient-to-br from-[#000000] via-[#020617] to-[#000000] text-white overflow-hidden">

      {/* 🌌 Subtle Glow (reduced brightness for darker feel) */}
      <div className="absolute top-[-120px] left-[-120px] w-[500px] h-[500px] bg-[#D4AF37] opacity-15 blur-[200px] rounded-full"></div>
      <div className="absolute bottom-[-120px] right-[-120px] w-[500px] h-[500px] bg-[#B8962E] opacity-15 blur-[200px] rounded-full"></div>
      <div className="absolute top-[40%] left-[30%] w-[300px] h-[300px] bg-[#8B7355] opacity-10 blur-[180px] rounded-full"></div>

      {/* Navbar (optional) */}
      {/* <Navbar /> */}

      <div className="relative z-10 flex justify-center items-center py-24 px-4">

        <div className="w-full max-w-xl p-[1.5px] rounded-xl bg-gradient-to-r from-[#D4AF37] to-[#B8962E]">

            <div className="bg-black rounded-xl p-8">

            <h2 className="text-2xl font-bold mb-6 bg-gradient-to-r from-[#D4AF37] to-[#B8962E] bg-clip-text text-transparent">
              Profile Settings
            </h2>

            {fetching ? (
              <div className="text-center text-gray-400">Loading profile...</div>
            ) : (
              <>
                <div className="mb-6">
                  <label className="text-sm text-gray-400">Full Name</label>
                  <input
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    placeholder="Your full name"
                    className="w-full mt-1 p-3 rounded-lg bg-white/[0.05] border border-white/10 outline-none focus:border-[#D4AF37]"
                  />
                </div>

                <div className="mb-6">
                  <label className="text-sm text-gray-400">Email</label>
                  <input
                    value={email}
                    disabled
                    placeholder="user@gmail.com"
                    className="w-full mt-1 p-3 rounded-lg bg-white/[0.05] border border-white/10 outline-none text-gray-500"
                  />
                  <p className="text-xs text-gray-500 mt-1">Email cannot be changed</p>
                </div>

                <div className="mb-6">
                  <label className="text-sm text-gray-400">
                    Telegram Handle
                  </label>
                  <input
                    value={telegram}
                    onChange={(e) => setTelegram(e.target.value)}
                    placeholder="@your_handle"
                    className="w-full mt-1 p-3 rounded-lg bg-white/[0.05] border border-white/10 outline-none focus:border-[#D4AF37]"
                  />
                </div>

                <div className="mb-6">
                  <label className="text-sm text-gray-400">
                    Phone Number
                  </label>
                  <input
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    placeholder="+91 9876543210"
                    className="w-full mt-1 p-3 rounded-lg bg-white/[0.05] border border-white/10 outline-none focus:border-[#D4AF37]"
                  />
                </div>

                <button
                  onClick={handleSave}
                  disabled={loading}
                  className="w-full py-3 rounded-lg bg-gradient-to-r from-[#D4AF37] to-[#B8962E] text-black font-semibold hover:scale-[1.02] transition disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100"
                >
                  {loading ? "Saving..." : "Save Changes"}
                </button>
              </>
            )}

          </div>
        </div>

      </div>
    </div>
  );
}