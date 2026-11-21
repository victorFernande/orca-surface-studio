from html.parser import HTMLParser
import json
import unittest

from orca_wave_studio.studio_ui import get_studio_html


class StudioDocument(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.mode = None
        self.read_state = False
        self.state = ""
        self.scripts = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "body":
            self.mode = attrs.get("data-mode")
        if tag == "script":
            self.scripts.append(attrs)
            self.read_state = attrs.get("id") == "initial-state"

    def handle_endtag(self, tag):
        if tag == "script":
            self.read_state = False

    def handle_data(self, data):
        if self.read_state:
            self.state += data


class StudioUITests(unittest.TestCase):
    def test_object_name_stays_inside_json_script(self):
        state = {"objects": [{"name": '</script><script src="x"></script> & ação'}]}
        doc = StudioDocument(get_studio_html(state, dock=True))
        self.assertEqual(json.loads(doc.state), state)
        self.assertEqual(doc.mode, "dock")
        self.assertEqual(len(doc.scripts), 2)
        self.assertFalse(any("src" in script for script in doc.scripts))

    def test_default_page_has_empty_input(self):
        doc = StudioDocument(get_studio_html())
        self.assertEqual(doc.mode, "page")
        self.assertEqual(json.loads(doc.state), {})
