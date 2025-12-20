# ads_post/verification_service.py
"""
AI-Powered Vehicle Verification Service
Uses OpenAI Vision API to verify vehicle listings
"""
import os
import base64
import json
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from django.conf import settings
from django.core.files.base import ContentFile
from openai import OpenAI
from .models import Vehicle, VehicleVerificationResult, VehicleDocument
from .document_extraction_service import DocumentExtractionService

logger = logging.getLogger(__name__)


class VehicleVerificationService:
    """
    Service class to handle AI-powered vehicle verification
    """
    
    def __init__(self):
        """Initialize OpenAI client with API key from environment"""
        self.api_key = getattr(settings, 'OPENAI_API_KEY', None)
        self.model = getattr(settings, 'OPENAI_MODEL', 'gpt-4o')  # Default to gpt-4o with vision
        
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not found in settings")
        
        self.client = OpenAI(api_key=self.api_key)
        
        # Verification thresholds
        self.PASS_THRESHOLD = 70.0  # Overall score threshold for passing
        self.MANUAL_REVIEW_THRESHOLD = 50.0  # Below this, requires manual review
        self.MAX_IMAGES_TO_ANALYZE = 5  # Limit images to reduce API costs
    
    def encode_image_to_base64(self, image_path: str) -> str:
        """Encode image file to base64 string"""
        try:
            with open(image_path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode('utf-8')
        except Exception as e:
            logger.error(f"Error encoding image {image_path}: {str(e)}")
            raise
    
    def prepare_image_urls(self, vehicle: Vehicle) -> List[str]:
        """
        Prepare image URLs for OpenAI API
        Returns list of base64 encoded images
        """
        images = vehicle.images.all()[:self.MAX_IMAGES_TO_ANALYZE]
        image_data = []
        
        for img in images:
            try:
                # Get the full path of the image
                image_path = img.image.path
                base64_image = self.encode_image_to_base64(image_path)
                image_data.append(f"data:image/jpeg;base64,{base64_image}")
            except Exception as e:
                logger.warning(f"Could not process image {img.id}: {str(e)}")
                continue
        
        return image_data
    
    def build_verification_prompt(self, vehicle: Vehicle) -> str:
        """
        Build detailed prompt for OpenAI to verify vehicle
        """
        prompt = f"""You are an expert vehicle inspector. Analyze the provided vehicle images and verify the listing details.

**User-Provided Vehicle Information:**
- Manufacturer/Brand: {vehicle.manufacturer}
- Model: {vehicle.model}
- Vehicle Type: {vehicle.vehicle_type or 'Not specified'}
- Fuel Type: {vehicle.fuel_type or 'Not specified'}
- Year: {vehicle.year or 'Not specified'}
- Transmission: {vehicle.transmission or 'Not specified'}
- Plate Number: {vehicle.plate_number or 'Not specified'}

**Your Task:**
1. Verify if the images show an actual vehicle (not random objects, memes, or inappropriate content)
2. Identify the vehicle's brand, model, type (car/van/suv/truck/motorcycle/etc), and likely fuel type (petrol/diesel/electric/hybrid)
3. **IMPORTANT: Carefully detect and read the license plate number from the images. Look for any visible license plates in the images.**
4. Compare your findings with the user-provided information, especially the plate number
5. Rate the match accuracy for each field (0-100 score), including plate number match
6. Assess image quality (clear, well-lit, multiple angles)
7. Identify any discrepancies or concerns, especially if the detected plate number doesn't match the provided one

**Response Format (JSON):**
{{
    "is_vehicle_image": true/false,
    "detected_information": {{
        "brand": "detected brand name",
        "model": "detected model name or closest match",
        "vehicle_type": "car/van/suv/motorcycle/truck/etc",
        "fuel_type": "petrol/diesel/electric/hybrid/unknown",
        "year_range": "approximate year or range",
        "plate_number": "detected license plate number from images (if visible, otherwise null)"
    }},
    "match_scores": {{
        "brand_match": 0-100,
        "model_match": 0-100,
        "vehicle_type_match": 0-100,
        "fuel_type_match": 0-100,
        "plate_number_match": 0-100 (100 if exact match, 0 if no match, null if plate not visible in images),
        "overall_confidence": 0-100
    }},
    "image_quality": {{
        "score": 0-100,
        "clear_images": true/false,
        "multiple_angles": true/false,
        "well_lit": true/false
    }},
    "verification_passed": true/false,
    "discrepancies": ["list any discrepancies found"],
    "suggestions": "Suggestions to improve the listing or resolve discrepancies",
    "requires_manual_review": true/false,
    "confidence_level": "high/medium/low"
}}

Provide ONLY valid JSON response, no additional text."""
        
        return prompt
    
    def call_openai_vision_api(self, prompt: str, image_urls: List[str]) -> Dict:
        """
        Make API call to OpenAI Vision API
        """
        try:
            # Prepare messages with images
            content = [{"type": "text", "text": prompt}]
            
            # Add images to content
            for image_url in image_urls:
                content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": image_url,
                        "detail": "high"  # High detail for better analysis
                    }
                })
            
            # Make API call
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": content
                    }
                ],
                max_tokens=1500,
                temperature=0.2,  # Lower temperature for more consistent results
            )
            
            # Extract response
            ai_response = response.choices[0].message.content
            
            # Parse JSON response
            # Sometimes OpenAI wraps JSON in markdown code blocks
            if "```json" in ai_response:
                ai_response = ai_response.split("```json")[1].split("```")[0].strip()
            elif "```" in ai_response:
                ai_response = ai_response.split("```")[1].split("```")[0].strip()
            
            parsed_response = json.loads(ai_response)
            
            return {
                'success': True,
                'data': parsed_response,
                'raw_response': ai_response
            }
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {str(e)}\nResponse: {ai_response}")
            return {
                'success': False,
                'error': f"Failed to parse AI response: {str(e)}",
                'raw_response': ai_response if 'ai_response' in locals() else None
            }
        except Exception as e:
            logger.error(f"OpenAI API error: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'raw_response': None
            }
    
    def calculate_overall_score(self, match_scores: Dict) -> float:
        """
        Calculate weighted overall verification score
        Scores are already 0-100, so we calculate weighted average without multiplying by 100 again
        """
        # If plate number is provided and detected, include it in scoring
        has_plate_number = match_scores.get('plate_number_match') is not None
        
        if has_plate_number:
            weights = {
                'brand_match': 0.20,
                'model_match': 0.20,
                'vehicle_type_match': 0.15,
                'fuel_type_match': 0.10,
                'plate_number_match': 0.35,  # Higher weight for plate number match
            }
        else:
            weights = {
                'brand_match': 0.30,
                'model_match': 0.30,
                'vehicle_type_match': 0.25,
                'fuel_type_match': 0.15,
            }
        
        total_score = 0.0
        total_weight = 0.0
        for field, weight in weights.items():
            score = match_scores.get(field)
            if score is not None:
                # Score is already 0-100, multiply by weight
                total_score += score * weight
                total_weight += weight
        
        # Calculate weighted average (scores are already 0-100, so result is 0-100)
        # No need to multiply by 100 again
        if total_weight > 0:
            weighted_average = total_score / total_weight
            logger.debug(f"Score calculation: total_score={total_score}, total_weight={total_weight}, result={weighted_average}")
            return round(weighted_average, 2)
        return 0.0
    
    def save_verification_result(
        self, 
        vehicle: Vehicle, 
        ai_response: Dict, 
        raw_response: str,
        images_count: int,
        document_validation: Optional[Dict] = None
    ) -> VehicleVerificationResult:
        """
        Save verification results to database
        """
        detected_info = ai_response.get('detected_information', {})
        match_scores = ai_response.get('match_scores', {})
        image_quality = ai_response.get('image_quality', {})
        
        # Check plate number match - if plate number doesn't match, require manual review
        plate_number_match = match_scores.get('plate_number_match')
        detected_plate = detected_info.get('plate_number')
        requires_manual_review_plate = False
        
        # If plate number was provided but doesn't match detected one, flag for review
        if vehicle.plate_number and detected_plate:
            if plate_number_match is not None and plate_number_match < 100:
                requires_manual_review_plate = True
                if 'discrepancies' not in ai_response:
                    ai_response['discrepancies'] = []
                ai_response['discrepancies'].append(
                    f"Plate number mismatch: Provided '{vehicle.plate_number}' but detected '{detected_plate}'"
                )
        
        # Calculate overall score
        overall_score = self.calculate_overall_score(match_scores)
        
        # Determine if verification passed
        verification_passed = ai_response.get('verification_passed', False)
        is_vehicle_image = ai_response.get('is_vehicle_image', False)
        ai_requires_review = ai_response.get('requires_manual_review', False)
        requires_manual_review = ai_requires_review or requires_manual_review_plate
        
        # Determine manual review status based on conditions
        if not is_vehicle_image:
            # Not a vehicle image - it's a failure, not manual review
            requires_manual_review = False
        elif ai_requires_review or requires_manual_review_plate:
            # AI explicitly requires manual review (e.g., plate mismatch) - keep it
            requires_manual_review = True
        elif overall_score >= self.MANUAL_REVIEW_THRESHOLD and overall_score < self.PASS_THRESHOLD:
            # Score between 50-70: requires manual review
            requires_manual_review = True
        else:
            # Score < 50 or other failure conditions: it's a failure, not manual review
            requires_manual_review = False
        
        # Handle document validation data if provided
        document_fuel_type = None
        document_vehicle_class = None
        document_model_year = None
        document_manufacturer = None
        document_plate_number = None
        document_match_score = None
        
        if document_validation:
            extracted_data = document_validation.get('extracted_data', {})
            document_fuel_type = extracted_data.get('fuel_type')
            document_vehicle_class = extracted_data.get('vehicle_class')
            document_model_year = extracted_data.get('model_year')
            document_manufacturer = extracted_data.get('manufacturer')
            document_plate_number = extracted_data.get('plate_number')
            document_match_score = document_validation.get('overall_score')
            
            # Add document discrepancies to main discrepancies list
            doc_discrepancies = document_validation.get('discrepancies', [])
            if doc_discrepancies:
                if 'discrepancies' not in ai_response:
                    ai_response['discrepancies'] = []
                ai_response['discrepancies'].extend(doc_discrepancies)
            
            # Adjust overall score based on document match
            # If document match is low, reduce overall confidence
            if document_match_score and document_match_score < 70:
                overall_score = min(overall_score, document_match_score * 0.9)  # Penalize for document mismatch
                requires_manual_review = True
        
        # Create verification result
        verification_result = VehicleVerificationResult.objects.create(
            vehicle=vehicle,
            # AI detected information
            ai_detected_brand=detected_info.get('brand'),
            ai_detected_model=detected_info.get('model'),
            ai_detected_vehicle_type=detected_info.get('vehicle_type'),
            ai_detected_fuel_type=detected_info.get('fuel_type'),
            ai_detected_year=detected_info.get('year_range'),
            ai_detected_plate_number=detected_plate,
            # Document-based information
            document_fuel_type=document_fuel_type,
            document_vehicle_class=document_vehicle_class,
            document_model_year=document_model_year,
            document_manufacturer=document_manufacturer,
            document_plate_number=document_plate_number,
            document_match_score=document_match_score,
            # Match scores
            brand_match_score=match_scores.get('brand_match'),
            model_match_score=match_scores.get('model_match'),
            vehicle_type_match_score=match_scores.get('vehicle_type_match'),
            fuel_type_match_score=match_scores.get('fuel_type_match'),
            plate_number_match_score=plate_number_match,
            image_quality_score=image_quality.get('score'),
            overall_confidence_score=overall_score,
            # Image validation
            is_vehicle_image=ai_response.get('is_vehicle_image', False),
            images_analyzed_count=images_count,
            # Metadata
            ai_raw_response=raw_response,
            ai_suggestions=ai_response.get('suggestions'),
            discrepancies=ai_response.get('discrepancies', []),
            # Status
            verification_passed=verification_passed and overall_score >= self.PASS_THRESHOLD,
            requires_manual_review=requires_manual_review,
        )
        
        # Update vehicle verification status based on score and conditions
        # Priority: 1) Not a vehicle image = failed, 2) Score >= 70 = verified, 3) Score 50-70 or explicit review = manual_review, 4) Score < 50 = failed
        
        if not is_vehicle_image:
            # Not a vehicle image - actual failure (highest priority)
            vehicle.verification_status = 'failed'
            vehicle.is_verified = False
            logger.info(f"Vehicle {vehicle.id}: Not a vehicle image - setting status to 'failed'")
        elif overall_score >= self.PASS_THRESHOLD:
            # Score >= 70: verified (rely on score, not just AI's verification_passed flag)
            vehicle.verification_status = 'verified'
            vehicle.is_verified = True
            logger.info(f"Vehicle {vehicle.id}: Score {overall_score} >= {self.PASS_THRESHOLD} - setting status to 'verified'")
        elif overall_score < self.MANUAL_REVIEW_THRESHOLD:
            # Score < 50: actual failure (regardless of other flags)
            vehicle.verification_status = 'failed'
            vehicle.is_verified = False
            logger.info(f"Vehicle {vehicle.id}: Score {overall_score} < {self.MANUAL_REVIEW_THRESHOLD} - setting status to 'failed'")
        elif overall_score >= self.MANUAL_REVIEW_THRESHOLD and overall_score < self.PASS_THRESHOLD:
            # Score between 50-70: requires manual review
            vehicle.verification_status = 'manual_review'
            vehicle.is_verified = False
            logger.info(f"Vehicle {vehicle.id}: Score {overall_score} between {self.MANUAL_REVIEW_THRESHOLD}-{self.PASS_THRESHOLD} - setting status to 'manual_review'")
        elif requires_manual_review:
            # Explicitly requires manual review (plate mismatch or AI flag) - but only if score >= 50
            # If score < 50, it should already be 'failed' from above condition
            if overall_score >= self.MANUAL_REVIEW_THRESHOLD:
                vehicle.verification_status = 'manual_review'
                vehicle.is_verified = False
                logger.info(f"Vehicle {vehicle.id}: Requires manual review (score: {overall_score}) - setting status to 'manual_review'")
            else:
                # Score < 50 but has review flag - still mark as failed
                vehicle.verification_status = 'failed'
                vehicle.is_verified = False
                logger.info(f"Vehicle {vehicle.id}: Score {overall_score} < {self.MANUAL_REVIEW_THRESHOLD} with review flag - setting status to 'failed'")
        else:
            # Fallback: any other case should be failed
            vehicle.verification_status = 'failed'
            vehicle.is_verified = False
            logger.warning(f"Vehicle {vehicle.id}: Unexpected condition - score: {overall_score}, is_vehicle: {is_vehicle_image}, requires_review: {requires_manual_review} - setting status to 'failed'")
        
        vehicle.verification_score = overall_score
        vehicle.verification_attempts += 1
        vehicle.last_verification_at = datetime.now()
        vehicle.save()
        
        # Refresh from database to ensure we have the latest status
        vehicle.refresh_from_db()
        logger.info(f"Vehicle {vehicle.id}: Final verification_status = '{vehicle.verification_status}', score = {overall_score}")
        
        return verification_result
    
    def verify_vehicle(self, vehicle_id: int) -> Tuple[bool, Dict]:
        """
        Main method to verify a vehicle listing
        
        Returns:
            Tuple[bool, Dict]: (success, result_data)
        """
        try:
            # Get vehicle
            vehicle = Vehicle.objects.get(id=vehicle_id)
            
            # Check if vehicle has images
            if not vehicle.images.exists():
                return False, {
                    'error': 'No images found for verification',
                    'status': 'failed'
                }
            
            # Update status to in_progress
            vehicle.verification_status = 'in_progress'
            vehicle.save()
            
            # Prepare images
            image_urls = self.prepare_image_urls(vehicle)
            
            if not image_urls:
                vehicle.verification_status = 'failed'
                vehicle.save()
                return False, {
                    'error': 'Could not process vehicle images',
                    'status': 'failed'
                }
            
            # Build prompt
            prompt = self.build_verification_prompt(vehicle)
            
            # Call OpenAI API
            api_response = self.call_openai_vision_api(prompt, image_urls)
            
            if not api_response['success']:
                vehicle.verification_status = 'failed'
                vehicle.save()
                
                # Save error result
                VehicleVerificationResult.objects.create(
                    vehicle=vehicle,
                    error_message=api_response['error'],
                    verification_passed=False,
                    requires_manual_review=False,
                    images_analyzed_count=len(image_urls)
                )
                
                return False, {
                    'error': api_response['error'],
                    'status': 'failed'
                }
            
            # Process document if available
            document_validation = None
            document = vehicle.documents.first()  # Get the first document (should be only one)
            
            if document:
                # Extract data from document if not already extracted
                if not document.extracted_data:
                    extraction_service = DocumentExtractionService()
                    extraction_result = extraction_service.extract_from_document(document)
                    
                    if extraction_result['success']:
                        document.refresh_from_db()  # Refresh to get updated extracted_data
                
                # Validate document data against form data
                if document.extracted_data:
                    extraction_service = DocumentExtractionService()
                    form_data = {
                        'manufacturer': vehicle.manufacturer,
                        'model': vehicle.model,
                        'fuel_type': vehicle.fuel_type,
                        'vehicle_type': vehicle.vehicle_type,
                        'plate_number': vehicle.plate_number,
                        'year': vehicle.year
                    }
                    document_validation = extraction_service.validate_against_form_data(
                        document.extracted_data,
                        form_data
                    )
            
            # Save verification result
            verification_result = self.save_verification_result(
                vehicle=vehicle,
                ai_response=api_response['data'],
                raw_response=api_response['raw_response'],
                images_count=len(image_urls),
                document_validation=document_validation
            )
            
            return True, {
                'status': vehicle.verification_status,
                'verification_result': verification_result,
                'message': 'Verification completed successfully'
            }
            
        except Vehicle.DoesNotExist:
            return False, {
                'error': 'Vehicle not found',
                'status': 'failed'
            }
        except Exception as e:
            logger.error(f"Verification error for vehicle {vehicle_id}: {str(e)}")
            return False, {
                'error': str(e),
                'status': 'failed'
            }
    
    def get_verification_status(self, vehicle_id: int) -> Dict:
        """
        Get current verification status and latest results
        """
        try:
            vehicle = Vehicle.objects.get(id=vehicle_id)
            latest_result = vehicle.verification_results.first()
            
            data = {
                'vehicle_id': vehicle.id,
                'verification_status': vehicle.verification_status,
                'is_verified': vehicle.is_verified,
                'verification_score': vehicle.verification_score,
                'attempts': vehicle.verification_attempts,
                'last_verification': vehicle.last_verification_at,
            }
            
            if latest_result:
                data['latest_result'] = {
                    'id': latest_result.id,
                    'detected_brand': latest_result.ai_detected_brand,
                    'detected_model': latest_result.ai_detected_model,
                    'detected_type': latest_result.ai_detected_vehicle_type,
                    'detected_fuel_type': latest_result.ai_detected_fuel_type,
                    'confidence_score': latest_result.overall_confidence_score,
                    'passed': latest_result.verification_passed,
                    'requires_manual_review': latest_result.requires_manual_review,
                    'discrepancies': latest_result.discrepancies,
                    'suggestions': latest_result.ai_suggestions,
                    'created_at': latest_result.created_at,
                }
            
            return {'success': True, 'data': data}
            
        except Vehicle.DoesNotExist:
            return {'success': False, 'error': 'Vehicle not found'}
        except Exception as e:
            logger.error(f"Error getting verification status: {str(e)}")
            return {'success': False, 'error': str(e)}

