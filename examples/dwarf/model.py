__author__ = "Vanessa Sochat"
__copyright__ = "Copyright 2022, Vanessa Sochat"
__license__ = "MPL 2.0"

import compspec.graph
from elftools.common.py3compat import bytes2str
from elftools.dwarf.descriptions import (
    describe_attr_value,
    set_global_machine_arch,
)
from elftools.dwarf.locationlists import LocationParser, LocationExpr
from elftools.dwarf.dwarf_expr import DWARFExprParser

import os
import sys
import re

here = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, here)
import location
from corpus import Corpus

# Human friendly names for general tag "types"
known_die_types = {"DW_TAG_array_type": "array"}


class DwarfGraph(compspec.graph.Graph):
    """
    A subclass of Graph to add nodes / relations that are for dwarf.

    Note implementation wise, a subclass of graph can either:
    1. add a custom iter_nodes, iter_relations function to provide those, OR
    2. parse into self.nodes (dict) or self.relations (list) separately.

    For the DWARF example here we do #2 because the examples are small/simple,
    however a different implementation could yield them instead. A better
    implementation would figure out how to do the comparison in pieces so
    we can cut out early.
    """

    def __init__(self, lib):
        self.corpus = Corpus(lib)
        super().__init__()
        self.type_lookup = self.corpus.get_type_lookup()
        self._prepare_location_parser()
        self.extract()

    def _prepare_location_parser(self):
        """
        Prepare the location parser using the dwarf info
        """
        location_lists = self.corpus.location_lists

        # Needed to decode register names in DWARF expressions.
        set_global_machine_arch(self.corpus.machine_arch)
        self.loc_parser = LocationParser(location_lists)

    def extract(self):
        """
        Note that if we wanted to yield facts, the class here could
        re-implement iter_nodes and iter_relations instead of calling this
        to be done first!
        """
        for die in self.corpus.iter_dwarf_information_entries():
            if not die or not die.tag:
                continue

            # Generate facts for the DIE
            self.facts(die)

    def generate_parent(self, die):
        """
        Generate the parent, if one exists.
        relation("A", "id6", "has", "id7").
        """
        parent = die.get_parent()
        if parent:
            if parent not in self.ids:
                self.ids[parent] = self.next()
            self.new_relation(self.ids[parent], "has", self.ids[die])

    def facts(self, die):
        """
        Yield facts for a die. We keep track of ids and relationships here.
        """
        # Have we parsed it yet?
        if die in self.lookup:
            return

        # Assume we are parsing all dies
        if die not in self.ids:
            self.ids[die] = self.next()
        self.lookup[die] = self.ids[die]

        if die.tag == "DW_TAG_namespace":
            return self.parse_namespace(die)

        if die.tag == "DW_TAG_compile_unit":
            return self.parse_compile_unit(die)

        if die.tag == "DW_TAG_class_type":
            return self.parse_class_type(die)

        if die.tag == "DW_TAG_subprogram":
            return self.parse_subprogram(die)

        if die.tag == "DW_TAG_formal_parameter":
            return self.parse_formal_parameter(die)

        # If we are consistent with base type naming, we don't
        # need to associate a base type size with everything that uses it,
        # but rather just the one base type
        if die.tag == "DW_TAG_base_type":
            return self.parse_base_type(die)

        if die.tag == "DW_TAG_variable":
            return self.parse_variable(die)

        if die.tag == "DW_TAG_pointer_type":
            return self.parse_pointer_type(die)

        if die.tag == "DW_TAG_structure_type":
            return self.parse_structure_type(die)

        if die.tag == "DW_TAG_member":
            return self.parse_member(die)

        if die.tag == "DW_TAG_array_type":
            return self.parse_array_type(die)

        if die.tag == "DW_TAG_subrange_type":
            return self.parse_subrange_type(die)

        # TODO haven't seen these yet
        print(die)
        import IPython

        IPython.embed()

        if die.tag == "DW_TAG_union_type":
            return self.parse_union_type(die)

        if die.tag == "DW_TAG_enumeration_type":
            return self.parse_enumeration_type(die)

        if die.tag == "DW_TAG_lexical_block":
            return self.parse_die(die)

        if die.tag == "DW_TAG_base_type":
            return self.parse_base_type(die)

        # Legical blocks wrap other things
        if die.tag == "DW_TAG_lexical_block":
            return self.parse_children(die)

    def parse_sized_generic(self, die, name):
        """
        parse a sized generic, meaning a named type with a parent and size.
        """
        self.new_node(name, get_name(die), self.ids[die])
        self.generate_parent(die)
        self.gen("size", get_size(die), parent=self.ids[die])

    def parse_base_type(self, die):
        return self.parse_sized_generic(die, "basetype")

    def parse_class_type(self, die):
        return self.parse_sized_generic(die, "class")

    def parse_namespace(self, die):
        """
        Parse a namespace, which is mostly a name and relationship
        """
        self.new_node("namespace", get_name(die), self.ids[die])
        self.generate_parent(die)

    def parse_formal_parameter(self, die):
        """
        Parse a formal parameter
        """
        self.parse_sized_generic(die, "parameter")
        self.gen("type", self.get_underlying_type(die), parent=self.ids[die])
        loc = self.parse_location(die)
        if not loc:
            return
        self.gen("location", loc, parent=self.ids[die])

    def parse_pointer_type(self, die):
        """
        Parse a pointer.
        """
        return self.parse_sized_generic(die, "pointer")

    def parse_member(self, die):
        """
        Parse a member, typically belonging to a union
        Note these can have DW_AT_data_member_location but we arn't parsing
        """
        self.new_node("member", get_name(die), self.ids[die])
        self.gen("type", self.get_underlying_type(die), parent=self.ids[die])
        self.generate_parent(die)

    def parse_structure_type(self, die):
        """
        Parse a structure type.
        """
        self.parse_sized_generic(die, "structure")

    def parse_variable(self, die):
        """
        Parse a formal parameter
        """
        self.parse_sized_generic(die, "variable")
        self.gen("type", self.get_underlying_type(die), parent=self.ids[die])
        loc = self.parse_location(die)
        if not loc:
            return
        self.gen("location", loc, parent=self.ids[die])

    def parse_subprogram(self, die):
        """
        Add a function (subprogram) parsed from DWARF
        """
        self.new_node("function", get_name(die), self.ids[die])
        self.generate_parent(die)
        self.gen("type", self.get_underlying_type(die), parent=self.ids[die])

    def parse_array_type(self, die):
        """
        Get an entry for an array.
        """
        self.new_node("array", get_name(die), self.ids[die])
        self.generate_parent(die)
        self.gen("membertype", self.get_underlying_type(die), parent=self.ids[die])

        if "DW_AT_ordering" in die.attributes:
            self.gen(
                "order", die.attributes["DW_AT_ordering"].value, parent=self.ids[die]
            )

        # Case 1: the each member of the array uses a non-traditional storage
        member_size = self._find_nontraditional_size(die)
        if member_size:
            self.gen("membersize", member_size, parent=self.ids[die])

    def parse_compile_unit(self, die):
        """
        Parse a top level compile unit.
        """
        # Generate node, parent (unlikely to have one)
        self.new_node("compileunit", get_name(die), self.ids[die])
        self.generate_parent(die)

        # we could load low/high PC here if needed
        lang = die.attributes.get("DW_AT_language", None)
        if lang:
            die_lang = describe_attr_value(lang, die, die.offset)
            node = self.new_node("language", die_lang)
            self.new_relation(self.ids[die], "has", node.nodeid)

    def _find_nontraditional_size(self, die):
        """
        Tag DIEs can have attributes to indicate their members use a nontraditional
        amount of storage, in which case we find this. Otherwise, look at member size.
        """
        if "DW_AT_byte_stride" in die.attributes:
            return die.attributes["DW_AT_byte_stride"].value
        if "DW_AT_bit_stride" in die.attributes:
            return die.attributes["DW_AT_bit_stride"].value * 8

    def get_underlying_type(self, die, pointer=False):
        """
        Given a type, parse down to the underlying type (and count pointer indirections)
        """
        if die.tag == "DW_TAG_base_type":
            if pointer:
                return "*%s" % get_name(die)
            return get_name(die)

        if "DW_AT_type" not in die.attributes:
            return "unknown"

        # Can we get the underlying type?
        type_die = self.type_lookup.get(die.attributes["DW_AT_type"].value)
        if not type_die:
            return "unknown"

        # Case 1: It's an array (and type is for elements)
        if type_die and type_die.tag in known_die_types:
            if pointer:
                return "*%s" % known_die_types[type_die.tag]
            return known_die_types[type_die.tag]

        if type_die.tag == "DW_TAG_base_type":
            if pointer:
                return "*%s" % get_name(type_die)
            return get_name(type_die)

        # Otherwise, keep digging
        elif type_die:
            while "DW_AT_type" in type_die.attributes:

                if type_die.tag == "DW_TAG_pointer_type":
                    pointer = True

                # Stop when we don't have next dies to parse
                next_die = self.type_lookup.get(type_die.attributes["DW_AT_type"].value)
                if not next_die:
                    break
                type_die = next_die

        if type_die:
            return self.get_underlying_type(type_die, pointer)
        return "unknown"

    def parse_subrange_type(self, die):
        """
        Parse a subrange type
        """
        self.new_node("subrange", get_name(die), self.ids[die])
        self.generate_parent(die)
        self.gen("membertype", self.get_underlying_type(die), parent=self.ids[die])

        # If the upper bound and count are missing, then the upper bound value is unknown.
        count = "unknown"

        # If we have DW_AT_count, this is the length of the subrange
        if "DW_AT_count" in die.attributes:
            count = die.attributes["DW_AT_count"].value

        # If we have both upper and lower bound
        elif (
            "DW_AT_upper_bound" in die.attributes
            and "DW_AT_lower_bound" in die.attributes
        ):
            count = (
                die.attributes["DW_AT_upper_bound"].value
                - die.attributes["DW_AT_lower_bound"].value
            )

        # If the lower bound value is missing, the value is assumed to be a language-dependent default constant.
        elif "DW_AT_upper_bound" in die.attributes:

            # TODO need to get language in here to derive
            # TODO: size seems one off.
            # The default lower bound is 0 for C, C++, D, Java, Objective C, Objective C++, Python, and UPC.
            # The default lower bound is 1 for Ada, COBOL, Fortran, Modula-2, Pascal and PL/I.
            lower_bound = 0
            count = die.attributes["DW_AT_upper_bound"].value - lower_bound
        self.gen("count", count, parent=self.ids[die])

    def parse_location(self, die):
        """
        Look to see if the DIE has DW_AT_location, and if so, parse to get
        registers. The loc_parser is called by elf.py (once) and addde
        to the corpus here when it is parsing DIEs.
        """
        if "DW_AT_location" not in die.attributes:
            return
        attr = die.attributes["DW_AT_location"]
        if self.loc_parser.attribute_has_location(attr, die.cu["version"]):
            loc = self.loc_parser.parse_from_attribute(attr, die.cu["version"])

            # Attribute itself contains location information
            if isinstance(loc, LocationExpr):
                loc = location.get_register_from_expr(
                    loc.loc_expr, die.dwarfinfo.structs, die.cu.cu_offset
                )
                # The first entry is the register
                return location.parse_register(loc[0])

            # List is reference to .debug_loc section
            elif isinstance(loc, list):
                loc = location.get_loclist(loc, die)
                return location.parse_register(loc[0][0])

    ############################ UNDER

    def parse_call_site(self, die, parent):
        """
        Parse a call site
        """
        entry = {}

        # The abstract origin points to the function
        if "DW_AT_abstract_origin" in die.attributes:
            origin = self.type_die_lookup.get(
                die.attributes["DW_AT_abstract_origin"].value
            )
            entry.update({"name": self.get_name(origin)})

        params = []
        for child in die.iter_children():
            # TODO need better param parsing
            if child.tag == "DW_TAG_GNU_call_site_parameter":
                param = self.parse_call_site_parameter(child)
                if param:
                    params.append(param)
            else:
                raise Exception("Unknown call site parameter!:\n%s" % child)

        if entry and params:
            entry["params"] = params
            self.callsites.append(entry)

    def parse_call_site_parameter(self, die):
        """
        Given a callsite parameter, parse the dwarf expression
        """
        param = {}
        loc = self.parse_location(die)
        if loc:
            param["location"] = loc
        if "DW_AT_GNU_call_site_value" in die.attributes:
            expr_parser = DWARFExprParser(die.dwarfinfo.structs)
            expr = die.attributes["DW_AT_GNU_call_site_value"].value
            # print(get_dwarf_from_expr(expr, die.dwarfinfo.structs, cu_offset=die.cu.cu_offset))
        return param

    # TAGs to parse
    def parse_lexical_block(self, die, code=None):
        """
        Lexical blocks typically have variable children?
        """
        for child in die.iter_children():
            if child.tag == "DW_TAG_variable":
                self.parse_variable(child)

            # We found a loop
            elif child.tag == "DW_AT_lexical_block":
                if code == die.abbrev_code:
                    return
                return self.parse_lexical_block(die)

    def parse_union_type(self, die):
        """
        Parse a union type.
        """
        # The size here includes padding
        entry = {
            "name": self.get_name(die),
            "size": self.get_size(die),
            "class": "Union",
        }

        # TODO An incomplete union won't have byte size attribute and will have DW_AT_declaration attribute.
        # page https://dwarfstd.org/doc/DWARF4.pdf 85

        # Parse children (members of the union)
        fields = []
        for child in die.iter_children():
            fields.append(self.parse_member(child))

        if fields:
            entry["fields"] = fields
        return entry

    def parse_enumeration_type(self, die):
        entry = {
            "name": self.get_name(die),
            "size": self.get_size(die),
            "class": "Scalar",
        }
        underlying_type = self.parse_underlying_type(die)
        entry.update(underlying_type)

        fields = []
        for child in die.iter_children():
            field = {
                "name": self.get_name(child),
                "value": child.attributes["DW_AT_const_value"].value,
            }
            fields.append(field)
        if fields:
            entry["fields"] = fields
        return entry

    def parse_sibling(self, die):
        """
        Try parsing a sibling.
        """
        sibling = self.type_die_lookup.get(die.attributes["DW_AT_sibling"].value)
        return self.parse_underlying_type(sibling)

    def add_class(self, die):
        """
        Given a type, add the class
        """
        if die.tag == "DW_TAG_base_type":
            return "Scalar"
        if die.tag == "DW_TAG_structure_type":
            return "Struct"
        if die.tag == "DW_TAG_array_type":
            return "Array"
        return "Unknown"


# Helper functions to parse a die
def get_name(die):
    """
    A common function to get the name for a die
    """
    name = "unknown"
    if "DW_AT_linkage_name" in die.attributes:
        return bytes2str(die.attributes["DW_AT_linkage_name"].value)
    if "DW_AT_name" in die.attributes:
        return bytes2str(die.attributes["DW_AT_name"].value)
    return name


def get_size(die):
    """
    Return size in bytes (not bits)
    """
    size = 0
    if "DW_AT_byte_size" in die.attributes:
        return die.attributes["DW_AT_byte_size"].value
    # A byte is 8 bits
    if "DW_AT_bit_size" in die.attributes:
        return die.attributes["DW_AT_bit_size"].value * 8
    if "DW_AT_data_bit_offset" in die.attributes:
        raise Exception("Found data_bit_offset in die to parse:\n%s" % die)
    return size