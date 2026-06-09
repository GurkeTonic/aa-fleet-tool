# Standard Library
import socket
from unittest.mock import Mock

# Django
from django.contrib.messages.middleware import MessageMiddleware
from django.contrib.sessions.middleware import SessionMiddleware
from django.core.handlers.wsgi import WSGIRequest
from django.test import RequestFactory, TestCase

# AA Fleet Tool
from aa_fleet_tool.tests.testdata.integrations.allianceauth import load_allianceauth
from aa_fleet_tool.tests.testdata.utils import create_user_from_evecharacter


class SocketAccessError(Exception):
    """Error raised when a test script accesses the network"""


class NoSocketsTestCase(TestCase):
    """Variation of Django's TestCase that prevents any network use."""

    @classmethod
    def setUpClass(cls):
        cls.socket_original = socket.socket
        socket.socket = cls.guard
        return super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        socket.socket = cls.socket_original
        return super().tearDownClass()

    @staticmethod
    def guard(*args, **kwargs):
        raise SocketAccessError("Attempted to access network")


class FleetToolTestCase(NoSocketsTestCase):
    """
    Preloaded TestCase for Fleet Tool tests without network access.

    Available test users:
        * ``user`` — standard Fleet Tool access (``aa_fleet_tool.view_fleet_tool``)
            * Character ID 1001, Corporation 2001, Alliance 3001
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_allianceauth()
        cls.factory = RequestFactory()
        cls.user, cls.user_character = create_user_from_evecharacter(
            character_id=1001,
            permissions=["aa_fleet_tool.view_fleet_tool"],
        )

    def _middleware_process_request(self, request: WSGIRequest):
        """Helper to process middleware for a request."""
        session_middleware = SessionMiddleware(Mock())
        session_middleware.process_request(request)
        message_middleware = MessageMiddleware(Mock())
        message_middleware.process_request(request)
