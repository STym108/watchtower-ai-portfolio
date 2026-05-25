export default function PricingCards() {
    return (
        <div className="relative py-24 px-6 overflow-hidden">
            {/* bg-gradient-to-br from-black via-zinc-900 to-black text-white */}
            {/* 🌌 Same Glow as Hero */}
            {/* <div className="absolute top-[-120px] left-[-120px] w-[500px] h-[500px] bg-cyan-500 opacity-10 blur-[150px] rounded-full"></div>
            <div className="absolute bottom-[-120px] right-[-120px] w-[500px] h-[500px] bg-purple-500 opacity-10 blur-[150px] rounded-full"></div>
            <div className="absolute top-[40%] left-[30%] w-[300px] h-[300px] bg-blue-500 opacity-5 blur-[120px] rounded-full"></div> */}

            <div className="relative z-10">

                {/* 🔥 Heading */}
                <h2 className="text-4xl md:text-5xl font-bold text-center mb-16 py-4 bg-gradient-to-r from-cyan-400 via-blue-500 to-purple-500 bg-clip-text text-transparent">
                    Pricing
                </h2>

                {/* Cards */}
                <div className="max-w-6xl mx-auto grid md:grid-cols-3 gap-10">

                    {/* Basic */}
                    <div className="p-6 rounded-xl bg-white/[0.03] backdrop-blur border border-white/10 hover:border-purple-400 transition duration-300">
                        <h3 className="text-xl font-bold text-cyan-400">Basic</h3>
                        <p className="mt-2 text-gray-400">Free</p>
                        <p className="mt-4 text-gray-300">
                            Upload local files
                        </p>
                    </div>

                    {/* Pro (highlighted) */}
                    <div className="p-6 rounded-xl bg-white/[0.03] backdrop-blur border border-white/10 hover:border-purple-400 transition duration-300">
                        <h3 className="text-xl font-bold text-cyan-400">Pro</h3>
                        <p className="mt-2 text-white">$49/mo</p>
                        <p className="mt-4 text-gray-300">
                            1 Live CCTV Stream integration
                        </p>
                    </div>

                    {/* Enterprise */}
                    <div className="p-6 rounded-xl bg-white/[0.03] backdrop-blur border border-white/10 hover:border-purple-400 transition duration-300">
                        <h3 className="text-xl font-bold text-cyan-400">Enterprise</h3>
                        <p className="mt-2 text-gray-400">Contact Us</p>
                        <p className="mt-4 text-gray-300">
                            Multi-camera WebRTC & unlimited alerts
                        </p>
                    </div>

                </div>
            </div>
        </div>
    );
}