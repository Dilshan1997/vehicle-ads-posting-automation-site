"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";
import { useNavigation } from "@/contexts/NavigationContext";

export default function LoginPage() {
  const router = useRouter();
  const { login, isAuthenticated, loading: authLoading } = useAuth();
  const { startNavigating } = useNavigation();
  const [formData, setFormData] = useState({
    email: "",
    password: "",
  });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [showResendVerification, setShowResendVerification] = useState(false);

  // Redirect if already authenticated
  useEffect(() => {
    if (!authLoading && isAuthenticated) {
      router.replace("/vehicles");
    }
  }, [isAuthenticated, authLoading, router]);

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const result = await login(formData.email, formData.password);

      if (result && result.success) {
        // Show loading bar
        startNavigating();

        // Wait a moment for auth state to update
        await new Promise((resolve) => setTimeout(resolve, 200));

        // Try router navigation first
        try {
          router.replace("/vehicles");
        } catch (routerError) {
          console.warn(
            "Router navigation failed, using window.location:",
            routerError
          );
          // Fallback to window.location if router fails
          window.location.href = "/vehicles";
        }
      } else {
        const errorMessage =
          result?.error ||
          result?.message ||
          "Login failed. Please check your credentials.";
        setError(errorMessage);

        // Check if error is about email verification
        if (
          errorMessage.toLowerCase().includes("verify") ||
          errorMessage.toLowerCase().includes("verification")
        ) {
          setShowResendVerification(true);
        } else {
          setShowResendVerification(false);
        }

        setLoading(false);
      }
    } catch (err) {
      console.error("Login error:", err);
      setError(err.message || "An error occurred. Please try again.");
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-purple-100 to-blue-100">
      <div className="bg-white shadow-2xl rounded-2xl p-8 w-full max-w-md">
        <h1 className="text-3xl font-bold text-center text-purple-700 mb-6">
          🔑 Login to Your Account
        </h1>

        {error && (
          <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4">
            {error}
            {showResendVerification && (
              <div className="mt-3 pt-3 border-t border-red-300">
                <p className="text-sm mb-2">
                  Need to resend the verification email?
                </p>
                <button
                  onClick={() => {
                    startNavigating();
                    router.push(
                      `/resend-verification?email=${encodeURIComponent(
                        formData.email
                      )}`
                    );
                  }}
                  className="text-sm text-red-700 font-semibold hover:underline"
                >
                  Resend Verification Email →
                </button>
              </div>
            )}
          </div>
        )}

        <form className="space-y-4" onSubmit={handleSubmit}>
          <div>
            <label className="block text-gray-700 font-medium mb-2">
              Email
            </label>
            <input
              type="email"
              name="email"
              placeholder="Enter your email"
              value={formData.email}
              onChange={handleChange}
              className="w-full border border-gray-300 rounded-lg px-4 py-3 text-gray-900 focus:ring-2 focus:ring-purple-500 focus:outline-none"
              required
            />
          </div>

          <div>
            <label className="block text-gray-700 font-medium mb-2">
              Password
            </label>
            <input
              type="password"
              name="password"
              placeholder="Enter your password"
              value={formData.password}
              onChange={handleChange}
              className="w-full border border-gray-300 rounded-lg px-4 py-3 text-gray-900 focus:ring-2 focus:ring-purple-500 focus:outline-none"
              required
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-purple-700 text-white py-3 rounded-lg font-semibold hover:bg-purple-800 transition disabled:bg-gray-400 disabled:cursor-not-allowed"
          >
            {loading ? "Logging in..." : "Login"}
          </button>
        </form>

        <p className="text-center text-gray-600 mt-6">
          Don't have an account?{" "}
          <button
            onClick={() => {
              startNavigating();
              router.push("/register");
            }}
            className="text-purple-700 font-semibold hover:underline"
          >
            Register
          </button>
        </p>

        <p className="text-center mt-4">
          <button
            onClick={() => {
              startNavigating();
              router.push("/");
            }}
            className="text-sm text-gray-500 hover:underline"
          >
            ← Back to Home
          </button>
        </p>
      </div>
    </div>
  );
}
