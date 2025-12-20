from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Case, When, IntegerField
from .models import VehicleCategory, Vehicle, VehicleImage, VehicleDocument, VehicleVerificationResult

class VehicleImageInline(admin.TabularInline):
    model = VehicleImage
    extra = 1
    readonly_fields = ('image_preview',)
    
    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="100" height="100" style="object-fit: cover;" />', obj.image.url)
        return "No image"
    image_preview.short_description = 'Preview'


class VehicleDocumentInline(admin.TabularInline):
    model = VehicleDocument
    extra = 0
    readonly_fields = ('document_preview', 'extracted_data', 'extraction_confidence', 'extraction_completed_at')
    can_delete = False
    
    def document_preview(self, obj):
        if obj.document_file:
            if obj.document_file.name.lower().endswith('.pdf'):
                return format_html(
                    '<a href="{}" target="_blank">📄 View PDF</a>',
                    obj.document_file.url
                )
            else:
                return format_html(
                    '<img src="{}" width="200" height="150" style="object-fit: contain;" />',
                    obj.document_file.url
                )
        return "No document"
    document_preview.short_description = 'Preview'


class VehicleVerificationResultInline(admin.TabularInline):
    model = VehicleVerificationResult
    extra = 0
    readonly_fields = (
        'ai_detected_brand', 'ai_detected_model', 'ai_detected_vehicle_type',
        'overall_confidence_score', 'verification_passed', 'requires_manual_review',
        'created_at'
    )
    can_delete = False
    
    fields = (
        'ai_detected_brand', 'ai_detected_model', 'ai_detected_vehicle_type',
        'overall_confidence_score', 'verification_passed', 'requires_manual_review',
        'created_at'
    )


class ManualReviewFilter(admin.SimpleListFilter):
    """Custom filter to easily find vehicles requiring manual review"""
    title = 'Manual Review Status'
    parameter_name = 'manual_review'

    def lookups(self, request, model_admin):
        return (
            ('needs_review', 'Needs Manual Review'),
            ('reviewed', 'Already Reviewed'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'needs_review':
            return queryset.filter(verification_status='manual_review')
        elif self.value() == 'reviewed':
            return queryset.exclude(verification_status='manual_review')


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = (
        'manufacturer', 'model', 'year', 'posted_by', 'price',
        'verification_status_badge', 'verification_score_display',
        'created_at'
    )
    list_filter = (
        ManualReviewFilter,
        'verification_status', 'is_verified', 'vehicle_type',
        'transmission', 'fuel_type', 'year'
    )
    search_fields = ('manufacturer', 'model', 'city', 'posted_by__email')
    readonly_fields = (
        'verification_status', 'is_verified', 'verification_score',
        'verification_attempts', 'last_verification_at', 'created_at', 'updated_at'
    )
    inlines = [VehicleImageInline, VehicleDocumentInline, VehicleVerificationResultInline]
    ordering = ['-created_at']
    
    def get_queryset(self, request):
        """Prioritize manual review items in the list"""
        qs = super().get_queryset(request)
        # If no specific filter is applied, show manual review items first
        if not request.GET.get('verification_status') and not request.GET.get('manual_review'):
            qs = qs.annotate(
                priority=Case(
                    When(verification_status='manual_review', then=0),
                    default=1,
                    output_field=IntegerField()
                )
            ).order_by('priority', '-created_at')
        return qs
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('posted_by', 'category', 'manufacturer', 'model', 'city', 'plate_number')
        }),
        ('Vehicle Details', {
            'fields': ('year', 'vehicle_type', 'engine_capacity', 'transmission', 'fuel_type', 'mileage')
        }),
        ('Pricing', {
            'fields': ('price',)
        }),
        ('Verification Status', {
            'fields': (
                'verification_status', 'is_verified', 'verification_score',
                'verification_attempts', 'last_verification_at'
            ),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def verification_status_badge(self, obj):
        """Display verification status with colored badge"""
        colors = {
            'pending': '#ffc107',      # yellow
            'in_progress': '#17a2b8',  # blue
            'verified': '#28a745',     # green
            'failed': '#dc3545',       # red
            'manual_review': '#fd7e14' # orange
        }
        color = colors.get(obj.verification_status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-weight: bold;">{}</span>',
            color,
            obj.get_verification_status_display()
        )
    verification_status_badge.short_description = 'Verification Status'
    
    def verification_score_display(self, obj):
        """Display verification score with color coding"""
        if obj.verification_score is None:
            return format_html('<span style="color: #6c757d;">N/A</span>')
        
        score = obj.verification_score
        score_formatted = f'{score:.1f}%'
        
        if score >= 70:
            color = '#28a745'  # green
        elif score >= 50:
            color = '#ffc107'  # yellow
        else:
            color = '#dc3545'  # red
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            score_formatted
        )
    verification_score_display.short_description = 'Score'
    
    actions = [
        'trigger_verification', 
        'mark_as_verified', 
        'mark_for_manual_review',
        'approve_manual_review',
        'reject_manual_review'
    ]
    
    def trigger_verification(self, request, queryset):
        """Admin action to trigger verification for selected vehicles"""
        from .verification_service import VehicleVerificationService
        
        service = VehicleVerificationService()
        success_count = 0
        error_count = 0
        
        for vehicle in queryset:
            try:
                success, result = service.verify_vehicle(vehicle.id)
                if success:
                    success_count += 1
                else:
                    error_count += 1
            except Exception as e:
                error_count += 1
        
        self.message_user(
            request,
            f'Verification triggered: {success_count} successful, {error_count} failed'
        )
    trigger_verification.short_description = 'Trigger AI Verification for selected vehicles'
    
    def mark_as_verified(self, request, queryset):
        """Admin action to manually mark vehicles as verified"""
        updated = queryset.update(verification_status='verified', is_verified=True)
        self.message_user(request, f'{updated} vehicle(s) marked as verified')
    mark_as_verified.short_description = 'Mark selected as Verified'
    
    def mark_for_manual_review(self, request, queryset):
        """Admin action to mark vehicles for manual review"""
        updated = queryset.update(verification_status='manual_review', is_verified=False)
        self.message_user(request, f'{updated} vehicle(s) marked for manual review')
    mark_for_manual_review.short_description = 'Mark selected for Manual Review'
    
    def approve_manual_review(self, request, queryset):
        """Admin action to approve vehicles that were in manual review"""
        # Only approve vehicles that are in manual_review status
        manual_review_vehicles = queryset.filter(verification_status='manual_review')
        updated = manual_review_vehicles.update(verification_status='verified', is_verified=True)
        self.message_user(
            request, 
            f'{updated} vehicle(s) approved and marked as verified. '
            f'{queryset.count() - updated} vehicle(s) were not in manual review status.'
        )
    approve_manual_review.short_description = '✓ Approve Manual Review (Mark as Verified)'
    
    def reject_manual_review(self, request, queryset):
        """Admin action to reject vehicles that were in manual review"""
        # Only reject vehicles that are in manual_review status
        manual_review_vehicles = queryset.filter(verification_status='manual_review')
        updated = manual_review_vehicles.update(verification_status='failed', is_verified=False)
        self.message_user(
            request,
            f'{updated} vehicle(s) rejected and marked as failed. '
            f'{queryset.count() - updated} vehicle(s) were not in manual review status.'
        )
    reject_manual_review.short_description = '✗ Reject Manual Review (Mark as Failed)'


@admin.register(VehicleImage)
class VehicleImageAdmin(admin.ModelAdmin):
    list_display = ('vehicle', 'image_thumbnail', 'is_primary', 'uploaded_at')
    list_filter = ('is_primary', 'uploaded_at')
    search_fields = ('vehicle__manufacturer', 'vehicle__model')
    readonly_fields = ('image_preview', 'uploaded_at')
    
    def image_thumbnail(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" width="50" height="50" style="object-fit: cover; border-radius: 5px;" />',
                obj.image.url
            )
        return "No image"
    image_thumbnail.short_description = 'Thumbnail'
    
    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" width="300" style="max-width: 100%; height: auto;" />',
                obj.image.url
            )
        return "No image"
    image_preview.short_description = 'Preview'


@admin.register(VehicleVerificationResult)
class VehicleVerificationResultAdmin(admin.ModelAdmin):
    list_display = (
        'vehicle_link', 'verification_passed_badge', 'overall_confidence_score',
        'requires_manual_review_badge', 'is_vehicle_image', 'created_at'
    )
    list_filter = (
        'verification_passed', 'requires_manual_review',
        'is_vehicle_image', 'created_at'
    )
    search_fields = (
        'vehicle__manufacturer', 'vehicle__model',
        'ai_detected_brand', 'ai_detected_model'
    )
    readonly_fields = (
        'vehicle', 'ai_detected_brand', 'ai_detected_model',
        'ai_detected_vehicle_type', 'ai_detected_fuel_type', 'ai_detected_year',
        'ai_detected_plate_number', 'document_fuel_type', 'document_vehicle_class',
        'document_model_year', 'document_manufacturer', 'document_plate_number',
        'document_match_score', 'brand_match_score', 'model_match_score',
        'vehicle_type_match_score', 'fuel_type_match_score', 'plate_number_match_score',
        'image_quality_score', 'overall_confidence_score',
        'is_vehicle_image', 'images_analyzed_count', 'ai_raw_response',
        'ai_suggestions', 'discrepancies', 'verification_passed',
        'requires_manual_review', 'error_message', 'created_at'
    )
    
    fieldsets = (
        ('Vehicle Information', {
            'fields': ('vehicle',)
        }),
        ('AI Detected Information', {
            'fields': (
                'ai_detected_brand', 'ai_detected_model',
                'ai_detected_vehicle_type', 'ai_detected_fuel_type',
                'ai_detected_year', 'ai_detected_plate_number'
            )
        }),
        ('Document Extracted Information', {
            'fields': (
                'document_fuel_type', 'document_vehicle_class',
                'document_model_year', 'document_manufacturer',
                'document_plate_number', 'document_match_score'
            ),
            'classes': ('collapse',)
        }),
        ('Match Scores', {
            'fields': (
                'brand_match_score', 'model_match_score',
                'vehicle_type_match_score', 'fuel_type_match_score',
                'image_quality_score', 'overall_confidence_score'
            )
        }),
        ('Image Validation', {
            'fields': ('is_vehicle_image', 'images_analyzed_count')
        }),
        ('Verification Results', {
            'fields': (
                'verification_passed', 'requires_manual_review',
                'ai_suggestions', 'discrepancies'
            )
        }),
        ('Error Information', {
            'fields': ('error_message',),
            'classes': ('collapse',)
        }),
        ('Raw AI Response', {
            'fields': ('ai_raw_response',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at',)
        }),
    )
    
    def vehicle_link(self, obj):
        """Display link to vehicle in admin"""
        url = reverse('admin:ads_post_vehicle_change', args=[obj.vehicle.id])
        return format_html('<a href="{}">{}</a>', url, obj.vehicle)
    vehicle_link.short_description = 'Vehicle'
    
    def verification_passed_badge(self, obj):
        """Display verification passed status with badge"""
        if obj.verification_passed:
            return format_html(
                '<span style="background-color: #28a745; color: white; padding: 3px 10px; '
                'border-radius: 3px; font-weight: bold;">✓ Passed</span>'
            )
        return format_html(
            '<span style="background-color: #dc3545; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-weight: bold;">✗ Failed</span>'
        )
    verification_passed_badge.short_description = 'Status'
    
    def requires_manual_review_badge(self, obj):
        """Display manual review requirement with badge"""
        if obj.requires_manual_review:
            return format_html(
                '<span style="background-color: #fd7e14; color: white; padding: 3px 10px; '
                'border-radius: 3px; font-weight: bold;">⚠ Review Needed</span>'
            )
        return format_html('<span style="color: #6c757d;">—</span>')
    requires_manual_review_badge.short_description = 'Manual Review'
    
    def has_add_permission(self, request):
        """Disable manual creation of verification results"""
        return False


@admin.register(VehicleDocument)
class VehicleDocumentAdmin(admin.ModelAdmin):
    list_display = ('vehicle_link', 'document_type_display', 'extraction_confidence_display', 'uploaded_at')
    list_filter = ('document_type', 'extraction_completed_at', 'uploaded_at')
    search_fields = ('vehicle__manufacturer', 'vehicle__model')
    readonly_fields = ('document_preview', 'extracted_data', 'extraction_confidence', 'extraction_completed_at', 'uploaded_at')
    
    fieldsets = (
        ('Vehicle Information', {
            'fields': ('vehicle',)
        }),
        ('Document Information', {
            'fields': ('document_type', 'document_file', 'document_preview')
        }),
        ('Extracted Data', {
            'fields': ('extracted_data', 'extraction_confidence', 'extraction_completed_at'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('uploaded_at',),
            'classes': ('collapse',)
        }),
    )
    
    def vehicle_link(self, obj):
        """Display link to vehicle in admin"""
        url = reverse('admin:ads_post_vehicle_change', args=[obj.vehicle.id])
        return format_html('<a href="{}">{}</a>', url, obj.vehicle)
    vehicle_link.short_description = 'Vehicle'
    
    def document_type_display(self, obj):
        return obj.get_document_type_display()
    document_type_display.short_description = 'Document Type'
    
    def extraction_confidence_display(self, obj):
        """Display extraction confidence with color coding"""
        if obj.extraction_confidence is None:
            return format_html('<span style="color: #6c757d;">Not extracted</span>')
        
        score = obj.extraction_confidence
        score_formatted = f'{score:.1f}%'
        
        if score >= 80:
            color = '#28a745'  # green
        elif score >= 60:
            color = '#ffc107'  # yellow
        else:
            color = '#dc3545'  # red
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            score_formatted
        )
    extraction_confidence_display.short_description = 'Extraction Confidence'
    
    def document_preview(self, obj):
        if obj.document_file:
            if obj.document_file.name.lower().endswith('.pdf'):
                return format_html(
                    '<a href="{}" target="_blank" class="button">📄 View PDF Document</a>',
                    obj.document_file.url
                )
            else:
                return format_html(
                    '<img src="{}" width="400" style="max-width: 100%; height: auto; border: 1px solid #ddd;" />',
                    obj.document_file.url
                )
        return "No document"
    document_preview.short_description = 'Document Preview'


admin.site.register(VehicleCategory)
