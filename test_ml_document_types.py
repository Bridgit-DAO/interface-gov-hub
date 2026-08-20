"""Tests for ML-REQ / ML-ADR document type helpers."""
import unittest

from services.ml_document_types import (
    CORE_ARTIFACT_TYPES,
    ML_DOC_TYPES,
    normalize_ml_doc_type,
    ml_doc_type_label,
)
from services.submissions import get_next_ml_number


class TestMlDocumentTypes(unittest.TestCase):
    def test_normalize_accepts_req_and_adr(self):
        self.assertEqual(normalize_ml_doc_type('req'), 'req')
        self.assertEqual(normalize_ml_doc_type('ADR'), 'adr')
        self.assertEqual(normalize_ml_doc_type('bogus'), 'draft')

    def test_labels(self):
        self.assertEqual(ml_doc_type_label('req'), 'ML-REQ')
        self.assertEqual(ml_doc_type_label('adr'), 'ML-ADR')

    def test_core_artifact_types_include_requirement_and_adr(self):
        self.assertIn('requirement', CORE_ARTIFACT_TYPES)
        self.assertIn('adr', CORE_ARTIFACT_TYPES)

    def test_ml_doc_types_set(self):
        self.assertEqual(ML_DOC_TYPES, frozenset({'draft', 'rfc', 'req', 'adr'}))


class TestMlNumbering(unittest.TestCase):
    def test_req_prefix_shape(self):
        from app import app
        with app.app_context():
            num = get_next_ml_number('req', layer_prefix='ML')
        self.assertTrue(num.startswith('ML-REQ-'))

    def test_adr_prefix_shape(self):
        from app import app
        with app.app_context():
            num = get_next_ml_number('adr', layer_prefix='ML')
        self.assertTrue(num.startswith('ML-ADR-'))


if __name__ == '__main__':
    unittest.main()
