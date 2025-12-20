# ads_post/models.py
from django.db import models
from django.conf import settings

class VehicleCategory(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

class Vehicle(models.Model):
    VERIFICATION_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('verified', 'Verified'),
        ('failed', 'Failed'),
        ('manual_review', 'Manual Review Required'),
    ]
    
    posted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='vehicles')
    category = models.ForeignKey(VehicleCategory, on_delete=models.SET_NULL, null=True, blank=True)
    manufacturer = models.CharField(max_length=120)
    model = models.CharField(max_length=120)
    city = models.CharField(max_length=120, blank=True, null=True)
    plate_number = models.CharField(max_length=50, blank=True, null=True, unique=True, db_index=True)
    year = models.PositiveSmallIntegerField(blank=True, null=True)
    vehicle_type = models.CharField(max_length=80, blank=True, null=True)
    engine_capacity = models.CharField(max_length=50, blank=True, null=True)
    transmission = models.CharField(max_length=50, blank=True, null=True)
    fuel_type = models.CharField(max_length=50, blank=True, null=True)
    mileage = models.CharField(max_length=50, blank=True, null=True)
    price = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    description = models.TextField(blank=True, null=True, help_text="Detailed description of the vehicle")
    
    # Verification fields
    verification_status = models.CharField(max_length=20, choices=VERIFICATION_STATUS_CHOICES, default='pending')
    is_verified = models.BooleanField(default=False)
    verification_score = models.FloatField(null=True, blank=True, help_text="AI confidence score (0-100)")
    verification_attempts = models.PositiveIntegerField(default=0)
    last_verification_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.manufacturer} {self.model}"

class VehicleImage(models.Model):
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='vehicles/')
    is_primary = models.BooleanField(default=False)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-is_primary', 'uploaded_at']

    def __str__(self):
        return f"Image for {self.vehicle}"


class VehicleDocument(models.Model):
    """Stores vehicle documents (emission test certificate or ownership book)"""
    DOCUMENT_TYPE_CHOICES = [
        ('emission_test', 'Emission Test Certificate'),
        ('ownership_book', 'Ownership Book'),
    ]
    
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name='documents')
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPE_CHOICES)
    document_file = models.FileField(upload_to='vehicle_documents/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    # Extracted information from document (populated by AI)
    extracted_data = models.JSONField(null=True, blank=True, help_text="Vehicle details extracted from document by AI")
    extraction_confidence = models.FloatField(null=True, blank=True, help_text="Confidence score for extraction (0-100)")
    extraction_completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-uploaded_at']
        verbose_name = 'Vehicle Document'
        verbose_name_plural = 'Vehicle Documents'
    
    def __str__(self):
        return f"{self.get_document_type_display()} for {self.vehicle}"


class VehicleVerificationResult(models.Model):
    """Stores detailed AI verification results for vehicle listings"""
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name='verification_results')
    
    # AI detected information
    ai_detected_brand = models.CharField(max_length=120, null=True, blank=True)
    ai_detected_model = models.CharField(max_length=120, null=True, blank=True)
    ai_detected_vehicle_type = models.CharField(max_length=80, null=True, blank=True)
    ai_detected_fuel_type = models.CharField(max_length=50, null=True, blank=True)
    ai_detected_year = models.CharField(max_length=20, null=True, blank=True)
    ai_detected_plate_number = models.CharField(max_length=50, null=True, blank=True, help_text="Plate number detected from images by AI")
    
    # Document-based information (from emission test or ownership book)
    document_fuel_type = models.CharField(max_length=50, null=True, blank=True, help_text="Fuel type extracted from document")
    document_vehicle_class = models.CharField(max_length=80, null=True, blank=True, help_text="Vehicle class from document")
    document_model_year = models.CharField(max_length=20, null=True, blank=True, help_text="Model year from document")
    document_manufacturer = models.CharField(max_length=120, null=True, blank=True, help_text="Manufacturer from document")
    document_plate_number = models.CharField(max_length=50, null=True, blank=True, help_text="Plate number from document")
    document_match_score = models.FloatField(null=True, blank=True, help_text="Overall match score between form data and document (0-100)")
    
    # Verification scores (0-100)
    brand_match_score = models.FloatField(null=True, blank=True)
    model_match_score = models.FloatField(null=True, blank=True)
    vehicle_type_match_score = models.FloatField(null=True, blank=True)
    fuel_type_match_score = models.FloatField(null=True, blank=True)
    plate_number_match_score = models.FloatField(null=True, blank=True, help_text="Match score for plate number (0-100)")
    image_quality_score = models.FloatField(null=True, blank=True)
    overall_confidence_score = models.FloatField(null=True, blank=True)
    
    # Image validation
    is_vehicle_image = models.BooleanField(default=False)
    images_analyzed_count = models.PositiveIntegerField(default=0)
    
    # AI response metadata
    ai_raw_response = models.JSONField(null=True, blank=True, help_text="Complete AI response for debugging")
    ai_suggestions = models.TextField(null=True, blank=True, help_text="AI suggestions for improvement")
    discrepancies = models.JSONField(null=True, blank=True, help_text="List of discrepancies found")
    
    # Status and tracking
    verification_passed = models.BooleanField(default=False)
    requires_manual_review = models.BooleanField(default=False)
    error_message = models.TextField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Vehicle Verification Result'
        verbose_name_plural = 'Vehicle Verification Results'
    
    def __str__(self):
        return f"Verification for {self.vehicle} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"
