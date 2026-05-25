import { Link } from "react-router-dom";
import { Shield, Zap, Target } from "lucide-react";

export default function Hero() {
  return (
    <div className="relative min-h-screen w-full overflow-hidden">
      
      {/* Tactical Grid Background */}
      <div className="absolute inset-0 tactical-grid opacity-10"></div>

      {/* Scan Line Effect */}
      <div className="absolute inset-0 scan-line opacity-30"></div>

      {/* Content */}
      <div className="relative z-10 flex flex-col items-center justify-center min-h-screen text-center px-4 sm:px-6 py-20">

        {/* Top Badge */}
        <div className="mb-6 sm:mb-8 px-4 sm:px-6 py-2 border border-[#D4AF37] bg-[#D4AF37]/10 text-[#D4AF37] text-xs sm:text-sm font-semibold tracking-[0.15em] uppercase inline-flex items-center gap-2">
          <Shield size={14} />
          AI-POWERED SURVEILLANCE
        </div>

        {/* Main Title */}
        <h1 className="text-4xl sm:text-5xl md:text-6xl lg:text-7xl font-bold leading-tight mb-4 sm:mb-6">
          <span className="block text-white">WATCHTOWER</span>
          <span className="block bg-gradient-to-r from-[#D4AF37] via-[#F4D03F] to-[#D4AF37] bg-clip-text text-transparent">
            TACTICAL EDGE
          </span>
        </h1>

        {/* Subtitle */}
        <p className="mt-4 text-base sm:text-lg md:text-xl text-gray-300 max-w-2xl leading-relaxed px-4">
          Transform CCTV into searchable intelligence. Query thousands of hours using natural language.
          <span className="block mt-2 text-[#D4AF37] font-semibold">Precision. Security. Advanced Technology.</span>
        </p>

        {/* Feature Pills */}
        <div className="mt-8 flex flex-wrap justify-center gap-3 sm:gap-4 px-4">
          <div className="px-3 sm:px-4 py-2 bg-[#0D0D0D] border border-[#8B7355] text-gray-300 text-xs sm:text-sm flex items-center gap-2">
            <Zap size={14} className="text-[#D4AF37]" />
            <span>Real-time Detection</span>
          </div>
          <div className="px-3 sm:px-4 py-2 bg-[#0D0D0D] border border-[#8B7355] text-gray-300 text-xs sm:text-sm flex items-center gap-2">
            <Target size={14} className="text-[#D4AF37]" />
            <span>NLP Query Engine</span>
          </div>
          <div className="px-3 sm:px-4 py-2 bg-[#0D0D0D] border border-[#8B7355] text-gray-300 text-xs sm:text-sm flex items-center gap-2">
            <Shield size={14} className="text-[#D4AF37]" />
            <span>Video-RAG Powered</span>
          </div>
        </div>

        {/* CTA Buttons */}
        <div className="mt-10 sm:mt-12 flex flex-col sm:flex-row gap-4 px-4">

          {/* Get Started */}
          <Link to="/signup">
            <button className="btn-tactical w-full sm:w-auto px-8 sm:px-10 py-3 sm:py-4">
              Deploy System
            </button>
          </Link>

          {/* Live Demo */}
          <Link to="/uploaddropzone">
            <button className="w-full sm:w-auto px-8 sm:px-10 py-3 sm:py-4 bg-transparent border-2 border-[#D4AF37] text-[#D4AF37] hover:bg-[#D4AF37] hover:text-black transition-all font-semibold tracking-wide uppercase text-sm">
              Live Demo
            </button>
          </Link>

        </div>

        {/* Bottom Tactical Lines */}
        <div className="absolute bottom-8 left-1/2 transform -translate-x-1/2 flex items-center gap-2">
          <div className="w-12 sm:w-16 h-px bg-gradient-to-r from-transparent to-[#D4AF37]"></div>
          <div className="w-2 h-2 border border-[#D4AF37] rotate-45"></div>
          <div className="w-12 sm:w-16 h-px bg-gradient-to-l from-transparent to-[#D4AF37]"></div>
        </div>

      </div>

      {/* Corner Tactical Markers */}
      <div className="absolute top-4 left-4 w-12 h-12 border-l-2 border-t-2 border-[#D4AF37] opacity-40"></div>
      <div className="absolute top-4 right-4 w-12 h-12 border-r-2 border-t-2 border-[#D4AF37] opacity-40"></div>
      <div className="absolute bottom-4 left-4 w-12 h-12 border-l-2 border-b-2 border-[#D4AF37] opacity-40"></div>
      <div className="absolute bottom-4 right-4 w-12 h-12 border-r-2 border-b-2 border-[#D4AF37] opacity-40"></div>

    </div>
  )
}
