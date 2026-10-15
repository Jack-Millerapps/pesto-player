"""
Reusable UI widgets for Pesto Player
Includes: Button, Slider, ListItem, ProgressBar, etc.

Design philosophy:
- All widgets handle their own rendering and touch detection
- Touch coordinates are passed as (x, y) tuples
- Widgets return True if they were interacted with
- Visual feedback is provided for all interactions
"""

import pygame
import config

# ============================================================================
# BASE WIDGET CLASS
# ============================================================================
class Widget:
    """Base class for all UI widgets"""
    def __init__(self, x, y, width, height):
        self.rect = pygame.Rect(x, y, width, height)
        self.visible = True
        self.enabled = True

    def draw(self, surface):
        """Override this method to draw the widget"""
        pass

    def handle_touch(self, pos):
        """
        Handle touch/click event
        Returns True if the widget was interacted with
        """
        if not self.visible or not self.enabled:
            return False
        return self.rect.collidepoint(pos)


# ============================================================================
# BUTTON WIDGET
# ============================================================================
class Button(Widget):
    """
    A clickable button with text or icon

    Features:
    - Visual feedback on press (color change)
    - Configurable colors and sizes
    - Text or icon support
    - Rounded corners
    """
    def __init__(self, x, y, width, height, text="",
                 bg_color=None, text_color=None, border_radius=10):
        super().__init__(x, y, width, height)
        self.text = text
        self.bg_color = bg_color or config.COLOR_PRIMARY
        self.text_color = text_color or config.COLOR_TEXT_PRIMARY
        self.border_radius = border_radius
        self.pressed = False
        self.font = pygame.font.Font(None, config.FONT_SIZE_MEDIUM)
        self.callback = None  # Optional callback function

    def draw(self, surface):
        if not self.visible:
            return

        # Choose color based on state
        if not self.enabled:
            bg_color = config.COLOR_BG_LIGHTER
            text_color = config.COLOR_TEXT_DISABLED
        elif self.pressed:
            bg_color = config.COLOR_PRIMARY_DARK
            text_color = self.text_color
        else:
            bg_color = self.bg_color
            text_color = self.text_color

        # Draw rounded rectangle background
        pygame.draw.rect(surface, bg_color, self.rect,
                        border_radius=self.border_radius)

        # Draw text centered
        if self.text:
            text_surface = self.font.render(self.text, True, text_color)
            text_rect = text_surface.get_rect(center=self.rect.center)
            surface.blit(text_surface, text_rect)

    def handle_touch(self, pos, event_type='down'):
        """
        Handle touch event
        event_type: 'down' or 'up'
        Returns True if button was clicked (on 'up' event)
        """
        if not super().handle_touch(pos):
            return False

        if event_type == 'down':
            self.pressed = True
            return False
        elif event_type == 'up':
            was_pressed = self.pressed
            self.pressed = False
            if was_pressed and self.callback:
                self.callback()
            return was_pressed

        return False

    def reset_state(self):
        """Reset button to unpressed state"""
        self.pressed = False


# ============================================================================
# ICON BUTTON WIDGET (for play/pause/skip controls)
# ============================================================================
class IconButton(Button):
    """
    A button that displays an icon/symbol instead of text
    Used for play/pause/skip controls
    """
    def __init__(self, x, y, size, icon_type, bg_color=None):
        super().__init__(x, y, size, size, bg_color=bg_color, border_radius=size//2)
        self.icon_type = icon_type  # 'play', 'pause', 'next', 'prev'
        self.icon_color = config.COLOR_TEXT_PRIMARY

    def draw(self, surface):
        if not self.visible:
            return

        # Draw circular background
        if not self.enabled:
            bg_color = config.COLOR_BG_LIGHTER
            icon_color = config.COLOR_TEXT_DISABLED
        elif self.pressed:
            bg_color = config.COLOR_PRIMARY_DARK
            icon_color = self.icon_color
        else:
            bg_color = self.bg_color
            icon_color = self.icon_color

        pygame.draw.circle(surface, bg_color, self.rect.center, self.rect.width // 2)

        # Draw icon
        self._draw_icon(surface, icon_color)

    def _draw_icon(self, surface, color):
        """Draw the icon based on icon_type"""
        center_x, center_y = self.rect.center
        size = self.rect.width // 3

        if self.icon_type == 'play':
            # Draw triangle pointing right
            points = [
                (center_x - size//2, center_y - size),
                (center_x - size//2, center_y + size),
                (center_x + size, center_y)
            ]
            pygame.draw.polygon(surface, color, points)

        elif self.icon_type == 'pause':
            # Draw two vertical bars
            bar_width = size // 2
            bar_height = size * 2
            pygame.draw.rect(surface, color,
                           (center_x - size, center_y - size, bar_width, bar_height))
            pygame.draw.rect(surface, color,
                           (center_x + size//2, center_y - size, bar_width, bar_height))

        elif self.icon_type == 'next':
            # Draw triangle pointing right + bar
            points = [
                (center_x - size, center_y - size),
                (center_x - size, center_y + size),
                (center_x + size//2, center_y)
            ]
            pygame.draw.polygon(surface, color, points)
            pygame.draw.rect(surface, color,
                           (center_x + size//2, center_y - size, size//2, size*2))

        elif self.icon_type == 'prev':
            # Draw triangle pointing left + bar
            points = [
                (center_x + size, center_y - size),
                (center_x + size, center_y + size),
                (center_x - size//2, center_y)
            ]
            pygame.draw.polygon(surface, color, points)
            pygame.draw.rect(surface, color,
                           (center_x - size, center_y - size, size//2, size*2))


# ============================================================================
# PROGRESS BAR / SEEK BAR WIDGET
# ============================================================================
class ProgressBar(Widget):
    """
    A progress bar that can be clicked/dragged to seek

    Features:
    - Shows current progress
    - Touch-draggable for seeking
    - Time labels (current / total)
    """
    def __init__(self, x, y, width, height):
        super().__init__(x, y, width, height)
        self.progress = 0.0  # 0.0 to 1.0
        self.dragging = False
        self.on_seek = None  # Callback for seek events: on_seek(position)

    def draw(self, surface):
        if not self.visible:
            return

        # Draw background track
        track_rect = pygame.Rect(
            self.rect.x,
            self.rect.y + (self.rect.height - config.PROGRESS_BAR_HEIGHT) // 2,
            self.rect.width,
            config.PROGRESS_BAR_HEIGHT
        )
        pygame.draw.rect(surface, config.COLOR_BG_LIGHTER, track_rect,
                        border_radius=config.PROGRESS_BAR_HEIGHT // 2)

        # Draw progress
        if self.progress > 0:
            progress_width = int(self.rect.width * self.progress)
            progress_rect = pygame.Rect(
                self.rect.x,
                track_rect.y,
                progress_width,
                config.PROGRESS_BAR_HEIGHT
            )
            pygame.draw.rect(surface, config.COLOR_PROGRESS, progress_rect,
                           border_radius=config.PROGRESS_BAR_HEIGHT // 2)

        # Draw draggable handle
        if self.progress > 0:
            handle_x = self.rect.x + int(self.rect.width * self.progress)
            handle_y = self.rect.y + self.rect.height // 2
            handle_radius = 8
            pygame.draw.circle(surface, config.COLOR_PRIMARY_LIGHT,
                             (handle_x, handle_y), handle_radius)

    def handle_touch(self, pos, event_type='down'):
        """
        Handle touch for seeking
        Returns True if position changed
        """
        if not self.visible or not self.enabled:
            return False

        if event_type == 'down':
            # Expand touch area vertically for easier grabbing
            expanded_rect = self.rect.inflate(0, 20)
            if expanded_rect.collidepoint(pos):
                self.dragging = True
                self._update_progress(pos[0])
                return True

        elif event_type == 'up':
            if self.dragging:
                self.dragging = False
                return True

        elif event_type == 'motion' and self.dragging:
            self._update_progress(pos[0])
            return True

        return False

    def _update_progress(self, x):
        """Update progress based on touch X position"""
        relative_x = max(0, min(x - self.rect.x, self.rect.width))
        self.progress = relative_x / self.rect.width

        if self.on_seek:
            self.on_seek(self.progress)

    def set_progress(self, progress):
        """Set progress externally (0.0 to 1.0)"""
        self.progress = max(0.0, min(1.0, progress))


# ============================================================================
# LIST ITEM WIDGET
# ============================================================================
class ListItem(Widget):
    """
    A list item showing song/playlist information

    Features:
    - Two-line text (title + subtitle)
    - Optional icon on left
    - Highlight on selection
    """
    def __init__(self, x, y, width, title, subtitle="", data=None):
        super().__init__(x, y, width, config.LIST_ITEM_HEIGHT)
        self.title = title
        self.subtitle = subtitle
        self.data = data  # Store associated data (song object, etc.)
        self.selected = False
        self.font_title = pygame.font.Font(None, config.FONT_SIZE_MEDIUM)
        self.font_subtitle = pygame.font.Font(None, config.FONT_SIZE_SMALL)
        self.on_click = None  # Callback function

    def draw(self, surface):
        if not self.visible:
            return

        # Draw background
        bg_color = config.COLOR_BG_LIGHTER if self.selected else config.COLOR_BG_DARK
        pygame.draw.rect(surface, bg_color, self.rect)

        # Draw bottom border
        pygame.draw.line(surface, config.COLOR_BORDER,
                        (self.rect.left, self.rect.bottom),
                        (self.rect.right, self.rect.bottom), 1)

        # Draw text
        padding = config.LIST_PADDING

        # Title
        title_surface = self.font_title.render(
            self.title, True, config.COLOR_TEXT_PRIMARY
        )
        # Truncate if too long
        if title_surface.get_width() > self.rect.width - padding * 2:
            # Simple truncation (could be improved with ellipsis)
            truncated_title = self.title[:30] + "..."
            title_surface = self.font_title.render(
                truncated_title, True, config.COLOR_TEXT_PRIMARY
            )
        surface.blit(title_surface, (self.rect.x + padding, self.rect.y + 10))

        # Subtitle
        if self.subtitle:
            subtitle_surface = self.font_subtitle.render(
                self.subtitle, True, config.COLOR_TEXT_SECONDARY
            )
            if subtitle_surface.get_width() > self.rect.width - padding * 2:
                truncated_subtitle = self.subtitle[:40] + "..."
                subtitle_surface = self.font_subtitle.render(
                    truncated_subtitle, True, config.COLOR_TEXT_SECONDARY
                )
            surface.blit(subtitle_surface, (self.rect.x + padding, self.rect.y + 35))

    def handle_touch(self, pos, event_type='down'):
        """Handle touch event"""
        if not super().handle_touch(pos):
            return False

        if event_type == 'up':
            if self.on_click:
                self.on_click(self)
            return True

        return False


# ============================================================================
# SCROLLABLE LIST WIDGET
# ============================================================================
class ScrollableList(Widget):
    """
    A scrollable list of ListItem widgets

    Features:
    - Touch scrolling (drag to scroll)
    - Automatic item positioning
    - Clipping to bounds
    """
    def __init__(self, x, y, width, height):
        super().__init__(x, y, width, height)
        self.items = []
        self.scroll_offset = 0
        self.dragging = False
        self.last_touch_y = 0

    def add_item(self, title, subtitle="", data=None):
        """Add an item to the list"""
        item_y = len(self.items) * config.LIST_ITEM_HEIGHT
        item = ListItem(self.rect.x, self.rect.y + item_y,
                       self.rect.width, title, subtitle, data)
        self.items.append(item)
        return item

    def clear_items(self):
        """Clear all items from the list"""
        self.items = []
        self.scroll_offset = 0

    def draw(self, surface):
        if not self.visible:
            return

        # Create a clipping rectangle
        clip_rect = surface.get_clip()
        surface.set_clip(self.rect)

        # Draw visible items
        for item in self.items:
            # Adjust item position based on scroll offset
            item.rect.y = self.rect.y + (self.items.index(item) * config.LIST_ITEM_HEIGHT) + self.scroll_offset

            # Only draw if visible in the viewport
            if (item.rect.bottom >= self.rect.top and
                item.rect.top <= self.rect.bottom):
                item.draw(surface)

        # Restore clip
        surface.set_clip(clip_rect)

        # Draw scrollbar indicator if needed
        total_height = len(self.items) * config.LIST_ITEM_HEIGHT
        if total_height > self.rect.height:
            self._draw_scrollbar(surface, total_height)

    def _draw_scrollbar(self, surface, total_height):
        """Draw a scrollbar indicator on the right side"""
        scrollbar_height = max(20, (self.rect.height / total_height) * self.rect.height)
        scroll_progress = abs(self.scroll_offset) / (total_height - self.rect.height)
        scrollbar_y = self.rect.y + (self.rect.height - scrollbar_height) * scroll_progress

        scrollbar_rect = pygame.Rect(
            self.rect.right - 4,
            int(scrollbar_y),
            3,
            int(scrollbar_height)
        )
        pygame.draw.rect(surface, config.COLOR_PRIMARY, scrollbar_rect,
                        border_radius=2)

    def handle_touch(self, pos, event_type='down'):
        """Handle touch for scrolling and item selection"""
        if not self.visible:
            return False

        if not self.rect.collidepoint(pos):
            if event_type == 'up':
                self.dragging = False
            return False

        if event_type == 'down':
            self.dragging = True
            self.last_touch_y = pos[1]

            # Check if an item was clicked
            for item in self.items:
                if item.rect.collidepoint(pos):
                    item.handle_touch(pos, 'down')
            return True

        elif event_type == 'motion' and self.dragging:
            # Scroll the list
            delta_y = pos[1] - self.last_touch_y
            self.last_touch_y = pos[1]
            self._scroll(delta_y)
            return True

        elif event_type == 'up':
            was_dragging = self.dragging
            self.dragging = False

            # If it was a small drag, treat as click
            if not was_dragging or abs(pos[1] - self.last_touch_y) < 5:
                for item in self.items:
                    if item.rect.collidepoint(pos):
                        item.handle_touch(pos, 'up')
                        return True

        return False

    def _scroll(self, delta_y):
        """Scroll the list by delta_y pixels"""
        total_height = len(self.items) * config.LIST_ITEM_HEIGHT

        self.scroll_offset += delta_y

        # Clamp scroll offset
        max_scroll = 0
        min_scroll = -(total_height - self.rect.height)

        if total_height <= self.rect.height:
            self.scroll_offset = 0
        else:
            self.scroll_offset = max(min_scroll, min(max_scroll, self.scroll_offset))


# ============================================================================
# TEXT LABEL WIDGET
# ============================================================================
class Label(Widget):
    """Simple text label"""
    def __init__(self, x, y, text, font_size=config.FONT_SIZE_MEDIUM,
                 color=None, align='left'):
        self.font = pygame.font.Font(None, font_size)
        text_surface = self.font.render(text, True, color or config.COLOR_TEXT_PRIMARY)
        width, height = text_surface.get_size()

        super().__init__(x, y, width, height)
        self.text = text
        self.color = color or config.COLOR_TEXT_PRIMARY
        self.align = align

    def draw(self, surface):
        if not self.visible:
            return

        text_surface = self.font.render(self.text, True, self.color)

        if self.align == 'center':
            text_rect = text_surface.get_rect(center=(self.rect.centerx, self.rect.centery))
            surface.blit(text_surface, text_rect)
        elif self.align == 'right':
            text_rect = text_surface.get_rect(right=self.rect.right, centery=self.rect.centery)
            surface.blit(text_surface, text_rect)
        else:  # left
            surface.blit(text_surface, self.rect.topleft)

    def set_text(self, text):
        """Update the label text"""
        self.text = text


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================
def format_time(seconds):
    """Format seconds as MM:SS"""
    if seconds is None or seconds < 0:
        return "0:00"

    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes}:{secs:02d}"
