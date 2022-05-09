__author__ = "Vanessa Sochat"
__copyright__ = "Copyright 2022, Vanessa Sochat"
__license__ = "MPL 2.0"

import compspec.entity as entity


class Graph:
    """
    A graph implicitly is scoped to one namespace
    """

    def __init__(self):

        # A counter to keep track of ids in this space
        self.count = entity.get_counter()
        self.ids = {}
        self.nodes = {}
        self.lookup = {}
        self.relations = []

    def to_dict(self):
        """
        Output dictionary representation of nodes and relations.
        """
        return {
            "nodes": [v.to_dict() for _, v in self.nodes.items()],
            "relations": [x.to_dict() for x in self.relations],
        }

    @classmethod
    def from_dict(self, obj):
        """
        Return a new graph loaded from a dictionary.
        """
        nodes = obj.get("nodes", [])
        relations = obj.get("relations", [])
        g = Graph()
        [g.new_node(**x) for x in nodes]
        [g.new_relation(**x) for x in relations]
        return g

    def next(self):
        """
        Return next id in the counter.
        """
        return next(self.count)

    def add_node(self, node):
        """
        Add an already generated node.
        """
        self.nodes[f"{node.uid}"] = node

    def add_relation(self, relation):
        """
        Add an already generated relation.
        """
        self.relations.append(relation)

    def new_node(self, name, value, nodeid=None):
        """
        Generate a node with a name (type) and value
        """
        if not nodeid:
            nodeid = self.next()
        node = entity.node(nodeid, name, value)
        self.nodes[f"{nodeid}"] = node
        return node

    def new_relation(self, fromid, relation, toid):
        """
        Generate a relation between parent (fromid) and child (toid).
        The relation here does not hard code a namespace, but it will
        be required to compare between two graphs.
        """
        relation = entity.relation(fromid, relation, toid)
        self.relations.append(relation)
        return relation

    def gen(self, name, value, parent, nodeid=None):
        """
        Generate a node and relation in one swoop!
        A parent is required.
        """
        if not nodeid:
            nodeid = self.next()
        node = entity.node(nodeid, name, value)
        relation = self.new_relation(parent, node.uid)
        return ["node", node.args], relation

    def iter_nodes(self):
        """
        Yield nodes. If a comparison is being done, a namespace needs to be
        added (e.g., node, namespace, *args)
        """
        for _, node in self.nodes.items():
            yield node.args

    def iter_relations(self):
        """
        Yield relations in the same manner.
        """
        for relation in self.relations:
            yield relation.args
