# ads_post/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from .models import Vehicle, VehicleCategory, VehicleDocument
from .serializers import VehicleSerializer, VehicleCategorySerializer
import jwt
from django.conf import settings
from rest_framework.parsers import MultiPartParser, FormParser

JWT_SECRET = getattr(settings, 'JWT_SECRET', settings.SECRET_KEY)

def get_user_id_from_request(request):
    token = request.COOKIES.get('jwt')
    if not token:
        raise AuthenticationFailed('Unauthenticated! Please log in to continue.')
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
    except jwt.ExpiredSignatureError:
        raise AuthenticationFailed('Session expired! Please log in again.')
    except jwt.InvalidTokenError:
        raise AuthenticationFailed('Invalid token! Please log in again.')
    return payload['id']


class VehicleCategoryView(APIView):
    def get(self, request):
        cats = VehicleCategory.objects.all()
        serializer = VehicleCategorySerializer(cats, many=True)
        return Response(serializer.data)


@method_decorator(csrf_exempt, name='dispatch')
class VehicleListCreateView(APIView):
    parser_classes = [MultiPartParser, FormParser]  # to allow file uploads

    def get(self, request):
        # Public listing - no authentication required for browsing
        mine = request.query_params.get('mine', 'false').lower() == 'true'
        
        if mine:
            # Only require auth when filtering for user's own vehicles
            user_id = get_user_id_from_request(request)
            qs = Vehicle.objects.filter(posted_by_id=user_id).order_by('-created_at')
        else:
            # Public listing - anyone can browse
            qs = Vehicle.objects.all().order_by('-created_at')

        serializer = VehicleSerializer(qs, many=True, context={'request': request})
        return Response(serializer.data)

    def post(self, request):
        from .models import VehicleImage
        from django.db import IntegrityError
        
        # Get user ID with proper error handling
        try:
            user_id = get_user_id_from_request(request)
        except AuthenticationFailed as e:
            return Response(
                {'detail': str(e)},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        data = request.data.copy()
        
        # Check for duplicate plate number if provided
        plate_number = data.get('plate_number', '').strip()
        if plate_number:
            existing_vehicle = Vehicle.objects.filter(plate_number=plate_number).first()
            if existing_vehicle:
                return Response({
                    'detail': f'A vehicle with plate number "{plate_number}" already exists. Each vehicle must have a unique plate number.',
                    'plate_number': plate_number,
                    'existing_vehicle_id': existing_vehicle.id
                }, status=status.HTTP_400_BAD_REQUEST)
        
        # Remove images and documents from data as we'll handle them separately
        images = request.FILES.getlist('images')
        document_file = request.FILES.get('document')
        document_type = data.get('document_type', 'emission_test').strip()
        
        # Validate document - only emission test is accepted
        if document_file:
            if document_type != 'emission_test':
                return Response({
                    'detail': 'Only Emission Test Certificate is accepted. Please upload your vehicle\'s emission test certificate.'
                }, status=status.HTTP_400_BAD_REQUEST)
        else:
            # Document is required
            return Response({
                'detail': 'Emission Test Certificate is required. Please upload your vehicle\'s emission test certificate.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create vehicle
        serializer = VehicleSerializer(data=data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        
        try:
            vehicle = serializer.save(posted_by_id=user_id)
        except IntegrityError as e:
            if 'plate_number' in str(e):
                return Response({
                    'detail': f'A vehicle with plate number "{plate_number}" already exists. Each vehicle must have a unique plate number.',
                    'plate_number': plate_number
                }, status=status.HTTP_400_BAD_REQUEST)
            raise
        
        # Add images
        for index, image_file in enumerate(images):
            VehicleImage.objects.create(
                vehicle=vehicle,
                image=image_file,
                is_primary=(index == 0)  # First image is primary
            )
        
        # Add document if provided
        if document_file and document_type:
            VehicleDocument.objects.create(
                vehicle=vehicle,
                document_type=document_type,
                document_file=document_file
            )
        
        # Return updated vehicle with images and document
        updated_serializer = VehicleSerializer(vehicle, context={'request': request})
        return Response(updated_serializer.data, status=status.HTTP_201_CREATED)


@method_decorator(csrf_exempt, name='dispatch')
class VehicleDetailView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request, ad_id):
        # Public view - no authentication required to view vehicle details
        vehicle = get_object_or_404(Vehicle, id=ad_id)
        serializer = VehicleSerializer(vehicle, context={'request': request})
        return Response(serializer.data)

    def put(self, request, ad_id):
        from .models import VehicleImage
        from django.db import IntegrityError
        
        user_id = get_user_id_from_request(request)
        vehicle = get_object_or_404(Vehicle, id=ad_id)
        if vehicle.posted_by_id != user_id:
            return Response({'detail': 'Not allowed'}, status=status.HTTP_403_FORBIDDEN)

        data = request.data.copy()
        
        # Check for duplicate plate number if being changed
        plate_number = data.get('plate_number', '').strip()
        if plate_number and plate_number != vehicle.plate_number:
            existing_vehicle = Vehicle.objects.filter(plate_number=plate_number).exclude(id=ad_id).first()
            if existing_vehicle:
                return Response({
                    'detail': f'A vehicle with plate number "{plate_number}" already exists. Each vehicle must have a unique plate number.',
                    'plate_number': plate_number,
                    'existing_vehicle_id': existing_vehicle.id
                }, status=status.HTTP_400_BAD_REQUEST)
        
        # Handle new images if provided
        images = request.FILES.getlist('images')
        if images:
            # Optional: delete old images or keep them
            # vehicle.images.all().delete()  # Uncomment to replace all images
            
            # Add new images
            existing_count = vehicle.images.count()
            for index, image_file in enumerate(images):
                VehicleImage.objects.create(
                    vehicle=vehicle,
                    image=image_file,
                    is_primary=(existing_count == 0 and index == 0)
                )

        # Update vehicle data
        serializer = VehicleSerializer(vehicle, data=data, partial=True, context={'request': request})
        serializer.is_valid(raise_exception=True)
        
        try:
            serializer.save()
        except IntegrityError as e:
            if 'plate_number' in str(e):
                return Response({
                    'detail': f'A vehicle with plate number "{plate_number}" already exists. Each vehicle must have a unique plate number.',
                    'plate_number': plate_number
                }, status=status.HTTP_400_BAD_REQUEST)
            raise
        
        return Response(serializer.data)

    def delete(self, request, ad_id):
        user_id = get_user_id_from_request(request)
        vehicle = get_object_or_404(Vehicle, id=ad_id)
        if vehicle.posted_by_id != user_id:
            return Response({'detail': 'Not allowed'}, status=status.HTTP_403_FORBIDDEN)
        vehicle.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@method_decorator(csrf_exempt, name='dispatch')
class VehicleImageDeleteView(APIView):
    def delete(self, request, image_id):
        from .models import VehicleImage
        
        user_id = get_user_id_from_request(request)
        image = get_object_or_404(VehicleImage, id=image_id)
        
        # Check if user owns the vehicle
        if image.vehicle.posted_by_id != user_id:
            return Response({'detail': 'Not allowed'}, status=status.HTTP_403_FORBIDDEN)
        
        image.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
