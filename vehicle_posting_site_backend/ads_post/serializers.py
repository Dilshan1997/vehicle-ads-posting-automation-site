# ads_post/serializers.py
from rest_framework import serializers
from .models import Vehicle, VehicleCategory, VehicleImage, VehicleVerificationResult, VehicleDocument
from django.conf import settings

class VehicleCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = VehicleCategory
        fields = ('id', 'name')

class VehicleImageSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = VehicleImage
        fields = ('id', 'image', 'image_url', 'is_primary', 'uploaded_at')
        read_only_fields = ('id', 'uploaded_at', 'image_url')

    def get_image_url(self, obj):
        request = self.context.get('request')
        if obj.image and request:
            return request.build_absolute_uri(obj.image.url)
        elif obj.image:
            return obj.image.url
        return None


class VehicleDocumentSerializer(serializers.ModelSerializer):
    document_url = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = VehicleDocument
        fields = ('id', 'document_type', 'document_file', 'document_url', 'extracted_data', 
                  'extraction_confidence', 'uploaded_at', 'extraction_completed_at')
        read_only_fields = ('id', 'uploaded_at', 'extraction_completed_at', 'extracted_data', 
                           'extraction_confidence', 'document_url')

    def get_document_url(self, obj):
        request = self.context.get('request')
        if obj.document_file and request:
            return request.build_absolute_uri(obj.document_file.url)
        elif obj.document_file:
            return obj.document_file.url
        return None

class VehicleVerificationResultSerializer(serializers.ModelSerializer):
    """Serializer for detailed verification results"""
    
    class Meta:
        model = VehicleVerificationResult
        fields = [
            'id', 'vehicle', 'ai_detected_brand', 'ai_detected_model', 
            'ai_detected_vehicle_type', 'ai_detected_fuel_type', 'ai_detected_year',
            'ai_detected_plate_number', 'document_fuel_type', 'document_vehicle_class',
            'document_model_year', 'document_manufacturer', 'document_plate_number',
            'document_match_score', 'brand_match_score', 'model_match_score', 
            'vehicle_type_match_score', 'fuel_type_match_score', 'plate_number_match_score',
            'image_quality_score', 'overall_confidence_score',
            'is_vehicle_image', 'images_analyzed_count', 'ai_suggestions', 
            'discrepancies', 'verification_passed', 'requires_manual_review',
            'error_message', 'created_at'
        ]
        read_only_fields = fields


class VehicleSerializer(serializers.ModelSerializer):
    posted_by = serializers.ReadOnlyField(source='posted_by.id')
    images = VehicleImageSerializer(many=True, read_only=True)
    documents = VehicleDocumentSerializer(many=True, read_only=True)
    category = serializers.PrimaryKeyRelatedField(queryset=VehicleCategory.objects.all(), required=False, allow_null=True)
    primary_image = serializers.SerializerMethodField(read_only=True)
    
    # Verification fields
    verification_status = serializers.CharField(read_only=True)
    is_verified = serializers.BooleanField(read_only=True)
    verification_score = serializers.FloatField(read_only=True)
    latest_verification = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Vehicle
        fields = [
            'id', 'posted_by', 'category', 'manufacturer', 'model', 'city', 'plate_number',
            'year', 'vehicle_type', 'engine_capacity', 'transmission', 'fuel_type',
            'mileage', 'price', 'description', 'images', 'documents', 'primary_image', 
            'verification_status', 'is_verified', 'verification_score', 'latest_verification',
            'created_at', 'updated_at'
        ]
        read_only_fields = (
            'id', 'posted_by', 'created_at', 'updated_at', 'images', 'documents', 'primary_image',
            'verification_status', 'is_verified', 'verification_score', 'latest_verification'
        )

    def get_primary_image(self, obj):
        primary_img = obj.images.filter(is_primary=True).first()
        if not primary_img:
            primary_img = obj.images.first()
        
        if primary_img:
            serializer = VehicleImageSerializer(primary_img, context=self.context)
            return serializer.data
        return None
    
    def get_latest_verification(self, obj):
        """Get the latest verification result summary"""
        latest = obj.verification_results.first()
        if latest:
            return {
                'id': latest.id,
                'overall_confidence_score': latest.overall_confidence_score,
                'verification_passed': latest.verification_passed,
                'requires_manual_review': latest.requires_manual_review,
                'created_at': latest.created_at
            }
        return None
