#!/usr/bin/env python3
"""
Performance testing script for MkDocs builds
Compares build times between original and optimized configurations
"""

import os
import sys
import time
import subprocess
import shutil
from pathlib import Path
import json
from typing import Dict, List, Tuple

def run_build_test(config_file: str, description: str, runs: int = 3) -> Dict:
    """Run MkDocs build test multiple times and measure performance"""
    
    print(f"\n{'='*60}")
    print(f"Testing: {description}")
    print(f"Config: {config_file}")
    print(f"Runs: {runs}")
    print(f"{'='*60}")
    
    results = {
        'description': description,
        'config_file': config_file,
        'runs': [],
        'avg_time': 0,
        'min_time': float('inf'),
        'max_time': 0,
        'success_rate': 0,
        'site_size': 0,
        'errors': []
    }
    
    successful_runs = 0
    total_time = 0
    
    for run in range(1, runs + 1):
        print(f"\nRun {run}/{runs}:")
        
        # Clean site directory
        site_dir = Path('site')
        if site_dir.exists():
            shutil.rmtree(site_dir)
        
        # Measure build time
        start_time = time.time()
        
        try:
            # Run MkDocs build
            result = subprocess.run([
                'mkdocs', 'build', '--config-file', config_file, '--quiet'
            ], capture_output=True, text=True, timeout=300)  # 5 minute timeout
            
            end_time = time.time()
            build_time = end_time - start_time
            
            if result.returncode == 0:
                successful_runs += 1
                total_time += build_time
                
                # Measure site size
                site_size = get_directory_size(site_dir) if site_dir.exists() else 0
                
                run_result = {
                    'run': run,
                    'time': build_time,
                    'site_size': site_size,
                    'success': True,
                    'error': None
                }
                
                results['runs'].append(run_result)
                results['min_time'] = min(results['min_time'], build_time)
                results['max_time'] = max(results['max_time'], build_time)
                
                print(f"  ✓ Success: {build_time:.2f}s, Site size: {site_size/1024/1024:.1f}MB")
                
            else:
                error_msg = result.stderr or result.stdout or "Unknown error"
                run_result = {
                    'run': run,
                    'time': None,
                    'site_size': 0,
                    'success': False,
                    'error': error_msg.strip()
                }
                
                results['runs'].append(run_result)
                results['errors'].append(f"Run {run}: {error_msg.strip()}")
                
                print(f"  ✗ Failed: {error_msg.strip()[:100]}...")
                
        except subprocess.TimeoutExpired:
            error_msg = "Build timed out (>5 minutes)"
            run_result = {
                'run': run,
                'time': None,
                'site_size': 0,
                'success': False,
                'error': error_msg
            }
            
            results['runs'].append(run_result)
            results['errors'].append(f"Run {run}: {error_msg}")
            print(f"  ✗ {error_msg}")
            
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            run_result = {
                'run': run,
                'time': None,
                'site_size': 0,
                'success': False,
                'error': error_msg
            }
            
            results['runs'].append(run_result)
            results['errors'].append(f"Run {run}: {error_msg}")
            print(f"  ✗ {error_msg}")
    
    # Calculate statistics
    if successful_runs > 0:
        results['avg_time'] = total_time / successful_runs
        results['success_rate'] = (successful_runs / runs) * 100
        
        # Get average site size from successful runs
        successful_sizes = [r['site_size'] for r in results['runs'] if r['success']]
        if successful_sizes:
            results['site_size'] = sum(successful_sizes) / len(successful_sizes)
    else:
        results['min_time'] = 0
    
    return results

def get_directory_size(path: Path) -> int:
    """Get total size of directory in bytes"""
    total_size = 0
    try:
        for dirpath, dirnames, filenames in os.walk(path):
            for filename in filenames:
                filepath = Path(dirpath) / filename
                try:
                    total_size += filepath.stat().st_size
                except (OSError, FileNotFoundError):
                    continue
    except (OSError, FileNotFoundError):
        pass
    return total_size

def print_results_summary(results: List[Dict]):
    """Print comparison summary of all test results"""
    
    print(f"\n{'='*80}")
    print("PERFORMANCE COMPARISON SUMMARY")
    print(f"{'='*80}")
    
    if not results:
        print("No results to display.")
        return
    
    # Find baseline (original) for comparison
    baseline = None
    for result in results:
        if 'original' in result['description'].lower() or result['config_file'] == 'mkdocs.yml':
            baseline = result
            break
    
    if not baseline:
        baseline = results[0]
    
    print(f"{'Configuration':<30} {'Avg Time':<12} {'Site Size':<12} {'Success':<10} {'Improvement':<12}")
    print("-" * 80)
    
    for result in results:
        avg_time = result['avg_time']
        site_size = result['site_size'] / (1024 * 1024)  # Convert to MB
        success_rate = result['success_rate']
        
        # Calculate improvement
        if baseline['avg_time'] > 0 and avg_time > 0 and result != baseline:
            time_improvement = ((baseline['avg_time'] - avg_time) / baseline['avg_time']) * 100
            improvement_str = f"{time_improvement:+.1f}%"
        elif result == baseline:
            improvement_str = "baseline"
        else:
            improvement_str = "N/A"
        
        time_str = f"{avg_time:.2f}s" if avg_time > 0 else "FAILED"
        size_str = f"{site_size:.1f}MB" if site_size > 0 else "N/A"
        success_str = f"{success_rate:.0f}%"
        
        description = result['description'][:29]
        print(f"{description:<30} {time_str:<12} {size_str:<12} {success_str:<10} {improvement_str:<12}")
    
    # Print detailed errors if any
    for result in results:
        if result['errors']:
            print(f"\nErrors in {result['description']}:")
            for error in result['errors']:
                print(f"  • {error}")

def save_results_json(results: List[Dict], filename: str = "performance_results.json"):
    """Save results to JSON file"""
    with open(filename, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to {filename}")

def main():
    if not shutil.which('mkdocs'):
        print("Error: mkdocs command not found. Please activate the virtual environment.")
        sys.exit(1)
    
    # Test configurations
    test_configs = [
        {
            'file': 'mkdocs.yml',
            'description': 'Original Configuration',
            'available': Path('mkdocs.yml').exists()
        },
        {
            'file': 'mkdocs-optimized.yml', 
            'description': 'Optimized Configuration',
            'available': Path('mkdocs-optimized.yml').exists()
        }
    ]
    
    # Filter available configs
    available_configs = [config for config in test_configs if config['available']]
    
    if not available_configs:
        print("Error: No configuration files found!")
        sys.exit(1)
    
    print("MkDocs Performance Testing")
    print(f"Available configurations: {len(available_configs)}")
    
    # Run tests
    all_results = []
    
    for config in available_configs:
        try:
            result = run_build_test(
                config_file=config['file'],
                description=config['description'],
                runs=3
            )
            all_results.append(result)
        except KeyboardInterrupt:
            print(f"\nTest interrupted for {config['description']}")
            break
        except Exception as e:
            print(f"\nError testing {config['description']}: {e}")
            continue
    
    # Print summary
    if all_results:
        print_results_summary(all_results)
        save_results_json(all_results)
    else:
        print("No successful tests completed.")

if __name__ == '__main__':
    main()