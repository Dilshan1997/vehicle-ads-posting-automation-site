# Entity Relationship Diagram

This document contains the ER diagram for the Vehicle Ads Posting Automation Site backend database schema.

## ER Diagram (Mermaid)

```mermaid
erDiagram
    User ||--o{ Vehicle : "posts"
    VehicleCategory ||--o{ Vehicle : "categorizes"
    Vehicle ||--o{ VehicleImage : "has"
    Vehicle ||--o{ VehicleVerificationResult : "has"

    User {
        bigint id PK
        string email UK "unique"
        string name
        string phone_number
        url nic_image_link
        boolean is_verified
        string verification_token
        datetime token_expires_at
        string password
        string first_name
        string last_name
        boolean is_staff
        boolean is_active
        boolean is_superuser
        datetime date_joined
        datetime last_login
    }

    VehicleCategory {
        bigint id PK
        string name
    }

    Vehicle {
        bigint id PK
        bigint posted_by_id FK "references User"
        bigint category_id FK "references VehicleCategory, nullable"
        string manufacturer
        string model
        string city "nullable"
        string plate_number "nullable, unique, indexed"
        smallint year "nullable"
        string vehicle_type "nullable"
        string engine_capacity "nullable"
        string transmission "nullable"
        string fuel_type "nullable"
        string mileage "nullable"
        decimal price "nullable, max_digits=12, decimal_places=2"
        text description "nullable"
        string verification_status "choices: pending, in_progress, verified, failed, manual_review"
        boolean is_verified
        float verification_score "nullable, 0-100"
        int verification_attempts
        datetime last_verification_at "nullable"
        datetime created_at
        datetime updated_at
    }

    VehicleImage {
        bigint id PK
        bigint vehicle_id FK "references Vehicle"
        image image "upload_to='vehicles/'"
        boolean is_primary
        datetime uploaded_at
    }

    VehicleVerificationResult {
        bigint id PK
        bigint vehicle_id FK "references Vehicle"
        string ai_detected_brand "nullable"
        string ai_detected_model "nullable"
        string ai_detected_vehicle_type "nullable"
        string ai_detected_fuel_type "nullable"
        string ai_detected_year "nullable"
        string ai_detected_plate_number "nullable"
        float brand_match_score "nullable, 0-100"
        float model_match_score "nullable, 0-100"
        float vehicle_type_match_score "nullable, 0-100"
        float fuel_type_match_score "nullable, 0-100"
        float plate_number_match_score "nullable, 0-100"
        float image_quality_score "nullable"
        float overall_confidence_score "nullable"
        boolean is_vehicle_image
        int images_analyzed_count
        json ai_raw_response "nullable"
        text ai_suggestions "nullable"
        json discrepancies "nullable"
        boolean verification_passed
        boolean requires_manual_review
        text error_message "nullable"
        datetime created_at
    }
```

## Model Relationships

### User Model
- **Extends**: Django's `AbstractUser`
- **Relationships**:
  - One-to-Many with `Vehicle` (a user can post multiple vehicles)
- **Key Fields**:
  - `email`: Unique identifier (USERNAME_FIELD)
  - `is_verified`: Email verification status
  - `verification_token`: Token for email verification
  - `token_expires_at`: Token expiration time

### VehicleCategory Model
- **Relationships**:
  - One-to-Many with `Vehicle` (a category can have multiple vehicles)
- **Key Fields**:
  - `name`: Category name

### Vehicle Model
- **Relationships**:
  - Many-to-One with `User` (posted_by)
  - Many-to-One with `VehicleCategory` (category, nullable)
  - One-to-Many with `VehicleImage` (has multiple images)
  - One-to-Many with `VehicleVerificationResult` (has multiple verification results)
- **Key Fields**:
  - `plate_number`: Unique identifier for vehicles (indexed)
  - `verification_status`: Current verification state
  - `verification_score`: AI confidence score (0-100)
  - `is_verified`: Verification status flag

### VehicleImage Model
- **Relationships**:
  - Many-to-One with `Vehicle` (belongs to a vehicle)
- **Key Fields**:
  - `is_primary`: Flag for primary image
  - `image`: Image file stored in 'vehicles/' directory

### VehicleVerificationResult Model
- **Relationships**:
  - Many-to-One with `Vehicle` (verification result for a vehicle)
- **Key Fields**:
  - AI-detected fields: `ai_detected_brand`, `ai_detected_model`, etc.
  - Match scores: Various score fields (0-100) for comparing AI detection with user input
  - `overall_confidence_score`: Overall AI confidence
  - `verification_passed`: Whether verification passed
  - `requires_manual_review`: Flag for manual review requirement

## Relationship Details

1. **User → Vehicle**: 
   - Relationship: One-to-Many
   - On Delete: CASCADE (if user is deleted, their vehicles are deleted)
   - Related Name: `vehicles`

2. **VehicleCategory → Vehicle**: 
   - Relationship: One-to-Many
   - On Delete: SET_NULL (if category is deleted, vehicle category is set to NULL)
   - Nullable: Yes

3. **Vehicle → VehicleImage**: 
   - Relationship: One-to-Many
   - On Delete: CASCADE (if vehicle is deleted, images are deleted)
   - Related Name: `images`

4. **Vehicle → VehicleVerificationResult**: 
   - Relationship: One-to-Many
   - On Delete: CASCADE (if vehicle is deleted, verification results are deleted)
   - Related Name: `verification_results`

## Notes

- The `User` model extends Django's `AbstractUser`, inheriting standard authentication fields
- `Vehicle.plate_number` is unique and indexed for fast lookups
- `VehicleVerificationResult` stores detailed AI verification data including match scores and discrepancies
- All models include `created_at` and/or `updated_at` timestamps for tracking
- The verification system supports multiple verification attempts per vehicle


