"""Static discoverability checks complement the real-browser render check."""

from pathlib import Path
import unittest


class PreviewLayoutTests(unittest.TestCase):
    def test_map_is_visible_before_camera_and_metrics(self) -> None:
        """Keep one non-collapsible map near the top with a direct jump link.

        Args:
            None.
        Returns:
            None: assertions fail if the map is buried or IDs are duplicated.
        """
        page = (Path(__file__).resolve().parents[2] / 'src/app/preview.html').read_text()
        self.assertIn('href="#session-view-map"', page)
        self.assertIn('Preview UI: view-map-2', page)
        panel = page.index('<section id="session-view-map"')
        self.assertLess(panel, page.index('<div class="view">'))
        self.assertLess(panel, page.index('<div class="cards">'))
        self.assertNotIn('<details', page[panel:page.index('</section>', panel)])
        for identifier in ('view-map', 'scene-enroll', 'scene-status', 'scene-recording'):
            self.assertEqual(page.count(f'id="{identifier}"'), 1)
