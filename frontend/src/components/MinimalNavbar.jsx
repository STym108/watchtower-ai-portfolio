import { Link, useNavigate } from "react-router-dom";
import { Bell, User } from "lucide-react";
import { useState, useEffect } from "react";
import useAlertStore from "../store/useAlertStore";

export default function MinimalNavbar() {
  const navigate = useNavigate();
  const [isLoggedIn, setIsLoggedIn] = useState(
    Boolean(localStorage.getItem("access_token"))
  );
  const [open, setOpen] = useState(false);
  const [alertLogs, setAlertLogs] = useState([]);
  const [alertLogsLoading, setAlertLogsLoading] = useState(false);
  const [alertLogsError, setAlertLogsError] = useState("");

  const notifications = useAlertStore((s) => s.notifications);
  const clearNotifications = useAlertStore((s) => s.clearNotifications);

  useEffect(() => {
    const syncAuthState = () => {
      setIsLoggedIn(Boolean(localStorage.getItem("access_token")));
    };

    syncAuthState();
    window.addEventListener("storage", syncAuthState);
    window.addEventListener("auth-changed", syncAuthState);

    return () => {
      window.removeEventListener("storage", syncAuthState);
      window.removeEventListener("auth-changed", syncAuthState);
    };
  }, []);

  useEffect(() => {
    const fetchAlertLogs = async () => {
      if (!open || !isLoggedIn) {
        setAlertLogs([]);
        setAlertLogsLoading(false);
        setAlertLogsError("");
        return;
      }

      setAlertLogsLoading(true);
      setAlertLogsError("");

      try {
        const token = localStorage.getItem("access_token");
        const res = await fetch("http://localhost:8000/api/alerts/logs", {
          headers: {
            "Authorization": `Bearer ${token}`
          }
        });

        if (!res.ok) {
          const text = await res.text();
          console.error("Alert Logs Backend Error:", text);
          throw new Error("⚠️ Unable to load alerts");
        }

        const data = await res.json();

        const logs =
          Array.isArray(data) ? data :
            Array.isArray(data?.alerts) ? data.alerts :
              Array.isArray(data?.logs) ? data.logs :
                Array.isArray(data?.history) ? data.history :
                  [];

        setAlertLogs(logs);
      } catch (err) {
        console.error("Alert logs fetch failed:", err);
        setAlertLogsError("⚠️ Unable to load alerts");
        setAlertLogs([]);
      } finally {
        setAlertLogsLoading(false);
      }
    };

    fetchAlertLogs();
  }, [open, isLoggedIn]);

  const handleNotificationClick = () => {
    if (!isLoggedIn) {
      navigate("/login");
      return;
    }
    setOpen((prev) => !prev);
  };

  const handleProfileClick = () => {
    if (!isLoggedIn) {
      navigate("/login");
      return;
    }
    navigate("/me");
  };

  return (
    <div className="fixed top-0 w-full z-50">
      {/* Background */}
      <div className="absolute inset-0 bg-gradient-to-r from-black via-zinc-900 to-black opacity-95 backdrop-blur-xl"></div>

      {/* Glow Line */}
      <div className="absolute bottom-0 left-0 w-full h-[2px] bg-gradient-to-r from-transparent via-[#D4AF37] to-[#B8962E] opacity-40"></div>

      {/* Content */}
      <div className="relative max-w-7xl mx-auto flex items-center justify-between px-4 md:px-8 py-4 gap-4">
        {/* Left: Logo */}
        <Link to="/" className="flex items-center justify-start gap-3">
          <h1 className="text-xl md:text-2xl font-bold bg-gradient-to-r from-[#D4AF37] via-[#F4D03F] to-[#B8962E] bg-clip-text text-transparent shrink-0">
            WatchTower AI
          </h1>
        </Link>

        {/* Center: Logged-in navigation */}
        {isLoggedIn && (
          <div className="hidden md:flex items-center justify-center gap-8 text-base font-semibold">
            <Link
              to="/dashboard"
              className="bg-gradient-to-r from-white to-gray-400 bg-clip-text text-transparent hover:from-[#D4AF37] hover:to-[#F4D03F] transition"
            >
              Dashboard
            </Link>
            <Link
              to="/tripwires"
              className="bg-gradient-to-r from-white to-gray-400 bg-clip-text text-transparent hover:from-[#D4AF37] hover:to-[#F4D03F] transition"
            >
              Alerts
            </Link>
          </div>
        )}

        {/* Right: Auth buttons or user icons */}
        <div className="flex gap-3 items-center">
          {isLoggedIn ? (
            <>
              {/* Notification */}
              <div className="relative shrink-0">
                <div
                  onClick={handleNotificationClick}
                  className="p-[1.5px] rounded-full bg-gradient-to-r from-[#D4AF37] to-[#B8962E] cursor-pointer"
                >
                  <div className="w-9 h-9 rounded-full bg-black flex items-center justify-center text-white hover:scale-105 transition">
                    <Bell size={18} />
                  </div>
                </div>

                {alertLogs.length > 0 || notifications.length > 0 && (
                  <span className="absolute -top-1 -right-1 bg-red-500 text-[10px] min-w-5 h-5 px-1 rounded-full flex items-center justify-center">
                    {alertLogs.length > 0 ? alertLogs.length : notifications.length}
                  </span>
                )}

                {open && (
                  <div className="absolute right-0 mt-3 w-72 bg-black border border-white/10 rounded-xl shadow-xl p-4 space-y-3 z-50">
                    <div className="flex justify-between items-center">
                      <span className="text-sm text-gray-400">Notifications</span>
                      <button
                        onClick={clearNotifications}
                        className="text-xs text-[#D4AF37] hover:underline"
                      >
                        Clear
                      </button>
                    </div>

                    {alertLogsLoading ? (
                      <div className="space-y-3">
                        {[1, 2].map((i) => (
                          <div
                            key={i}
                            className="h-16 rounded-lg bg-white/5 border border-white/10 animate-pulse"
                          />
                        ))}
                      </div>
                    ) : alertLogsError ? (
                      <p className="text-red-300 text-sm">{alertLogsError}</p>
                    ) : alertLogs.length > 0 || notifications.length > 0 ? (
                      <div className="space-y-3">
                        {alertLogs.map((item, i) => {
                          const message =
                            item.message ||
                            item.alert ||
                            item.text ||
                            item.title ||
                            "Alert";

                          const time =
                            item.created_at ||
                            item.timestamp ||
                            item.time ||
                            item.createdAt ||
                            "";

                          return (
                            <div
                              key={item.id || i}
                              className="p-3 rounded-lg bg-red-500/10 border border-red-400/30"
                            >
                              <p className="text-white text-sm">🚨 {message}</p>
                              {item.description && (
                                <p className="text-xs text-gray-300 mt-1">
                                  {item.description}
                                </p>
                              )}
                              {time && (
                                <p className="text-xs text-gray-400 mt-1">
                                  {time}
                                </p>
                              )}
                            </div>
                          );
                        })}
                        {notifications.map((n, i) => (
                          <div
                            key={i}
                            className="p-3 rounded-lg bg-red-500/10 border border-red-400/30"
                          >
                            <p className="text-white text-sm">🚨 {n}</p>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-gray-500 text-sm">No alerts yet</p>
                    )}
                  </div>
                )}
              </div>

              {/* Profile */}
              <button
                onClick={handleProfileClick}
                className="p-[1.5px] rounded-full bg-gradient-to-r from-[#D4AF37] to-[#B8962E] hover:scale-105 transition shrink-0"
              >
                <div className="w-9 h-9 rounded-full bg-black flex items-center justify-center text-white">
                  <User size={18} />
                </div>
              </button>
            </>
          ) : (
            <>
              {/* Login */}
              <Link to="/login">
                <button className="px-4 py-2 rounded-lg font-semibold text-white hover:text-[#D4AF37] transition-colors duration-300">
                  Login
                </button>
              </Link>
              {/* Sign Up */}
              <Link to="/signup">
                <div className="p-[1.5px] rounded-lg bg-gradient-to-r from-[#D4AF37] to-[#B8962E]">
                  <button className="px-4 py-2 rounded-lg bg-black font-semibold text-white hover:bg-gradient-to-r hover:from-[#D4AF37] hover:to-[#B8962E] transition-all duration-300">
                    Sign Up
                  </button>
                </div>
              </Link>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
