export default function LoadingScanner() {
    return (
        <div className="flex flex-col gap-3 p-4 bg-[#0D0D0D] border border-[#8B7355]">
            
            {/* Loading Bar */}
            <div className="loading-scanner"></div>

            {/* Status Text */}
            <div className="flex items-center gap-3 text-[#D4AF37] text-xs font-semibold uppercase tracking-wider">
                {/* Spinner */}
                <div className="w-4 h-4 border-2 border-[#D4AF37] border-t-transparent animate-spin"></div>
                
                {/* Text */}
                <span>Analyzing Vector Database...</span>
            </div>

            {/* Tactical Scan Line */}
            <div className="flex items-center gap-2">
                <div className="h-px flex-1 bg-gradient-to-r from-transparent via-[#D4AF37] to-transparent opacity-30"></div>
            </div>
        </div>
    );
}
