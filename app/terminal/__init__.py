"""Terminal package — POS error image analysis and PAX error knowledge base."""
from .pos_error_processor import analyze_pos_error_image
from .pax_errors import lookup_pax_error, search_pax_errors

__all__ = ["analyze_pos_error_image", "lookup_pax_error", "search_pax_errors"]
