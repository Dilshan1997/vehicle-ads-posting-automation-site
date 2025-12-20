# ads_post/document_extraction_service.py
"""
AI-Powered Document Extraction Service
Uses OpenAI Vision API to extract vehicle details from emission test certificates or ownership books
"""
import os
import base64
import json
import logging
from typing import Dict, Optional
from datetime import datetime
from django.conf import settings
from openai import OpenAI
from .models import VehicleDocument

logger = logging.getLogger(__name__)


class DocumentExtractionService:
    """
    Service class to extract vehicle information from documents using OpenAI Vision API
    """
    
    def __init__(self):
        """Initialize OpenAI client with API key from environment"""
        self.api_key = getattr(settings, 'OPENAI_API_KEY', None)
        self.model = getattr(settings, 'OPENAI_MODEL', 'gpt-4o')  # Default to gpt-4o with vision
        
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not found in settings")
        
        self.client = OpenAI(api_key=self.api_key)
    
    def encode_image_to_base64(self, file_path: str) -> str:
        """Encode image file to base64 string"""
        try:
            with open(file_path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode('utf-8')
        except Exception as e:
            logger.error(f"Error encoding document {file_path}: {str(e)}")
            raise
    
    def build_extraction_prompt(self, document_type: str) -> str:
        """
        Build detailed prompt for OpenAI to extract vehicle information from document
        Focuses only on essential fields needed for validation
        """
        if document_type == 'emission_test':
            prompt = """You are an expert document analyzer specializing in vehicle emission test certificates and vehicle registration documents. Extract ONLY the essential vehicle identification fields from this document.

**CRITICAL INSTRUCTIONS:**
- IGNORE all other fields like Certificate No, Date of Issue, Valid Till, Test Type, Overall Result, Test Details, Center, Test Fee, Machine ID, Inspector, Emission Test Parameters, Authorization, Revenue License No, Signatures, etc.
- DO NOT extract plate number from images - only extract it from text fields (Registration No field)
- Focus ONLY on the "Vehicle Details" section of the emission test certificate
- NOTE: For electric vehicles, if this is a registration document instead of an emission test certificate, still extract the vehicle details from the appropriate section

**REQUIRED FIELDS TO EXTRACT (from Vehicle Details section only):**
1. **Vehicle Class** - Look for "Vehicle Class" field (e.g., Car, SUV, Van, Motorcycle, etc.)
2. **Engine No** - Look for "Engine No" or "Engine Number" field
3. **Chassis No** - Look for "Chassis No" or "Chassis Number" field
4. **Fuel Type** - Look for "Fuel Type" field (Petrol, Diesel, Electric, Hybrid, etc.)
5. **Make** - Look for "Make" field (Manufacturer/Brand name like Toyota, Honda, etc.)
6. **Model** - Look for "Model" field (Vehicle model name)
7. **Year of Manufacture** - Look for "Year of Manufacture" field

**IMPORTANT NOTES:**
- Extract ONLY text values from the specified fields
- If a field is not visible, unclear, or handwritten and illegible, set it to null
- Do NOT confuse Certificate No with Registration No - only extract Registration No if it's clearly labeled as such
- Do NOT extract plate numbers from images/photos in the document
- Extract exact values as they appear in the document (preserve original formatting)
- If you see "Registration No" in the Vehicle Details section, extract it as plate_number

**Response Format (JSON):**
{
    "vehicle_class": "extracted vehicle class from Vehicle Details section or null",
    "engine_no": "extracted engine number from Vehicle Details section or null",
    "chassis_no": "extracted chassis number from Vehicle Details section or null",
    "fuel_type": "extracted fuel type from Vehicle Details section or null",
    "manufacturer": "extracted make/manufacturer from Vehicle Details section or null",
    "model": "extracted model from Vehicle Details section or null",
    "model_year": "extracted year of manufacture from Vehicle Details section or null",
    "plate_number": "extracted registration number from Vehicle Details section (text only, not from images) or null",
    "extraction_confidence": 0-100,
    "document_quality": "good/fair/poor",
    "notes": "any relevant notes about the extraction, especially if fields were unclear or missing"
}

Provide ONLY valid JSON response, no additional text."""
        
        else:  # ownership_book (kept for backward compatibility, but not used in frontend)
            prompt = """You are an expert document analyzer specializing in vehicle ownership/registration books (CR forms). Extract ONLY the essential vehicle identification fields from this document.

**CRITICAL INSTRUCTIONS:**
- IGNORE all other fields like CR No, Application Form details, Applicant Details, Declarations, Official Use Only sections, Signatures, Stamps, etc.
- Focus ONLY on the "Section 2: Subject / Vehicle / Item Details" section
- DO NOT extract plate number from images - only extract it from text fields

**REQUIRED FIELDS TO EXTRACT (from Section 2: Subject / Vehicle / Item Details only):**
1. **Vehicle Class** - Look for "Type / Category" field (e.g., Car, SUV, Van, Motorcycle, etc.)
2. **Engine No** - Look for "Engine No" or "Engine Number" field
3. **Chassis No** - Look for "Chassis No" or "Chassis Number" field
4. **Fuel Type** - May be in Type/Category or inferred from vehicle details (Petrol, Diesel, Electric, Hybrid, etc.)
5. **Make** - Look for "Make / Model" field - extract the Make/Manufacturer part (e.g., Toyota, Honda, etc.)
6. **Model** - Look for "Make / Model" field - extract the Model part
7. **Year of Manufacture** - Look for "Year of Manufacture" field
8. **Registration No** - Look for "Registration No" field (text only, not from images)

**IMPORTANT NOTES:**
- Extract ONLY from Section 2: Subject / Vehicle / Item Details
- If a field is not visible, unclear, or handwritten and illegible, set it to null
- Do NOT confuse CR No with Registration No - only extract Registration No from Section 2
- Do NOT extract plate numbers from images/photos in the document
- For "Make / Model" field, try to separate Make (manufacturer) and Model (vehicle model)
- Extract exact values as they appear in the document (preserve original formatting)

**Response Format (JSON):**
{
    "vehicle_class": "extracted type/category from Section 2 or null",
    "engine_no": "extracted engine number from Section 2 or null",
    "chassis_no": "extracted chassis number from Section 2 or null",
    "fuel_type": "extracted or inferred fuel type or null",
    "manufacturer": "extracted make/manufacturer from Section 2 or null",
    "model": "extracted model from Section 2 or null",
    "model_year": "extracted year of manufacture from Section 2 or null",
    "plate_number": "extracted registration number from Section 2 (text only, not from images) or null",
    "extraction_confidence": 0-100,
    "document_quality": "good/fair/poor",
    "notes": "any relevant notes about the extraction, especially if fields were unclear or missing"
}

Provide ONLY valid JSON response, no additional text."""
        
        return prompt
    
    def extract_from_document(self, document: VehicleDocument) -> Dict:
        """
        Extract vehicle information from a document using OpenAI Vision API
        
        Returns:
            Dict: {
                'success': bool,
                'data': extracted_data_dict or None,
                'error': error_message or None
            }
        """
        try:
            # Get the document file path
            document_path = document.document_file.path
            
            # Encode document to base64
            base64_image = self.encode_image_to_base64(document_path)
            image_data_url = f"data:image/jpeg;base64,{base64_image}"
            
            # Build extraction prompt
            prompt = self.build_extraction_prompt(document.document_type)
            
            # Prepare content for OpenAI API
            content = [
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": image_data_url,
                        "detail": "high"  # High detail for better text recognition
                    }
                }
            ]
            
            # Call OpenAI Vision API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": content
                    }
                ],
                max_tokens=2000,
                temperature=0.1,  # Very low temperature for accurate extraction
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
            
            # Update document with extracted data
            document.extracted_data = parsed_response
            document.extraction_confidence = parsed_response.get('extraction_confidence')
            document.extraction_completed_at = datetime.now()
            document.save()
            
            logger.info(f"Successfully extracted data from document {document.id}")
            
            return {
                'success': True,
                'data': parsed_response,
                'raw_response': ai_response
            }
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error for document {document.id}: {str(e)}\nResponse: {ai_response}")
            return {
                'success': False,
                'error': f"Failed to parse AI response: {str(e)}",
                'raw_response': ai_response if 'ai_response' in locals() else None
            }
        except Exception as e:
            logger.error(f"Document extraction error for document {document.id}: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'raw_response': None
            }
    
    def validate_against_form_data(self, extracted_data: Dict, form_data: Dict) -> Dict:
        """
        Compare extracted document data with form data and calculate validation scores
        
        Args:
            extracted_data: Data extracted from document (should have: vehicle_class, engine_no, chassis_no, fuel_type, manufacturer, model, model_year, plate_number)
            form_data: Data from the vehicle form (manufacturer, model, fuel_type, vehicle_type, plate_number, year, etc.)
        
        Returns:
            Dict with validation scores and match information
        """
        scores = {}
        matches = {}
        discrepancies = []
        
        # Normalize strings for comparison
        def normalize(s):
            if s is None:
                return None
            return str(s).strip().lower().replace('-', '').replace('_', '').replace(' ', '')
        
        # Compare fuel type
        doc_fuel = normalize(extracted_data.get('fuel_type'))
        form_fuel = normalize(form_data.get('fuel_type'))
        if doc_fuel and form_fuel:
            if doc_fuel == form_fuel:
                scores['fuel_type'] = 100
                matches['fuel_type'] = True
            else:
                # Partial match (e.g., "petrol" vs "gasoline")
                if doc_fuel in form_fuel or form_fuel in doc_fuel:
                    scores['fuel_type'] = 70
                    matches['fuel_type'] = 'partial'
                else:
                    scores['fuel_type'] = 0
                    matches['fuel_type'] = False
                    discrepancies.append(f"Fuel type mismatch: Form says '{form_data.get('fuel_type')}' but document shows '{extracted_data.get('fuel_type')}'")
        elif doc_fuel or form_fuel:
            scores['fuel_type'] = 50  # One is missing
            matches['fuel_type'] = 'incomplete'
        else:
            scores['fuel_type'] = None
            matches['fuel_type'] = None
        
        # Compare manufacturer
        doc_manufacturer = normalize(extracted_data.get('manufacturer'))
        form_manufacturer = normalize(form_data.get('manufacturer'))
        if doc_manufacturer and form_manufacturer:
            if doc_manufacturer == form_manufacturer:
                scores['manufacturer'] = 100
                matches['manufacturer'] = True
            elif doc_manufacturer in form_manufacturer or form_manufacturer in doc_manufacturer:
                scores['manufacturer'] = 80
                matches['manufacturer'] = 'partial'
            else:
                scores['manufacturer'] = 0
                matches['manufacturer'] = False
                discrepancies.append(f"Manufacturer mismatch: Form says '{form_data.get('manufacturer')}' but document shows '{extracted_data.get('manufacturer')}'")
        elif doc_manufacturer or form_manufacturer:
            scores['manufacturer'] = 50
            matches['manufacturer'] = 'incomplete'
        else:
            scores['manufacturer'] = None
            matches['manufacturer'] = None
        
        # Compare model
        doc_model = normalize(extracted_data.get('model'))
        form_model = normalize(form_data.get('model'))
        if doc_model and form_model:
            if doc_model == form_model:
                scores['model'] = 100
                matches['model'] = True
            elif doc_model in form_model or form_model in doc_model:
                scores['model'] = 80
                matches['model'] = 'partial'
            else:
                scores['model'] = 0
                matches['model'] = False
                discrepancies.append(f"Model mismatch: Form says '{form_data.get('model')}' but document shows '{extracted_data.get('model')}'")
        elif doc_model or form_model:
            scores['model'] = 50
            matches['model'] = 'incomplete'
        else:
            scores['model'] = None
            matches['model'] = None
        
        # Compare vehicle class/type
        doc_class = normalize(extracted_data.get('vehicle_class'))
        form_type = normalize(form_data.get('vehicle_type'))
        if doc_class and form_type:
            if doc_class == form_type:
                scores['vehicle_type'] = 100
                matches['vehicle_type'] = True
            elif doc_class in form_type or form_type in doc_class:
                scores['vehicle_type'] = 80
                matches['vehicle_type'] = 'partial'
            else:
                scores['vehicle_type'] = 0
                matches['vehicle_type'] = False
                discrepancies.append(f"Vehicle type mismatch: Form says '{form_data.get('vehicle_type')}' but document shows '{extracted_data.get('vehicle_class')}'")
        elif doc_class or form_type:
            scores['vehicle_type'] = 50
            matches['vehicle_type'] = 'incomplete'
        else:
            scores['vehicle_type'] = None
            matches['vehicle_type'] = None
        
        # Compare plate number
        doc_plate = normalize(extracted_data.get('plate_number'))
        form_plate = normalize(form_data.get('plate_number'))
        if doc_plate and form_plate:
            if doc_plate == form_plate:
                scores['plate_number'] = 100
                matches['plate_number'] = True
            else:
                scores['plate_number'] = 0
                matches['plate_number'] = False
                discrepancies.append(f"Plate number mismatch: Form says '{form_data.get('plate_number')}' but document shows '{extracted_data.get('plate_number')}'")
        elif doc_plate or form_plate:
            scores['plate_number'] = 50
            matches['plate_number'] = 'incomplete'
        else:
            scores['plate_number'] = None
            matches['plate_number'] = None
        
        # Compare year
        doc_year = extracted_data.get('model_year')
        form_year = form_data.get('year')
        if doc_year and form_year:
            try:
                doc_year_int = int(str(doc_year).strip()[:4])  # Extract year from string if needed
                form_year_int = int(form_year)
                if doc_year_int == form_year_int:
                    scores['year'] = 100
                    matches['year'] = True
                elif abs(doc_year_int - form_year_int) <= 1:
                    scores['year'] = 90
                    matches['year'] = 'close'
                else:
                    scores['year'] = 0
                    matches['year'] = False
                    discrepancies.append(f"Year mismatch: Form says '{form_year}' but document shows '{doc_year}'")
            except (ValueError, TypeError):
                scores['year'] = 50
                matches['year'] = 'incomplete'
        elif doc_year or form_year:
            scores['year'] = 50
            matches['year'] = 'incomplete'
        else:
            scores['year'] = None
            matches['year'] = None
        
        # Calculate overall document match score (weighted average)
        valid_scores = {k: v for k, v in scores.items() if v is not None}
        if valid_scores:
            weights = {
                'fuel_type': 0.25,
                'manufacturer': 0.20,
                'model': 0.20,
                'vehicle_type': 0.15,
                'plate_number': 0.15,
                'year': 0.05
            }
            
            total_score = 0.0
            total_weight = 0.0
            for field, score in valid_scores.items():
                weight = weights.get(field, 0.1)
                total_score += score * weight
                total_weight += weight
            
            overall_score = total_score / total_weight if total_weight > 0 else 0.0
        else:
            overall_score = 0.0
        
        return {
            'scores': scores,
            'matches': matches,
            'discrepancies': discrepancies,
            'overall_score': round(overall_score, 2),
            'extracted_data': extracted_data
        }

