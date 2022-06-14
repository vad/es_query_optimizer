import json
import hashlib
import logging
from collections import defaultdict
from typing import List, Optional

logger = logging.getLogger(__name__)


class Node:
    def __init__(self, q):
        self._q = q

    def query(self) -> dict:
        return self._q


class BoolNode(Node):
    filter: List[Node]
    must: List[Node]
    must_not: List[Node]
    should: List[Node]

    def __init__(self, filter, must, must_not, should):
        self.filter = filter
        self.must = must
        self.must_not = must_not
        self.should = should

    def total_len(self):
        return len(self.filter) + len(self.must) + len(self.must_not) + len(self.should)

    def query(self):
        q = {}

        for field, name in [
            (self.filter, "filter"),
            (self.must, "must"),
            (self.must_not, "must_not"),
            (self.should, "should"),
        ]:
            if field:
                q[name] = [child.query() for child in field]

        return {"bool": q}


class TermsNode(Node):
    field: Optional[str] = None
    boost: Optional[str] = None

    def __init__(self, q: dict):
        super().__init__(q)

        copy_q = dict(q)
        self.boost = copy_q.pop("boost", None)

        keys = list(key for key in copy_q.keys() if not key.startswith("_"))
        if len(keys) != 1:
            logger.warning("Cannot identify field for terms query %v", q)
            return

        self.field = keys[0]
        self.values = q[self.field]
        self._parameters = None
        self._parameters_hash = None

        # terms lookup, don't merge
        # TODO: test
        if isinstance(self.values, dict):
            self.field = None
            return

        _parameters = dict(q)
        _parameters.pop(self.field)
        self._parameters = _parameters
        self._parameters_hash = hashlib.md5(
            json.dumps(_parameters).encode("utf-8")
        ).digest()

    def mergeability_hash(self) -> str:
        return f"{self.field}:{self._parameters_hash}"

    def is_mergeable(self) -> bool:
        return getattr(self, '_parameters_hash', None) is not None

    def query(self) -> dict:
        return {"terms": self._q}


class QueryParser:
    @classmethod
    def parse(cls, q: dict) -> Node:
        if not q:
            return Node({})

        if "bool" in q:
            b = q["bool"]
            if b.get("_name"):
                # cannot optimize bool with _name
                return Node(q)
            return BoolNode(
                cls.iter_parse(b.get("filter", [])),
                cls.iter_parse(b.get("must", [])),
                cls.iter_parse(b.get("must_not", [])),
                cls.iter_parse(b.get("should", [])),
            )
        if "terms" in q:
            return TermsNode(q["terms"])
        else:
            return Node(q)

    @classmethod
    def iter_parse(cls, iter_queries) -> List[Node]:
        if isinstance(iter_queries, list):
            return [cls.parse(item) for item in iter_queries]
        else:
            return [cls.parse(iter_queries)]


def _optimize_pass(node: Node) -> Node:
    if isinstance(node, BoolNode):
        filter_out = []
        for child in node.filter:
            if not isinstance(child, BoolNode):
                filter_out.append(child)
                continue

            filter_out.extend(child.filter)
            child.filter = []

            filter_out.extend(child.must)
            child.must = []

            # remove child if empty
            if child.total_len():
                filter_out.append(child)
        node.filter = filter_out

        must_out = []
        for child in node.must:
            if not isinstance(child, BoolNode):
                must_out.append(child)
                continue

            must_out.extend(child.must)
            child.must = []

            node.must_not.extend(child.must_not)
            child.must_not = []

            # remove child if empty
            if child.total_len():
                must_out.append(child)
        node.must = must_out

        bool_clauses = {'filter': node.filter, 'must': node.must, 'must_not': node.must_not, 'should': node.should}

        # optimize terms
        for bool_type, bool_clause in bool_clauses.items():
            groupable_terms = defaultdict(list)
            rewrite = []

            for child in bool_clause:
                if bool_type in {'must', 'filter'} or not isinstance(child, TermsNode) or not child.is_mergeable():
                    rewrite.append(child)
                    continue
                groupable_terms[child.mergeability_hash()].append(child)

            for _, terms_list in groupable_terms.items():
                rewrite.append(merge_terms(terms_list))

            # overwrite list
            bool_clause.clear()
            bool_clause.extend(rewrite)

        # recurse
        for bool_clause in bool_clauses.values():
            rewrite = []
            for child in bool_clause:
                optimized_child = _optimize_pass(child)
                rewrite.append(optimized_child)
            bool_clause.clear()
            bool_clause.extend(rewrite)

    return node


def merge_terms(terms_list: List[TermsNode]) -> TermsNode:
    first = terms_list[0]
    if len(terms_list) == 1:
        return first

    values = []
    for other in terms_list:
        values.extend(other.values)
    parameters = dict(first._parameters)
    parameters[first.field] = values
    return TermsNode(parameters)


def optimize(q: dict) -> dict:
    node = QueryParser.parse(q)
    query = node.query()

    iterations = 100
    while iterations > 0:
        iterations -= 1

        node_new = _optimize_pass(node)
        query_new = node_new.query()

        if query_new == query:
            return query

        query = query_new
        node = node_new

    return query
