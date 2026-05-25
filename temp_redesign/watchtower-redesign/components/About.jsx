import { Database, Cpu, Zap } from "lucide-react";

export default function About() {
  return (
    <div className="relative py-16 sm:py-20 md:py-24 px-4 sm:px-6 overflow-hidden">

      <div className="relative z-10 max-w-7xl mx-auto">

        {/* Heading */}
        <div className="text-center mb-12 sm:mb-16">
          <div className="inline-flex items-center gap-2 mb-4">
            <div className="w-8 h-px bg-[#D4AF37]"></div>
            <span className="text-xs text-[#D4AF37] uppercase tracking-[0.3em] font-semibold">System Architecture</span>
            <div className="w-8 h-px bg-[#D4AF37]"></div>
          </div>
          <h2 className="text-3xl sm:text-4xl md:text-5xl font-bold text-white mb-4">
            TACTICAL WORKFLOW
          </h2>
          <p className="text-gray-400 max-w-2xl mx-auto text-sm sm:text-base">
            Three-stage intelligence pipeline for real-time surveillance analysis
          </p>
        </div>

        {/* Cards */}
        <div className="grid sm:grid-cols-2 md:grid-cols-3 gap-6 sm:gap-8">

          {/* Stage 1 */}
          <div className="tactical-card p-6 sm:p-8 group">
            <div className="flex items-center gap-3 mb-6">
              <div className="w-12 h-12 flex items-center justify-center bg-[#D4AF37]/10 border border-[#D4AF37]">
                <Database size={24} className="text-[#D4AF37]" />
              </div>
              <div>
                <div className="text-xs text-[#8B7355] uppercase tracking-wider font-semibold">Phase 01</div>
                <h3 className="text-lg font-bold text-white">Vector Indexing</h3>
              </div>
            </div>
            <p className="text-gray-400 text-sm leading-relaxed">
              Video streams are processed and indexed into a Vector Database, creating semantic embeddings for intelligent retrieval.
            </p>
            <div className="mt-6 h-px bg-gradient-to-r from-[#D4AF37] to-transparent"></div>
          </div>

          {/* Stage 2 */}
          <div className="tactical-card p-6 sm:p-8 group">
            <div className="flex items-center gap-3 mb-6">
              <div className="w-12 h-12 flex items-center justify-center bg-[#D4AF37]/10 border border-[#D4AF37]">
                <Cpu size={24} className="text-[#D4AF37]" />
              </div>
              <div>
                <div className="text-xs text-[#8B7355] uppercase tracking-wider font-semibold">Phase 02</div>
                <h3 className="text-lg font-bold text-white">NLP Matching</h3>
              </div>
            </div>
            <p className="text-gray-400 text-sm leading-relaxed">
              Natural language queries are processed by AI and matched against video embeddings using advanced semantic search.
            </p>
            <div className="mt-6 h-px bg-gradient-to-r from-[#D4AF37] to-transparent"></div>
          </div>

          {/* Result */}
          <div className="tactical-card p-6 sm:p-8 group sm:col-span-2 md:col-span-1">
            <div className="flex items-center gap-3 mb-6">
              <div className="w-12 h-12 flex items-center justify-center bg-[#D4AF37]/10 border border-[#D4AF37]">
                <Zap size={24} className="text-[#D4AF37]" />
              </div>
              <div>
                <div className="text-xs text-[#8B7355] uppercase tracking-wider font-semibold">Phase 03</div>
                <h3 className="text-lg font-bold text-white">Instant Retrieval</h3>
              </div>
            </div>
            <p className="text-gray-400 text-sm leading-relaxed">
              Precise clip retrieval with exact timestamps, real-time alert triggering, and tactical event visualization.
            </p>
            <div className="mt-6 h-px bg-gradient-to-r from-[#D4AF37] to-transparent"></div>
          </div>

        </div>

        {/* Bottom Tactical Line */}
        <div className="mt-12 sm:mt-16 flex items-center justify-center gap-3">
          <div className="w-12 sm:w-20 h-px bg-gradient-to-r from-transparent to-[#D4AF37]"></div>
          <div className="w-2 h-2 border border-[#D4AF37] rotate-45"></div>
          <div className="w-12 sm:w-20 h-px bg-gradient-to-l from-transparent to-[#D4AF37]"></div>
        </div>
      </div>
    </div>
  );
}
