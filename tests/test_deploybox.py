
import importlib.util
import io
import os
import sys
import types
import unittest
import zipfile

from pathlib import Path
from unittest.mock import MagicMock, patch


ROOT = Path(__file__).resolve().parents[1]


def load_module(name, relative):
    spec = importlib.util.spec_from_file_location(
        name,
        ROOT / relative,
    )

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    return module


class WebhookTests(unittest.TestCase):

    def setUp(self):
        self.fake_boto = types.ModuleType("boto3")
        self.fake_boto.resource = MagicMock()
        self.fake_boto.client = MagicMock()

        self.env = patch.dict(
            os.environ,
            {
                "TABLE_NAME": "test",
                "DEPLOY_ENGINE_FUNCTION": "engine",
            },
        )
        self.env.start()

        self.boto = patch.dict(
            sys.modules,
            {
                "boto3": self.fake_boto
            },
        )
        self.boto.start()

        self.handler = load_module(
            "webhook_under_test",
            "src/webhook_handler/app.py",
        )

    def tearDown(self):
        self.boto.stop()
        self.env.stop()

    def test_preflight(self):
        result = self.handler.lambda_handler(
            {
                "httpMethod": "OPTIONS"
            },
            None,
        )

        self.assertEqual(
            result["statusCode"],
            200,
        )

        self.assertEqual(
            result["headers"]["Access-Control-Allow-Origin"],
            "*",
        )

    def test_bad_repo(self):
        result = self.handler.lambda_handler(
            {
                "httpMethod": "POST",
                "body": (
                    '{"repository":'
                    '{"full_name":"invalid"}}'
                ),
            },
            None,
        )

        self.assertEqual(
            result["statusCode"],
            400,
        )

    def test_successful_queue(self):
        self.handler.LAMBDA.invoke.return_value = {
            "StatusCode": 202
        }

        result = self.handler.lambda_handler(
            {
                "httpMethod": "POST",
                "body": (
                    '{"repository":'
                    '{"full_name":"owner/repo"}}'
                ),
            },
            None,
        )

        self.assertEqual(
            result["statusCode"],
            202,
        )

        self.handler.DYNAMODB.Table.return_value \
            .put_item.assert_called_once()


class ArchiveTests(unittest.TestCase):

    def setUp(self):
        self.fake_boto = types.ModuleType("boto3")
        self.fake_boto.resource = MagicMock()
        self.fake_boto.client = MagicMock()

        self.env = patch.dict(
            os.environ,
            {
                "TABLE_NAME": "test",
                "DEPLOY_BUCKET": "test-bucket",
            },
        )
        self.env.start()

        self.boto = patch.dict(
            sys.modules,
            {
                "boto3": self.fake_boto
            },
        )
        self.boto.start()

        self.engine = load_module(
            "engine_under_test",
            "src/deploy_engine/app.py",
        )

    def tearDown(self):
        self.boto.stop()
        self.env.stop()

    def archive(self, files):
        buf = io.BytesIO()

        with zipfile.ZipFile(buf, "w") as z:
            for name, data in files.items():
                z.writestr(name, data)

        buf.seek(0)
        return zipfile.ZipFile(buf)

    def test_valid_static_site(self):
        with self.archive(
            {
                "repo-abc/index.html": "<h1>Hello</h1>",
                "repo-abc/style.css": "body{}",
            }
        ) as z:
            files = self.engine.extract_static_files(z)

        self.assertEqual(
            len(files),
            2,
        )

    def test_missing_index(self):
        with self.archive(
            {
                "repo-abc/style.css": "body{}"
            }
        ) as z:
            with self.assertRaises(ValueError):
                self.engine.extract_static_files(z)

    def test_path_traversal(self):
        with self.archive(
            {
                "repo-abc/index.html": "ok",
                "repo-abc/../bad.html": "bad",
            }
        ) as z:
            with self.assertRaises(ValueError):
                self.engine.extract_static_files(z)


if __name__ == "__main__":
    unittest.main()
