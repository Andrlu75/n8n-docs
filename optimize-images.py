#!/usr/bin/env python3
"""
Script to optimize images in the n8n docs project
- Convert PNG to WebP for better compression
- Resize large images
- Remove unnecessary metadata
"""

import os
import sys
from pathlib import Path
from PIL import Image, ImageOps
import subprocess
import argparse

def convert_to_webp(image_path: Path, output_path: Path, quality: int = 85) -> bool:
    """Convert image to WebP format"""
    try:
        with Image.open(image_path) as img:
            # Remove EXIF data and optimize
            img = ImageOps.exif_transpose(img)
            
            # Convert to RGB if necessary
            if img.mode in ('RGBA', 'LA', 'P'):
                # For images with transparency, keep RGBA
                if img.mode == 'P' and 'transparency' in img.info:
                    img = img.convert('RGBA')
                elif img.mode == 'RGBA':
                    pass  # Keep RGBA
                else:
                    img = img.convert('RGB')
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Save as WebP
            img.save(output_path, 'WebP', quality=quality, optimize=True)
            return True
    except Exception as e:
        print(f"Error converting {image_path}: {e}")
        return False

def resize_image(image_path: Path, max_width: int = 1200, max_height: int = 800) -> bool:
    """Resize image if it's too large"""
    try:
        with Image.open(image_path) as img:
            # Check if resize is needed
            if img.width <= max_width and img.height <= max_height:
                return False
            
            # Calculate new dimensions maintaining aspect ratio
            ratio = min(max_width / img.width, max_height / img.height)
            new_width = int(img.width * ratio)
            new_height = int(img.height * ratio)
            
            # Resize image
            img_resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # Save optimized image
            if image_path.suffix.lower() in ['.jpg', '.jpeg']:
                img_resized.save(image_path, 'JPEG', quality=85, optimize=True)
            else:
                img_resized.save(image_path, optimize=True)
            
            return True
    except Exception as e:
        print(f"Error resizing {image_path}: {e}")
        return False

def optimize_png(image_path: Path) -> bool:
    """Optimize PNG using pngquant if available"""
    try:
        # Check if pngquant is available
        subprocess.run(['pngquant', '--version'], 
                      capture_output=True, check=True)
        
        # Run pngquant
        result = subprocess.run([
            'pngquant', '--force', '--quality=65-85', 
            '--output', str(image_path), str(image_path)
        ], capture_output=True)
        
        return result.returncode == 0
    except (subprocess.CalledProcessError, FileNotFoundError):
        # pngquant not available or failed
        return False

def get_file_size(path: Path) -> int:
    """Get file size in bytes"""
    return path.stat().st_size

def optimize_images_in_directory(docs_dir: Path, convert_webp: bool = False, 
                                resize: bool = True, max_width: int = 1200, 
                                max_height: int = 800) -> dict:
    """Optimize all images in the docs directory"""
    
    results = {
        'processed': 0,
        'converted_webp': 0,
        'resized': 0,
        'optimized_png': 0,
        'total_savings': 0,
        'errors': []
    }
    
    # Image extensions to process
    image_extensions = {'.png', '.jpg', '.jpeg', '.gif'}
    
    # Find all images
    images_dir = docs_dir / '_images'
    if not images_dir.exists():
        print(f"Images directory not found: {images_dir}")
        return results
    
    for image_path in images_dir.rglob('*'):
        if image_path.suffix.lower() not in image_extensions:
            continue
            
        if not image_path.is_file():
            continue
            
        original_size = get_file_size(image_path)
        results['processed'] += 1
        
        print(f"Processing: {image_path.relative_to(docs_dir)}")
        
        # Resize if needed
        if resize and resize_image(image_path, max_width, max_height):
            results['resized'] += 1
            print(f"  Resized to max {max_width}x{max_height}")
        
        # Convert to WebP if requested
        if convert_webp and image_path.suffix.lower() in ['.png', '.jpg', '.jpeg']:
            webp_path = image_path.with_suffix('.webp')
            if convert_to_webp(image_path, webp_path):
                # Check if WebP is smaller
                webp_size = get_file_size(webp_path)
                if webp_size < original_size * 0.8:  # Only keep if 20%+ savings
                    results['converted_webp'] += 1
                    results['total_savings'] += (original_size - webp_size)
                    print(f"  Converted to WebP: {original_size} → {webp_size} bytes")
                else:
                    webp_path.unlink()  # Remove WebP if not beneficial
        
        # Optimize PNG
        elif image_path.suffix.lower() == '.png':
            if optimize_png(image_path):
                new_size = get_file_size(image_path)
                savings = original_size - new_size
                if savings > 0:
                    results['optimized_png'] += 1
                    results['total_savings'] += savings
                    print(f"  Optimized PNG: {original_size} → {new_size} bytes")
    
    return results

def main():
    parser = argparse.ArgumentParser(description='Optimize images in n8n docs')
    parser.add_argument('--docs-dir', type=Path, default=Path('docs'),
                       help='Path to docs directory (default: docs)')
    parser.add_argument('--convert-webp', action='store_true',
                       help='Convert images to WebP format')
    parser.add_argument('--no-resize', action='store_true',
                       help='Skip resizing large images')
    parser.add_argument('--max-width', type=int, default=1200,
                       help='Maximum width for images (default: 1200)')
    parser.add_argument('--max-height', type=int, default=800,
                       help='Maximum height for images (default: 800)')
    
    args = parser.parse_args()
    
    if not args.docs_dir.exists():
        print(f"Error: Docs directory not found: {args.docs_dir}")
        sys.exit(1)
    
    print(f"Optimizing images in: {args.docs_dir}")
    print(f"Convert to WebP: {args.convert_webp}")
    print(f"Resize images: {not args.no_resize}")
    if not args.no_resize:
        print(f"Max dimensions: {args.max_width}x{args.max_height}")
    print()
    
    results = optimize_images_in_directory(
        args.docs_dir, 
        convert_webp=args.convert_webp,
        resize=not args.no_resize,
        max_width=args.max_width,
        max_height=args.max_height
    )
    
    # Print results
    print("\n" + "="*50)
    print("OPTIMIZATION RESULTS")
    print("="*50)
    print(f"Images processed: {results['processed']}")
    if results['converted_webp']:
        print(f"Converted to WebP: {results['converted_webp']}")
    if results['resized']:
        print(f"Images resized: {results['resized']}")
    if results['optimized_png']:
        print(f"PNGs optimized: {results['optimized_png']}")
    
    if results['total_savings'] > 0:
        savings_mb = results['total_savings'] / (1024 * 1024)
        print(f"Total space saved: {savings_mb:.2f} MB")
    
    if results['errors']:
        print(f"\nErrors encountered: {len(results['errors'])}")
        for error in results['errors']:
            print(f"  {error}")

if __name__ == '__main__':
    main()