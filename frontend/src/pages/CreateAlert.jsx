import { useState } from "react";
import axios from "axios";
import Navbar from "../components/Navbar";

export default function CreateAlert() {
    const [condition, setCondition] = useState("");
    const [loading, setLoading] = useState(false);

    const handleCreate = async () => {
        if (!condition.trim()) return;

        try {
            setLoading(true);

            await axios.post("http://localhost:8000/api/alerts/setup", {
                condition,
            });

            alert("✅ Alert created successfully!");
            setCondition("");

        } catch (err) {
            console.error(err);
            alert("❌ Failed to create alert");
        }

        setLoading(false);
    };

    return (
        <div className="min-h-screen bg-gradient-to-br from-black via-zinc-900 to-black text-white">

            <Navbar />

            <div className="flex justify-center items-center pt-32 sm:pt-40 px-4">

                <div className="w-full max-w-2xl p-[1.5px] rounded-xl bg-gradient-to-r from-[#D4AF37] to-[#B8962E]">

                    <div className="bg-black rounded-xl p-8">

                        <h2 className="text-3xl font-bold mb-6 bg-gradient-to-r from-[#D4AF37] to-[#B8962E] bg-clip-text text-transparent">
                            Create Alert
                        </h2>

                        <textarea
                            value={condition}
                            onChange={(e) => setCondition(e.target.value)}
                            placeholder="e.g. Someone loitering near the backdoor"
                            className="w-full h-32 p-4 rounded-lg bg-white/[0.05] border border-white/10 outline-none focus:border-[#D4AF37]"
                        />

                        <button
                            onClick={handleCreate}
                            className="mt-6 w-full py-3 rounded-lg bg-gradient-to-r from-[#D4AF37] to-[#B8962E] text-black font-semibold"
                        >
                            {loading ? "Creating..." : "Create Alert"}
                        </button>

                    </div>
                </div>
            </div>
        </div>
    );
}