export default function TripWireTable({ alerts, telegramHandle }) {
    return (
        <div className="space-y-4">

            {alerts.length === 0 && (
                <p className="text-gray-500 text-center">
                    No active alerts yet.
                </p>
            )}

            {alerts.map((alert) => (
                <div
                    key={alert.id}
                    className="p-6 rounded-xl bg-white/[0.03] backdrop-blur border border-white/10 hover:border-[#D4AF37] transition"
                >
                    <div className="flex justify-between items-center">

                        <p className="text-gray-200">{alert.text}</p>

                        <span className="text-green-400 animate-pulse text-sm">
                            🟢 Active
                        </span>

                    </div>

                    <p className="text-sm text-gray-400 mt-2">
                        Routing notifications to{" "}
                        <span className="text-[#D4AF37]">
                            {telegramHandle}
                        </span>
                    </p>

                </div>
            ))}

        </div>
    );
}