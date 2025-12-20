'use client';

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";
import { useNavigation } from "@/contexts/NavigationContext";
import { vehicleAPI } from "@/lib/api";
import Navbar from "../components/Navbar";
import LoadingSpinner from "../components/LoadingSpinner";
import VerificationModal from "../components/VerificationModal";

export default function PostVehicle() {
  const router = useRouter();
  const { isAuthenticated, loading: authLoading } = useAuth();
  const { startNavigating } = useNavigation();
  
  const [formData, setFormData] = useState({
    manufacturer: "",
    model: "",
    city: "",
    plate_number: "",
    year: "",
    vehicle_type: "",
    engine_capacity: "",
    transmission: "",
    fuel_type: "",
    mileage: "",
    price: "",
    description: "",
  });
  
  const [vehicleImages, setVehicleImages] = useState([]);
  const [imagePreviews, setImagePreviews] = useState([]);
  const [documentFile, setDocumentFile] = useState(null);
  const [documentPreview, setDocumentPreview] = useState(null);
  const [documentType] = useState("emission_test"); // Always emission test
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  
  // Verification states
  const [showVerificationModal, setShowVerificationModal] = useState(false);
  const [verificationResult, setVerificationResult] = useState(null);
  const [createdVehicleId, setCreatedVehicleId] = useState(null);

  // Redirect if not authenticated
  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.push("/login");
    }
  }, [isAuthenticated, authLoading, router]);

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleImageChange = (e) => {
    const files = Array.from(e.target.files);
    if (files.length > 0) {
      setVehicleImages(files);
      const previews = files.map(file => URL.createObjectURL(file));
      setImagePreviews(previews);
    }
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    const files = Array.from(e.dataTransfer.files).filter(file => file.type.startsWith('image/'));
    if (files.length > 0) {
      setVehicleImages(files);
      const previews = files.map(file => URL.createObjectURL(file));
      setImagePreviews(previews);
    }
  };

  const removeImage = (index) => {
    const newImages = vehicleImages.filter((_, i) => i !== index);
    const newPreviews = imagePreviews.filter((_, i) => i !== index);
    setVehicleImages(newImages);
    setImagePreviews(newPreviews);
  };

  const handleDocumentChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      setDocumentFile(file);
      const preview = URL.createObjectURL(file);
      setDocumentPreview(preview);
    }
  };

  const removeDocument = () => {
    setDocumentFile(null);
    setDocumentPreview(null);
    if (document.getElementById('document-input')) {
      document.getElementById('document-input').value = '';
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const data = new FormData();
      
      // Append all form fields
      Object.keys(formData).forEach((key) => {
        if (formData[key]) {
          data.append(key, formData[key]);
        }
      });
      
      // Append images if exist
      vehicleImages.forEach((image) => {
        data.append("images", image);
      });

      // Validate and append document (required)
      if (!documentFile) {
        setError("Please upload an Emission Test Certificate. This is required for verification.");
        setLoading(false);
        return;
      }
      
      data.append("document", documentFile);
      data.append("document_type", "emission_test"); // Always emission test

      // Create the vehicle
      const createdVehicle = await vehicleAPI.createVehicle(data);
      setCreatedVehicleId(createdVehicle.id);
      
      // If vehicle has images, trigger verification automatically
      if (vehicleImages.length > 0) {
        setShowVerificationModal(true);
        
        // Set initial verification state
        setVerificationResult({
          verification_status: 'in_progress',
          verification_result: null
        });
        
        // Trigger verification
        try {
          const verificationResponse = await vehicleAPI.verifyVehicle(createdVehicle.id);
          
          setVerificationResult({
            verification_status: verificationResponse.verification_status,
            verification_result: verificationResponse.verification_result
          });
          
        } catch (verifyError) {
          console.error("Verification error:", verifyError);
          setVerificationResult({
            verification_status: 'failed',
            verification_result: {
              error_message: verifyError.message || "Verification failed"
            }
          });
        }
      } else {
        // No images, skip verification and navigate directly
        alert("Vehicle posted successfully!");
        startNavigating();
        router.push("/my-ads");
      }
      
      setLoading(false);
      
    } catch (err) {
      // Handle duplicate plate number error
      const errorMessage = err.detail || err.message || "Failed to post vehicle. Please try again.";
      setError(errorMessage);
      setLoading(false);
    }
  };

  const handleVerificationClose = () => {
    setShowVerificationModal(false);
    
    // Navigate to my-ads based on verification status
    const status = verificationResult?.verification_status;
    
    if (status === 'verified') {
      alert("🎉 Vehicle verified and posted successfully!");
    } else if (status === 'manual_review') {
      alert("⚠️ Your vehicle is pending manual review. You'll be notified once approved.");
    } else if (status === 'failed') {
      alert("❌ Verification failed. Your listing has been saved but may need corrections.");
    }
    
    startNavigating();
    router.push("/my-ads");
  };

  const handleVerificationRetry = async () => {
    if (!createdVehicleId) return;
    
    setVerificationResult({
      verification_status: 'in_progress',
      verification_result: null
    });
    
    try {
      const retryResponse = await vehicleAPI.retryVerification(createdVehicleId);
      
      setVerificationResult({
        verification_status: retryResponse.verification_status,
        verification_result: retryResponse.verification_result
      });
      
    } catch (error) {
      console.error("Retry verification error:", error);
      setVerificationResult({
        verification_status: 'failed',
        verification_result: {
          error_message: error.message || "Retry failed"
        }
      });
    }
  };

  if (authLoading) {
    return (
      <div className="min-h-screen bg-gray-50">
        <Navbar />
        <div className="flex items-center justify-center h-96">
          <LoadingSpinner size="lg" text="Checking authentication..." />
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return null;
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />
      
      {/* Verification Modal */}
      <VerificationModal
        isOpen={showVerificationModal}
        vehicleId={createdVehicleId}
        verificationResult={verificationResult}
        onClose={handleVerificationClose}
        onRetry={handleVerificationRetry}
      />
      
      <div className="container mx-auto px-4 py-8">
        <div className="max-w-3xl mx-auto bg-white shadow-2xl rounded-2xl p-8">
          <h1 className="text-3xl font-bold text-center text-purple-700 mb-6">
            🚗 Post Your Vehicle
          </h1>

          {error && (
            <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4">
              {error}
            </div>
          )}

          <form className="space-y-6" onSubmit={handleSubmit}>
            {/* Basic Information */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-gray-700 font-medium mb-2">Manufacturer *</label>
                <input
                  type="text"
                  name="manufacturer"
                  placeholder="e.g., Toyota, Honda"
                  value={formData.manufacturer}
                  onChange={handleChange}
                  className="w-full border border-gray-300 rounded-lg px-4 py-3 text-gray-900 focus:ring-2 focus:ring-purple-500 focus:outline-none"
                  required
                />
              </div>

              <div>
                <label className="block text-gray-700 font-medium mb-2">Model *</label>
                <input
                  type="text"
                  name="model"
                  placeholder="e.g., Civic, Corolla"
                  value={formData.model}
                  onChange={handleChange}
                  className="w-full border border-gray-300 rounded-lg px-4 py-3 text-gray-900 focus:ring-2 focus:ring-purple-500 focus:outline-none"
                  required
                />
              </div>

              <div>
                <label className="block text-gray-700 font-medium mb-2">City</label>
                <input
                  type="text"
                  name="city"
                  placeholder="e.g., Colombo"
                  value={formData.city}
                  onChange={handleChange}
                  className="w-full border border-gray-300 rounded-lg px-4 py-3 text-gray-900 focus:ring-2 focus:ring-purple-500 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-gray-700 font-medium mb-2">
                  Plate Number <span className="text-red-500">*</span>
                  <span className="text-sm text-gray-500 font-normal ml-2">(Must be unique)</span>
                </label>
                <input
                  type="text"
                  name="plate_number"
                  placeholder="e.g., ABC-1234"
                  value={formData.plate_number}
                  onChange={handleChange}
                  className="w-full border border-gray-300 rounded-lg px-4 py-3 text-gray-900 focus:ring-2 focus:ring-purple-500 focus:outline-none"
                  required
                />
                <p className="text-xs text-gray-500 mt-1">
                  The AI will verify this plate number matches the images you upload
                </p>
              </div>

              <div>
                <label className="block text-gray-700 font-medium mb-2">Year</label>
                <input
                  type="number"
                  name="year"
                  placeholder="e.g., 2020"
                  value={formData.year}
                  onChange={handleChange}
                  min="1900"
                  max={new Date().getFullYear() + 1}
                  className="w-full border border-gray-300 rounded-lg px-4 py-3 text-gray-900 focus:ring-2 focus:ring-purple-500 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-gray-700 font-medium mb-2">Vehicle Type</label>
                <select
                  name="vehicle_type"
                  value={formData.vehicle_type}
                  onChange={handleChange}
                  className="w-full border border-gray-300 rounded-lg px-4 py-3 text-gray-900 focus:ring-2 focus:ring-purple-500 focus:outline-none"
                >
                  <option value="">Select Type</option>
                  <option value="Car">Car</option>
                  <option value="SUV">SUV</option>
                  <option value="Van">Van</option>
                  <option value="Bike">Bike</option>
                  <option value="Three-Wheeler">Three-Wheeler</option>
                  <option value="Truck">Truck</option>
                  <option value="Lorry">Lorry</option>
                </select>
              </div>
            </div>

            {/* Technical Specifications */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-gray-700 font-medium mb-2">Engine Capacity</label>
                <input
                  type="text"
                  name="engine_capacity"
                  placeholder="e.g., 1500cc"
                  value={formData.engine_capacity}
                  onChange={handleChange}
                  className="w-full border border-gray-300 rounded-lg px-4 py-3 text-gray-900 focus:ring-2 focus:ring-purple-500 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-gray-700 font-medium mb-2">Transmission</label>
                <select
                  name="transmission"
                  value={formData.transmission}
                  onChange={handleChange}
                  className="w-full border border-gray-300 rounded-lg px-4 py-3 text-gray-900 focus:ring-2 focus:ring-purple-500 focus:outline-none"
                >
                  <option value="">Select Transmission</option>
                  <option value="Manual">Manual</option>
                  <option value="Automatic">Automatic</option>
                  <option value="Semi-Automatic">Semi-Automatic</option>
                </select>
              </div>

              <div>
                <label className="block text-gray-700 font-medium mb-2">Fuel Type</label>
                <select
                  name="fuel_type"
                  value={formData.fuel_type}
                  onChange={handleChange}
                  className="w-full border border-gray-300 rounded-lg px-4 py-3 text-gray-900 focus:ring-2 focus:ring-purple-500 focus:outline-none"
                >
                  <option value="">Select Fuel Type</option>
                  <option value="Petrol">Petrol</option>
                  <option value="Diesel">Diesel</option>
                  <option value="Electric">Electric</option>
                  <option value="Hybrid">Hybrid</option>
                </select>
              </div>

              <div>
                <label className="block text-gray-700 font-medium mb-2">Mileage (km)</label>
                <input
                  type="text"
                  name="mileage"
                  placeholder="e.g., 50000"
                  value={formData.mileage}
                  onChange={handleChange}
                  className="w-full border border-gray-300 rounded-lg px-4 py-3 text-gray-900 focus:ring-2 focus:ring-purple-500 focus:outline-none"
                />
              </div>
            </div>

            {/* Price */}
            <div>
              <label className="block text-gray-700 font-medium mb-2">Price (LKR)</label>
              <input
                type="number"
                name="price"
                placeholder="e.g., 5000000"
                value={formData.price}
                onChange={handleChange}
                className="w-full border border-gray-300 rounded-lg px-4 py-3 text-gray-900 focus:ring-2 focus:ring-purple-500 focus:outline-none"
              />
            </div>

            {/* Description */}
            <div>
              <label className="block text-gray-700 font-medium mb-2">Description</label>
              <textarea
                name="description"
                placeholder="Provide a detailed description of your vehicle (condition, features, history, etc.)"
                value={formData.description}
                onChange={handleChange}
                rows={5}
                className="w-full border border-gray-300 rounded-lg px-4 py-3 text-gray-900 focus:ring-2 focus:ring-purple-500 focus:outline-none resize-vertical"
              />
            </div>

            {/* Document Upload Section */}
            <div className="bg-blue-50 border-2 border-blue-200 rounded-xl p-6">
              <label className="block text-gray-700 font-bold mb-3 text-lg">
                📄 Emission Test Certificate (Required) *
              </label>
              <p className="text-sm text-gray-600 mb-4">
                Please upload your vehicle's <strong>Emission Test Certificate</strong> that clearly shows:
                <br />• Fuel Type • Vehicle Class • Model Year • Manufacturer • Model • Registration No
              </p>
              
              {formData.fuel_type === 'Electric' && (
                <div className="mb-4 p-3 bg-yellow-50 border border-yellow-300 rounded-lg">
                  <p className="text-sm text-yellow-800">
                    <strong>Note for Electric Vehicles:</strong> If your electric vehicle doesn't have an emission test certificate, 
                    please upload any official vehicle registration document that shows the required vehicle details.
                  </p>
                </div>
              )}
              
              <input type="hidden" name="document_type" value="emission_test" />

              {!documentPreview ? (
                <div className="border-2 border-dashed border-blue-300 rounded-xl p-8 text-center bg-white">
                  <input
                    type="file"
                    accept="image/*,.pdf"
                    onChange={handleDocumentChange}
                    className="hidden"
                    id="document-input"
                    required
                  />
                  <label
                    htmlFor="document-input"
                    className="cursor-pointer flex flex-col items-center justify-center space-y-3"
                  >
                    <div className="text-5xl">📄</div>
                    <div className="space-y-1">
                      <p className="text-gray-700 font-semibold">Click to upload document</p>
                      <p className="text-sm text-gray-500">PNG, JPG, PDF up to 10MB</p>
                    </div>
                    <button
                      type="button"
                      onClick={() => document.getElementById('document-input').click()}
                      className="mt-2 px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition font-medium"
                    >
                      Browse Files
                    </button>
                  </label>
                </div>
              ) : (
                <div className="relative">
                  <div className="border-2 border-blue-300 rounded-lg p-4 bg-white">
                    {documentPreview && documentFile.type.startsWith('image/') ? (
                      <img
                        src={documentPreview}
                        alt="Document preview"
                        className="max-w-full h-auto max-h-64 mx-auto rounded"
                      />
                    ) : (
                      <div className="text-center py-8">
                        <div className="text-5xl mb-2">📄</div>
                        <p className="text-gray-700 font-semibold">{documentFile.name}</p>
                        <p className="text-sm text-gray-500">PDF Document</p>
                      </div>
                    )}
                    <div className="mt-3 text-center">
                      <p className="text-sm text-gray-600">
                        <strong>Type:</strong> Emission Test Certificate
                      </p>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={removeDocument}
                    className="absolute top-2 right-2 bg-red-500 text-white rounded-full w-8 h-8 flex items-center justify-center hover:bg-red-600 transition shadow-md"
                    title="Remove document"
                  >
                    ×
                  </button>
                </div>
              )}
            </div>

            {/* Images Upload */}
            <div>
              <label className="block text-gray-700 font-medium mb-3">Vehicle Images</label>
              
              {/* Upload Area */}
              <div
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                className={`relative border-2 border-dashed rounded-xl p-8 text-center transition-all duration-200 ${
                  isDragging
                    ? 'border-purple-500 bg-purple-50'
                    : 'border-purple-300 bg-purple-50/50 hover:border-purple-400 hover:bg-purple-50'
                }`}
              >
                <input
                  type="file"
                  accept="image/*"
                  multiple
                  onChange={handleImageChange}
                  className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                  id="vehicle-images-input"
                />
                <div className="flex flex-col items-center justify-center space-y-3">
                  <div className="text-5xl">📸</div>
                  <div className="space-y-1">
                    <p className="text-gray-700 font-semibold">
                      {imagePreviews.length > 0 
                        ? `${imagePreviews.length} image${imagePreviews.length > 1 ? 's' : ''} selected`
                        : 'Click to upload or drag and drop'
                      }
                    </p>
                    <p className="text-sm text-gray-500">
                      {imagePreviews.length > 0 
                        ? 'Click to change or add more images'
                        : 'PNG, JPG, GIF up to 10MB (first image will be primary)'
                      }
                    </p>
                  </div>
                  {imagePreviews.length === 0 && (
                    <button
                      type="button"
                      onClick={() => document.getElementById('vehicle-images-input').click()}
                      className="mt-2 px-6 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition font-medium"
                    >
                      Browse Files
                    </button>
                  )}
                </div>
              </div>
              
              {/* Image Previews */}
              {imagePreviews.length > 0 && (
                <div className="mt-6">
                  <p className="text-sm text-gray-600 mb-3 font-medium">
                    {imagePreviews.length} image{imagePreviews.length > 1 ? 's' : ''} selected
                  </p>
                  <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                    {imagePreviews.map((preview, index) => (
                      <div key={index} className="relative group">
                        <div className="relative aspect-video rounded-lg overflow-hidden border-2 border-gray-200 hover:border-purple-400 transition">
                          <img
                            src={preview}
                            alt={`Preview ${index + 1}`}
                            className="w-full h-full object-cover"
                          />
                          {index === 0 && (
                            <span className="absolute top-2 left-2 bg-green-500 text-white text-xs px-2 py-1 rounded font-semibold shadow-md">
                              Primary
                            </span>
                          )}
                          <button
                            type="button"
                            onClick={() => removeImage(index)}
                            className="absolute top-2 right-2 bg-red-500 text-white rounded-full w-7 h-7 flex items-center justify-center hover:bg-red-600 transition shadow-md opacity-0 group-hover:opacity-100"
                            title="Remove image"
                          >
                            ×
                          </button>
                        </div>
                        <p className="text-xs text-gray-500 mt-1 text-center truncate">
                          Image {index + 1}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Submit Button */}
            <button
              type="submit"
              disabled={loading}
              className="w-full bg-yellow-400 text-purple-900 font-bold text-lg px-6 py-4 rounded-lg hover:bg-yellow-500 transition disabled:bg-gray-400 disabled:cursor-not-allowed"
            >
              {loading ? "Posting..." : "🚗 Post Vehicle"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
