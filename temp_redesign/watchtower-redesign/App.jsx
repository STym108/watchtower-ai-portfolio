import { Routes, Route, Link } from "react-router-dom";
import Home from "./pages/Home";
import Dashboard from "./pages/Dashboard";
import Profile from "./pages/Profile";
import Tripwires from "./pages/TripWires";
import Login from "./pages/Login";
import Signup from "./pages/Signup";
import UploadDropzone from "./components/UploadDropZone";
import MyProfile from "./pages/MyProfile";
import CreateAlert from "./pages/CreateAlert";
import LiveStream from "./pages/LiveStream";
import Toast from "./components/Toast";

export default function App() {
  return (
    <div className="min-h-screen bg-black text-white">
      <Toast />
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/tripwires" element={<Tripwires />} />

        {/* 🔥 ADD THESE */}
        <Route path="/login" element={<Login />} />
        <Route path="/signup" element={<Signup />} />
        <Route path="/me/edit" element={<Profile />} />
        <Route path="/uploaddropzone" element={<UploadDropzone />} />
        <Route path="/me" element={<MyProfile />} />
        <Route path="/alerts/create" element={<CreateAlert />} />
        <Route path="/livestream" element={<LiveStream />} />

      </Routes>
    </div>
  );
}
