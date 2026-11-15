import importlib
import json

import pytest
from jsonschema import ValidationError, validate

from conftest import ROOT


def test_gateway_schema_rejects_unknown_nested_fields():
    assert (ROOT / "ci/__init__.py").is_file(), "shared schema derivation missing"
    ci = importlib.import_module("ci")
    crd = b"""kind: CustomResourceDefinition
metadata: {name: httproutes.gateway.networking.k8s.io}
spec:
  versions:
    - name: v1
      schema:
        openAPIV3Schema:
          type: object
          properties:
            metadata: {type: object}
            spec:
              type: object
              properties:
                rules: {type: array, items: {type: object, properties: {name: {type: string}}}}
"""
    schema = ci.strict_gateway_schema(crd, {"type": "object", "properties": {"name": {"type": "string"}}})
    validate({"metadata": {"name": "route"}, "spec": {"rules": [{"name": "rule"}]}}, schema)
    for bad in [{"metadata": {"secretTypo": 1}}, {"spec": {"rules": [{"typo": 1}]}}, {"typo": 1}]:
        with pytest.raises(ValidationError):
            validate(bad, schema)
