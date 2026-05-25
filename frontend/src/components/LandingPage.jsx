import { Link } from "react-router-dom";

export default function LandingPage() {
  return (
    <div className="relative min-h-screen w-full flex items-center justify-center px-4 pt-24">
      {/* Parent Container - Flex centered */}
      <div className="flex gap-12">
        
        {/* Login Option */}
        <div className="w-full sm:w-auto p-[1.5px] rounded-2xl bg-gradient-to-r from-[#D4AF37] to-[#B8962E]">
          <div className="bg-black rounded-2xl p-8 sm:p-10 min-w-[320px] text-center">
            <h2 className="text-2xl font-bold mb-4 text-white">
              Already have an account?
            </h2>
            <p className="text-gray-400 mb-8">
              Sign in to access your CCTV AI dashboard
            </p>
            <Link to="/login" className="w-full block">
              <div className="p-[1.5px] rounded-lg bg-gradient-to-r from-[#D4AF37] to-[#B8962E]">
                <button className="w-full px-6 py-3 rounded-lg bg-black font-semibold text-white hover:bg-gradient-to-r hover:from-[#D4AF37] hover:to-[#B8962E] transition-all duration-300">
                  Login
                </button>
              </div>
            </Link>
          </div>
        </div>

        {/* Signup Option */}
        <div className="p-[1.5px] rounded-2xl bg-gradient-to-r from-[#D4AF37] to-[#B8962E]">
          <div className="bg-black rounded-2xl p-8 sm:p-10 min-w-[320px] text-center">
            <h2 className="text-2xl font-bold mb-4 text-white">
              New user?
            </h2>
            <p className="text-gray-400 mb-8">
              Create an account and join our surveillance intelligence platform
            </p>
            <Link to="/signup" className="w-full block">
              <div className="p-[1.5px] rounded-lg bg-gradient-to-r from-[#D4AF37] to-[#B8962E]">
                <button className="w-full px-6 py-3 rounded-lg bg-black font-semibold text-white hover:bg-gradient-to-r hover:from-[#D4AF37] hover:to-[#B8962E] transition-all duration-300">
                  Sign Up
                </button>
              </div>
            </Link>
          </div>
        </div>

      </div>
    </div>
  );
}
