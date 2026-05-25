import Navbar from "../components/Navbar"
import Hero from "../components/Hero"
import About from "../components/About"
import PricingCards from "../components/PricingCards"
import MinimalNavbar from "../components/MinimalNavbar"
import { useState, useEffect } from "react"

export default function Home() {
  const [isLoggedIn, setIsLoggedIn] = useState(
    Boolean(localStorage.getItem("access_token"))
  );

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

  return (
    <div className="relative bg-black text-white overflow-hidden">

      {/* Tactical Grid Background */}
      <div className="tactical-grid"></div>

      {/* Gold Ambient Glow */}
      <div className="absolute top-[-300px] left-[-300px] w-[800px] h-[800px] bg-[#D4AF37] opacity-5 blur-[200px] rounded-full pointer-events-none"></div>
      <div className="absolute bottom-[-300px] right-[-300px] w-[800px] h-[800px] bg-[#D4AF37] opacity-5 blur-[200px] rounded-full pointer-events-none"></div>
      <div className="absolute top-[40%] left-[30%] w-[500px] h-[500px] bg-[#B8962E] opacity-5 blur-[180px] rounded-full pointer-events-none"></div>
      
      {/* CONTENT */}
      <div className="relative z-10">
        {isLoggedIn ? (
          <>
            <Navbar />
            <Hero />
            <About />
            <PricingCards />
          </>
        ) : (
          <>
            <MinimalNavbar />
            <Hero />
          </>
        )}
      </div>
    </div>
  );
}
