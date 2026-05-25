import { useEffect } from "react";
import { X, CheckCircle, AlertCircle, Info } from "lucide-react";
import useToastStore from "../store/useToastStore";

export default function Toast() {
  const toasts = useToastStore((s) => s.toasts);
  const removeToast = useToastStore((s) => s.removeToast);

  const getIconColor = (type) => {
    switch (type) {
      case "success":
        return "text-green-400";
      case "error":
        return "text-red-400";
      case "info":
        return "text-[#D4AF37]";
      default:
        return "text-gray-400";
    }
  };

  const getBackgroundColor = (type) => {
    switch (type) {
      case "success":
        return "bg-green-500/10 border-green-400/30";
      case "error":
        return "bg-red-500/10 border-red-400/30";
      case "info":
        return "bg-[#D4AF37]/10 border-[#D4AF37]/30";
      default:
        return "bg-gray-500/10 border-gray-400/30";
    }
  };

  const getIcon = (type) => {
    switch (type) {
      case "success":
        return <CheckCircle size={20} />;
      case "error":
        return <AlertCircle size={20} />;
      case "info":
        return <Info size={20} />;
      default:
        return null;
    }
  };

  return (
    <div className="fixed top-20 right-6 z-[100] space-y-3 pointer-events-none">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className={`p-4 rounded-lg border flex items-center gap-3 pointer-events-auto animate-in fade-in slide-in-from-right-4 duration-300 ${getBackgroundColor(
            toast.type
          )}`}
        >
          <div className={getIconColor(toast.type)}>
            {getIcon(toast.type)}
          </div>
          <p className="text-white text-sm">{toast.message}</p>
          <button
            onClick={() => removeToast(toast.id)}
            className="ml-auto text-gray-400 hover:text-white transition"
          >
            <X size={16} />
          </button>
        </div>
      ))}
    </div>
  );
}
