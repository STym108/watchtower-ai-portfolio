import { useState } from "react";

export default function AuthModal({ isOpen, onClose, type }) {
    const [isLogin, setIsLogin] = useState(type === "login");

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur">

            {/* Modal Box */}
            <div className="w-full max-w-md p-[1.5px] rounded-xl bg-gradient-to-r from-cyan-400 to-purple-500">

                <div className="bg-black rounded-xl p-8 relative">

                    {/* Close Button */}
                    <button
                        onClick={onClose}
                        className="absolute top-3 right-3 text-gray-400 hover:text-white"
                    >
                        ✕
                    </button>

                    {/* Title */}
                    <h2 className="text-2xl font-bold mb-6 text-center bg-gradient-to-r from-cyan-400 to-purple-500 bg-clip-text text-transparent">
                        {isLogin ? "Login" : "Sign Up"}
                    </h2>

                    {/* Form */}
                    <div className="flex flex-col gap-4">

                        <input
                            type="email"
                            placeholder="Email"
                            className="p-3 rounded-lg bg-white/[0.05] border border-white/10 focus:border-cyan-400 outline-none"
                        />

                        <input
                            type="password"
                            placeholder="Password"
                            className="p-3 rounded-lg bg-white/[0.05] border border-white/10 focus:border-cyan-400 outline-none"
                        />

                        {/* Button */}
                        <button className="mt-4 p-[1.5px] rounded-lg bg-gradient-to-r from-cyan-400 to-purple-500">
                            <div className="bg-black rounded-lg py-2 font-semibold text-white hover:bg-gradient-to-r hover:from-cyan-400 hover:to-purple-500 hover:bg-clip-text hover:text-transparent transition">
                                {isLogin ? "Login" : "Create Account"}
                            </div>
                        </button>

                    </div>

                    {/* Switch */}
                    <p className="mt-6 text-sm text-center text-gray-400">
                        {isLogin ? "Don't have an account?" : "Already have an account?"}
                        <span
                            className="ml-2 cursor-pointer text-cyan-400 hover:underline"
                            onClick={() => setIsLogin(!isLogin)}
                        >
                            {isLogin ? "Sign Up" : "Login"}
                        </span>
                    </p>

                </div>
            </div>
        </div>
    );
}