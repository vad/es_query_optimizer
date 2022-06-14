from .optimizer import optimize


def test_bool_filter_filter():
    opt = optimize(
        {"bool": {"filter": [{"bool": {"filter": [{"exists": {"field": "field1"}}]}}]}}
    )
    assert opt == {"bool": {"filter": [{"exists": {"field": "field1"}}]}}


def test_bool_filter_filter_10_times():
    q = {"exists": {"field": "field1"}}
    for _ in range(10):
        q = {"bool": {"filter": [q]}}
    opt = optimize(q)
    assert opt == {"bool": {"filter": [{"exists": {"field": "field1"}}]}}


def test_bool_filter_must():
    opt = optimize(
        {"bool": {"filter": [{"bool": {"must": [{"exists": {"field": "field1"}}]}}]}}
    )
    assert opt == {"bool": {"filter": [{"exists": {"field": "field1"}}]}}


def test_bool_must_must_not():
    q1 = {"exists": {"field": "field1"}}
    q = {
        "bool": {"must": [{"bool": {"must_not": [q1]}}, {"bool": {"must_not": [q1]}},]}
    }
    opt = optimize(q)
    assert opt == {"bool": {"must_not": [q1, q1]}}


def test_bool_must_not_terms():
    q = {
        "bool": {
            "must": [
                {"bool": {"must_not": [{"terms": {"field1": ["01.11"]}}]}},
                {"bool": {"must_not": [{"terms": {"field1": ["02.22"]}}]}},
            ]
        }
    }
    opt = optimize(q)
    assert opt == {"bool": {"must_not": [{"terms": {"field1": ["01.11", "02.22"]}}]}}


def test_filter_terms():
    q = {
        'bool': {
            'filter': [{
                'bool': {
                    'must': [
                        {'terms': {'field': ['A']}},
                        {'terms': {'field': ['B']}}
                    ]
                }
            }]
        }
    }
    opt = optimize(q)
    assert opt == {'bool': {'filter': [{'terms': {'field': ['A']}}, {'terms': {'field': ['B']}}]}}


def test_should_terms():
    q = {
        'bool': {
            'filter': [{
                'bool': {
                    'should': [
                        {'terms': {'field': ['A']}},
                        {'terms': {'field': ['B']}}
                    ]
                }
            }]
        }
    }
    opt = optimize(q)
    assert opt == {'bool': {'filter': [{'bool': {'should': [{'terms': {'field': ['A', 'B']}}]}}]}}


def test_terms_with_id():
    q = {"bool": {"filter": [{"bool": {"must": [{"terms": {"_id": {"index": "a", "type": "b", "id": 1}}}]}}]}}
    opt = optimize(q)
    assert opt == {"bool": {"filter": [{"terms": {"_id": {"index": "a", "type": "b", "id": 1}}}]}}


def test_dont_destroy_single_item_bool():
    q = {"bool": {"must": {'query_string': {'default_operator': 'AND', 'fields': ['f1', 'f2'], 'query': 'some content'}}}}
    opt = optimize(q)
    assert opt == {"bool": {"must": [{'query_string': {'default_operator': 'AND', 'fields': ['f1', 'f2'], 'query': 'some content'}}]}}


def test_preserve_named_queries():
    q = {
        'bool': {
            'filter': [{
                'bool': {
                    'should': [
                        {'terms': {'field': ['A'], '_name': 'field_A'}},
                        {'terms': {'field': ['B'], '_name': 'field_B'}}
                    ]
                }
            }]
        }
    }
    opt = optimize(q)
    assert opt == q


def test_merge_named_queries_with_same_name():
    q = {
        'bool': {
            'filter': [{
                'bool': {
                    'should': [
                        {'terms': {'field': ['A'], '_name': 'field_C'}},
                        {'terms': {'field': ['B'], '_name': 'field_C'}}
                    ]
                }
            }]
        }
    }
    opt = optimize(q)
    assert opt == {'bool': {'filter': [{'bool': {'should': [{'terms': {'field': ['A', 'B'], '_name': 'field_C'}}]}}]}}
