import requests
import json
import urllib.parse
from typing import Optional, Dict, Any
import re
import unicodedata
import os
import time
from functools import lru_cache
import threading

def define_env(env):
    no_template = os.environ.get('NO_TEMPLATE', False)
    
    # Cache for API responses
    _template_cache: Dict[str, Any] = {}
    _cache_lock = threading.Lock()
    _cache_ttl = 3600  # 1 hour cache
    
    # Precompiled regex for better performance
    SLUG_REGEX_1 = re.compile(r'[^\w\s$*_+~.()\'"!\-:@]+')
    SLUG_REGEX_2 = re.compile(r'[^A-Za-z0-9\s]')
    SLUG_REGEX_3 = re.compile(r'\s+')

    # Optimized character map (reduced size)
    CHAR_MAP = {
        "$": "dollar", "%": "percent", "&": "and", "<": "less", ">": "greater",
        "|": "or", "¢": "cent", "£": "pound", "¤": "currency", "¥": "yen",
        "©": "(c)", "®": "(r)", "À": "A", "Á": "A", "Â": "A", "Ã": "A",
        "Ä": "A", "Å": "A", "Æ": "AE", "Ç": "C", "È": "E", "É": "E",
        "Ê": "E", "Ë": "E", "Ì": "I", "Í": "I", "Î": "I", "Ï": "I",
        "Ð": "D", "Ñ": "N", "Ò": "O", "Ó": "O", "Ô": "O", "Õ": "O",
        "Ö": "O", "Ø": "O", "Ù": "U", "Ú": "U", "Û": "U", "Ü": "U",
        "Ý": "Y", "Þ": "TH", "ß": "ss", "à": "a", "á": "a", "â": "a",
        "ã": "a", "ä": "a", "å": "a", "æ": "ae", "ç": "c", "è": "e",
        "é": "e", "ê": "e", "ë": "e", "ì": "i", "í": "i", "î": "i",
        "ï": "i", "ð": "d", "ñ": "n", "ò": "o", "ó": "o", "ô": "o",
        "õ": "o", "ö": "o", "ø": "o", "ù": "u", "ú": "u", "û": "u",
        "ü": "u", "ý": "y", "þ": "th", "ÿ": "y", "€": "euro",
        "–": "-", "'": "'", "'": "'", """: "\"", """: "\"",
        "„": "\"", "…": "..."
    }

    @lru_cache(maxsize=1000)
    def custom_slugify(string: str) -> str:
        """Optimized slugify function with caching"""
        if not isinstance(string, str):
            raise ValueError("slugify: string argument expected")

        # Process the string with optimized character mapping
        slug = ''.join(
            CHAR_MAP.get(ch, ch).replace('-', ' ')
            for ch in unicodedata.normalize('NFKC', string)
        )

        # Apply regex optimizations
        slug = SLUG_REGEX_1.sub('', slug)
        slug = SLUG_REGEX_2.sub('', slug).strip()
        slug = SLUG_REGEX_3.sub('-', slug).lower()

        return slug

    def _get_cached_templates(cache_key: str) -> Optional[Dict[str, Any]]:
        """Get cached template data"""
        with _cache_lock:
            cached_data = _template_cache.get(cache_key)
            if cached_data and time.time() - cached_data['timestamp'] < _cache_ttl:
                return cached_data['data']
            return None

    def _set_cached_templates(cache_key: str, data: Dict[str, Any]):
        """Set cached template data"""
        with _cache_lock:
            _template_cache[cache_key] = {
                'data': data,
                'timestamp': time.time()
            }

    def _make_api_request(url: str, timeout: int = 5) -> Optional[Dict[str, Any]]:
        """Make optimized API request with timeout and error handling"""
        try:
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, json.JSONDecodeError, Exception):
            return None

    @env.macro
    def templatesWidget(title: str, slug: str, toLoad: int = 3) -> str:
        """Optimized template widget with caching"""
        
        if no_template:
            return '<div class="n8n-templates-widget"><p>Template widget placeholder.</p></div>'

        # Create cache key
        cache_key = f"{title}:{toLoad}"
        
        # Check cache first
        cached_result = _get_cached_templates(cache_key)
        if cached_result:
            return cached_result

        node_for_template = 'email+imap' if title == 'Email Trigger (IMAP)' else title.replace(' ', '+')
        
        # Fallback link for errors
        fallback_html = (
            f'<span class="n8n-templates-widget-more">'
            f'<a href="https://n8n.io/integrations/{slug}/" target="_blank">'
            f'Browse {title} integration templates</a>, or '
            f'<a href="https://n8n.io/workflows/" target="_blank">search all templates</a>'
            f'</span>'
        )

        # Make API request with timeout
        api_url = f'https://api.n8n.io/api/templates/search?rows={toLoad}&search={node_for_template}&page=1&sort=views:desc'
        data = _make_api_request(api_url, timeout=3)
        
        if not data:
            _set_cached_templates(cache_key, fallback_html)
            return fallback_html

        workflows = data.get("workflows", [])[:toLoad]

        if len(workflows) < 3:
            _set_cached_templates(cache_key, fallback_html)
            return fallback_html

        # Process workflows with optimized error handling
        template_items = []
        for workflow in workflows:
            try:
                workflow_detail = {
                    "title": workflow["name"],
                    "user": workflow["user"].get("name", "n8n Community"),
                    "url": f'https://n8n.io/workflows/{workflow["id"]}-{custom_slugify(workflow["name"])}/',
                }
                template_items.append(
                    f'<div class="n8n-templates-widget-template">'
                    f'<strong>{workflow_detail["title"]}</strong>'
                    f'<p class="n8n-templates-name">by {workflow_detail["user"]}</p>'
                    f'<a class="n8n-templates-link" href="{workflow_detail["url"]}" target="_blank">View template details</a>'
                    f'</div>'
                )
            except (KeyError, TypeError):
                continue

        if not template_items:
            _set_cached_templates(cache_key, fallback_html)
            return fallback_html

        # Build final HTML
        result_html = (
            f'<div class="n8n-templates-widget">'
            f'{"".join(template_items)}'
            f'<span class="n8n-templates-widget-more">'
            f'<a href="https://n8n.io/integrations/{slug}/" target="_blank">Browse {title} integration templates</a>, or '
            f'<a href="https://n8n.io/workflows/" target="_blank">search all templates</a>'
            f'</span></div>'
        )

        # Cache the result
        _set_cached_templates(cache_key, result_html)
        return result_html

    @env.macro
    def workflowDemo(workflow_json: str) -> str:
        """Optimized workflow demo with better error handling"""
        
        if no_template:
            return "<div class='n8n-workflow-preview'><p>Workflow preview placeholder.</p></div>"

        try:
            parsed_workflow_url = urllib.parse.urlparse(workflow_json)

            if parsed_workflow_url.scheme in ["https", "http"]:
                # Make optimized API request
                data = _make_api_request(workflow_json, timeout=5)
                if not data:
                    return "<div class='n8n-workflow-preview'><p>Failed to load workflow.</p></div>"
                
                template_url = f'https://n8n.io/workflows/{data["id"]}-{custom_slugify(data["name"])}/'
                workflow_json_data = {
                    "nodes": data['workflow']['nodes'],
                    "connections": data['workflow']['connections']
                }
                workflow_message = "View template details"
                
            elif parsed_workflow_url.scheme == "file":
                BASE_DIR = os.path.dirname(os.path.abspath(__file__))
                request_path = parsed_workflow_url.path
                file_path = f'{BASE_DIR}/docs/_workflows{request_path}'
                
                try:
                    with open(file_path, 'r', encoding='utf-8') as file:
                        data = json.load(file)
                except (FileNotFoundError, json.JSONDecodeError, IOError):
                    return "<div class='n8n-workflow-preview'><p>Workflow file not found.</p></div>"
                
                template_url = f'/_workflows{request_path}'
                workflow_json_data = {
                    "nodes": data['nodes'],
                    "connections": data['connections']
                }
                workflow_message = "View workflow file"
            else:
                raise ValueError("Workflow JSON must include a URL scheme")

            # Optimize JSON encoding
            encoded_workflow_json = urllib.parse.quote(
                json.dumps(workflow_json_data, separators=(',', ':'))
            )
            
            return (
                f"<div class='n8n-workflow-preview'>"
                f"<n8n-demo hidecanvaserrors='true' clicktointeract='true' frame='false' "
                f"collapseformobile='false' workflow='{encoded_workflow_json}'></n8n-demo>"
                f"<a href='{template_url}' target='_blank'>{workflow_message}</a>"
                f"</div>"
            )

        except Exception as e:
            return f"<div class='n8n-workflow-preview'><p>Error loading workflow: {str(e)}</p></div>"