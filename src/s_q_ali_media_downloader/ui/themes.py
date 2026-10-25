"""Theme management for S-Q Creator Studio.

Provides easy switching between different visual themes:
- Default (current dark theme)
- Neon (electric blue glowing theme)
- Custom themes can be added here
"""

import os
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import QApplication


class ThemeManager:
    """Manage application themes and style switching."""
    
    # Theme options
    THEMES = {
        "neon": "Neon Theme (Electric Blue)",
        "default": "Default Theme",
    }
    
    def __init__(self, app: QApplication):
        """Initialize theme manager.
        
        Args:
            app: The QApplication instance
        """
        self.app = app
        self.current_theme = "default"
    
    def apply_theme(self, theme_name: str) -> bool:
        """Apply a theme to the application.
        
        Args:
            theme_name: Name of the theme to apply
            
        Returns:
            True if theme was applied successfully, False otherwise
        """
        try:
            if theme_name == "neon":
                self._apply_neon_theme()
                self.current_theme = "neon"
            elif theme_name == "default":
                self._apply_default_theme()
                self.current_theme = "default"
            else:
                return False
            
            return True
        except Exception as e:
            print(f"Failed to apply theme '{theme_name}': {e}")
            return False
    
    def _apply_neon_theme(self):
        """Apply the neon theme stylesheet."""
        # Import the neon theme
        from s_q_ali_media_downloader.core.theme_neon import NeonTheme
        
        stylesheet = NeonTheme.get_stylesheet()
        self.app.setStyleSheet(stylesheet)
        
        # Also try to load from QSS file
        qss_path = self._get_qss_path()
        if qss_path and qss_path.exists():
            self._apply_qss_file(qss_path)
    
    def _apply_default_theme(self):
        """Apply the default theme (reset to system defaults)."""
        # Clear custom stylesheet
        self.app.setStyleSheet("")
        self.current_theme = "default"
    
    def _apply_qss_file(self, path: Path):
        """Apply a QSS file to the application."""
        if path.exists():
            with open(path, 'r', encoding='utf-8') as f:
                stylesheet = f.read()
                self.app.setStyleSheet(stylesheet)
    
    def _get_qss_path(self) -> Optional[Path]:
        """Get path to theme QSS files."""
        try:
            # Get the package path
            from s_q_ali_media_downloader import ui
            package_path = Path(ui.__file__).parent / "stylesheets"
            
            if package_path.exists():
                return package_path / "neon.qss"
        except Exception:
            pass
        
        return None
    
    def get_available_themes(self) -> dict:
        """Get list of available themes.
        
        Returns:
            Dictionary mapping theme names to descriptions
        """
        return self.THEMES.copy()
    
    def get_current_theme(self) -> str:
        """Get the currently active theme name.
        
        Returns:
            Theme name (e.g., 'neon', 'default')
        """
        return self.current_theme
    
    def toggle_theme(self) -> str:
        """Toggle between available themes.
        
        Returns:
            Name of the newly applied theme
        """
        themes = list(self.THEMES.keys())
        current_index = themes.index(self.current_theme)
        next_index = (current_index + 1) % len(themes)
        
        new_theme = themes[next_index]
        self.apply_theme(new_theme)
        
        return new_theme


# Global theme manager instance
_theme_manager: Optional[ThemeManager] = None


def get_theme_manager(app: QApplication) -> ThemeManager:
    """Get or create the global theme manager instance.
    
    Args:
        app: The QApplication instance
        
    Returns:
        ThemeManager instance
    """
    global _theme_manager
    if _theme_manager is None:
        _theme_manager = ThemeManager(app)
    return _theme_manager


def apply_neon_theme(app: QApplication):
    """Quick function to apply neon theme to the application.
    
    Args:
        app: The QApplication instance
    """
    from s_q_ali_media_downloader.core.theme_neon import NeonTheme
    app.setStyleSheet(NeonTheme.get_stylesheet())


def apply_default_theme(app: QApplication):
    """Quick function to apply default theme (reset).
    
    Args:
        app: The QApplication instance
    """
    app.setStyleSheet("")
