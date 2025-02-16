# Copyright 2017 Martin Olejar
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os

from .head import Header, DTB_BEGIN_NODE, DTB_END_NODE, DTB_PROP, DTB_END, DTB_NOP
from .item import new_property, Property, PropBytes, PropWords, PropStrings, PropIncBin, Node
from .misc import strip_comments, split_to_lines, get_version_info, extract_string

__author__  = "Martin Olejar"
__contact__ = "martin.olejar@gmail.com"
__version__ = "0.1.2"
__license__ = "Apache 2.0"
__status__  = "Development"
__all__     = [
    # FDT Classes
    'FDT',
    'Node',
    'Header',
    # properties
    'Property',
    'PropBytes',
    'PropWords',
    'PropStrings',
    'PropIncBin',
    # core methods
    'parse_dts',
    'parse_dtb',
    'diff'
]


class ItemType:
    NODE = 0
    PROP = 1
    BOTH = 3


class FDT(object):
    """ Flattened Device Tree Class """

    @property
    def empty(self):
        return self.root_node.empty

    def __init__(self, header=None):
        self.header = Header() if header is None else header
        self.entries = []
        self.root_node = Node('/')

    def __str__(self):
        """ String representation """
        return self.info()

    def info(self):
        """ Return object info in human readable format """
        msg = "FDT Content:\n"
        for path, nodes, props in self.walk():
            msg += "{} [{}N, {}P]\n".format(path, len(nodes), len(props))
        return msg

    def get_node(self, path, create=False):
        """ Get node from specified path
        :param path: Path as string
        :param create: If True, not existing nodes will be created
        :return: Node object
        """
        assert isinstance(path, str), "Node path must be a string type !"

        node = self.root_node
        path = path.lstrip('/')
        if path:
            names = path.split('/')
            for name in names:
                item = node.get_subnode(name)
                if item is None:
                    if create:
                        item = Node(name)
                        node.append(item)
                    else:
                        raise ValueError("Path \"{}\" doesn't exists".format(self, path))
                node = item

        return node

    def get_property(self, name, path=''):
        """ Get property obj by name
        :param name: Property name
        :param path: Path to sub-node
        :return: property object
        """
        return self.get_node(path).get_property(name)

    def set_property(self, name, value, path=''):
        """ Get property obj by name
        :param name: Property name
        :param value: Property value
        :param path: Path to sub-node
        """
        self.get_node(path).set_property(name, value)

    def exist_node(self, path):
        """ Check if <path>/node exist
        :param path: path/node name
        :return True if <path>/node exist else False
        """
        try:
            self.get_node(path)
        except:
            return False
        else:
            return True

    def exist_property(self, name, path=''):
        """ Check if property exist
        :param name: Property name
        :return True if property exist else False
        """
        return self.get_node(path).exist_property(name) if self.exist_node(path) else False

    def remove_node(self, name, path=''):
        """ Remove node obj by path/name. Raises ValueError if path/name doesn't exist
        :param name: Node name
        :param path: Path to sub-node
        """
        self.get_node(path).remove_subnode(name)

    def remove_property(self, name, path=''):
        """ Remove property obj by name. Raises ValueError if path/name doesn't exist
        :param name: Property name
        :param path: Path to sub-node
        """
        self.get_node(path).remove_property(name)

    def add_item(self, obj, path='', create=True):
        """ Add sub-node or property at specified path. Raises ValueError if path doesn't exist
        :param obj: The node or property object
        :param path: The path to sub-node
        :param create: If True, not existing nodes will be created
        """
        self.get_node(path, create).append(obj)

    def search(self, name, itype=ItemType.BOTH, path=''):
        """ Search property/node in all sub-nodes
        :param name: Property or Node name
        :param itype:
        :param path: Path to root node
        :return: List of founded properties
        """
        assert isinstance(name, str), "Property name must be a string type !"

        node = self.get_node(path)
        nodes = []
        items = []
        while True:
            nodes += node.nodes
            if itype == ItemType.NODE or itype == ItemType.BOTH:
                if node.name == name:
                    items.append(node)
            if itype == ItemType.PROP or itype == ItemType.BOTH:
                for p in node.props:
                    if p.name == name:
                        items.append(p)
            if not nodes: break
            node = nodes.pop()

        return items

    def walk(self, path='', relative=False):
        """ Walk trough nodes and return relative/absolute path with list of sub-nodes and properties
        :param path: The path to root node
        :param relative: True for relative or False for absolute return path
        :return: List with 3 items
        """
        node = self.get_node(path)
        nodes = []
        while True:
            nodes += node.nodes
            current_path = "{}/{}".format(node.path, node.name).replace('///', '/').replace('//', '/')
            if path and relative:
                current_path = current_path.replace(path, '').lstrip('/')
            yield (current_path, node.nodes, node.props)
            if not nodes: break
            node = nodes.pop()

    def merge(self, fdt_obj, replace=True):
        """ Merge external FDT object into this object.
        :param fdt_obj: The FDT object which will be merged into this
        """
        assert isinstance(fdt_obj, FDT), "Invalid object type"
        if self.header.version is None:
            self.header = fdt_obj.header
        else:
            if fdt_obj.header.version is not None and \
               fdt_obj.header.version > self.header.version:
                self.header.version = fdt_obj.header.version
        if fdt_obj.entries:
            for in_entry in fdt_obj.entries:
                exist = False
                for index in range(len(self.entries)):
                    if self.entries[index]['address'] == in_entry['address']:
                        self.entries[index]['address'] = in_entry['size']
                        exist = True
                        break
                if not exist:
                    self.entries.append(in_entry)

        self.root_node.merge(fdt_obj.get_node('/'), replace)

    def to_dts(self, tabsize=4):
        """ Store FDT Object into string format (DTS)

        :param tabsize:
        :return:
        """
        result = "/dts-v1/;\n"
        if self.header.version is not None:
            result += "// version: {}\n".format(self.header.version)
            result += "// last_comp_version: {}\n".format(self.header.last_comp_version)
            if self.header.version >= 2:
                result += "// boot_cpuid_phys: 0x{:X}\n".format(self.header.boot_cpuid_phys)
        result += '\n'
        if self.entries:
            for entry in self.entries:
                result += "/memreserve/ "
                result += "{:#x} ".format(entry['address']) if entry['address'] else "0 "
                result += "{:#x}".format(entry['size']) if entry['size'] else "0"
                result += ";\n"
        if self.root_node is not None:
            result += self.root_node.to_dts(tabsize)
        return result

    def to_dtb(self, version=None, last_comp_version=None, boot_cpuid_phys=None):
        """ Export FDT Object into Binary Blob format (DTB)

        :param version:
        :param last_comp_version:
        :param boot_cpuid_phys:
        :return:
        """
        if self.root_node is None:
            return None

        from struct import pack

        if version is not None:
            self.header.version = version
        if last_comp_version is not None:
            self.header.last_comp_version = last_comp_version
        if boot_cpuid_phys is not None:
            self.header.boot_cpuid_phys = boot_cpuid_phys
        if self.header.version is None:
            raise Exception("DTB Version must be specified !")

        blob_entries = bytes()
        if self.entries:
            for entry in self.entries:
                blob_entries += pack('>QQ', entry['address'], entry['size'])
        blob_entries += pack('>QQ', 0, 0)
        blob_data_start = self.header.size + len(blob_entries)
        (blob_data, blob_strings, data_pos) = self.root_node.to_dtb('', blob_data_start, self.header.version)
        blob_data += pack('>I', DTB_END)
        self.header.size_dt_strings = len(blob_strings)
        self.header.size_dt_struct = len(blob_data)
        self.header.off_mem_rsvmap = self.header.size
        self.header.off_dt_struct = blob_data_start
        self.header.off_dt_strings = blob_data_start + len(blob_data)
        self.header.total_size = blob_data_start + len(blob_data) + len(blob_strings)
        blob_header = self.header.export()
        return blob_header + blob_entries + blob_data + blob_strings.encode('ascii')


def parse_dts(text, root_dir=''):
    """ Parse DTS text file and create FDT Object

    """
    ver = get_version_info(text)
    text = strip_comments(text)
    dts_lines = split_to_lines(text)
    fdt_obj = FDT()
    if 'version' in ver:
        fdt_obj.header.version = ver['version']
    if 'last_comp_version' in ver:
        fdt_obj.header.last_comp_version = ver['last_comp_version']
    if 'boot_cpuid_phys' in ver:
        fdt_obj.header.boot_cpuid_phys = ver['boot_cpuid_phys']
    # parse entries
    fdt_obj.entries = []
    for line in dts_lines:
        if line.endswith('{'):
            break
        if line.startswith('/memreserve/'):
            line = line.strip(';')
            line = line.split()
            if len(line) != 3 :
                raise Exception()
            fdt_obj.entries.append({'address': int(line[1], 0), 'size': int(line[2], 0)})
    # parse nodes
    curnode = None
    fdt_obj.root_node = None
    for line in dts_lines:
        if line.endswith('{'):
            # start node
            node_name = line.split()[0]
            new_node = Node(node_name)
            if fdt_obj.root_node is None:
                fdt_obj.root_node = new_node
            if curnode is not None:
                curnode.append(new_node)
            curnode = new_node
        elif line.endswith('}'):
            # end node
            if curnode is not None:
                curnode = curnode.parent
        else:
            # properties
            if line.find('=') == -1:
                prop_name = line
                prop_obj = Property(prop_name)
            else:
                line = line.split('=', maxsplit=1)
                prop_name = line[0].rstrip(' ')
                prop_value = line[1].lstrip(' ')
                if prop_value.startswith('<'):
                    prop_obj = PropWords(prop_name)
                    prop_value = prop_value.replace('<', '').replace('>', '')
                    for prop in prop_value.split():
                        if prop.startswith('0x'):
                            prop_obj.append(int(prop, 16))
                        elif prop.startswith('0b'):
                            prop_obj.append(int(prop, 2))
                        elif prop.startswith('0'):
                            prop_obj.append(int(prop, 8))
                        else:
                            prop_obj.append(int(prop))
                elif prop_value.startswith('['):
                    prop_obj = PropBytes(prop_name)
                    prop_value = prop_value.replace('[', '').replace(']', '')
                    for prop in prop_value.split():
                        prop_obj.append(int(prop, 16))
                elif prop_value.startswith('/incbin/'):
                    prop_value = prop_value.replace('/incbin/("', '').replace('")', '')
                    prop_value = prop_value.split(',')
                    file_path  = os.path.join(root_dir, prop_value[0].strip())
                    file_offset = int(prop_value.strip(), 0) if len(prop_value) > 1 else 0
                    file_size = int(prop_value.strip(), 0) if len(prop_value) > 2 else 0
                    if file_path is None or not os.path.exists(file_path):
                        raise Exception("File path doesn't exist: {}".format(file_path))
                    with open(file_path, "rb") as f:
                        f.seek(file_offset)
                        prop_data = f.read(file_size) if file_size > 0 else f.read()
                    prop_obj = PropIncBin(prop_name, prop_data, os.path.split(file_path)[1])
                elif prop_value.startswith('/plugin/'):
                    raise NotImplementedError("Not implemented property value: /plugin/")
                elif prop_value.startswith('/bits/'):
                    raise NotImplementedError("Not implemented property value: /bits/")
                else:
                    prop_obj = PropStrings(prop_name)
                    for prop in prop_value.split('",'):
                        prop = prop.replace('"', "")
                        prop = prop.strip()
                        prop_obj.append(prop)
            if curnode is not None:
                curnode.append(prop_obj)

    return fdt_obj


def parse_dtb(data, offset=0):
    """ Parse FDT Binary Blob and create FDT Object
    :param data: FDT Binary Blob as bytes or bytearray
    :param offset:
    :return FDT object
    """
    assert isinstance(data, (bytes, bytearray)), "Invalid argument type"

    from struct import unpack_from

    fdt_obj = FDT()
    # parse header
    fdt_obj.header = Header.parse(data)
    # parse entries
    index = fdt_obj.header.off_mem_rsvmap
    while True:
        entrie = dict(zip(('address', 'size'), unpack_from(">QQ", data, offset + index)))
        index += 16
        if entrie['address'] == 0 and entrie['size'] == 0:
            break
        fdt_obj.entries.append(entrie)
    # parse nodes
    current_node = None
    fdt_obj.root_node = None
    index = fdt_obj.header.off_dt_struct
    while True:
        if len(data) < (offset + index + 4):
            raise Exception("Index out of range !")
        tag = unpack_from(">I", data, offset + index)[0]
        index += 4
        if tag == DTB_BEGIN_NODE:
            node_name = extract_string(data, offset + index)
            index = ((index + len(node_name) + 4) & ~3)
            if not node_name: node_name = '/'
            new_node = Node(node_name)
            if fdt_obj.root_node is None:
                fdt_obj.root_node = new_node
            if current_node is not None:
                current_node.append(new_node)
            current_node = new_node
        elif tag == DTB_END_NODE:
            if current_node is not None:
                current_node = current_node.parent
        elif tag == DTB_PROP:
            prop_size, prop_string_pos, = unpack_from(">II", data, offset + index)
            prop_start = index + 8
            if fdt_obj.header.version < 16 and prop_size >= 8:
                prop_start = ((prop_start + 7) & ~0x7)
            prop_name = extract_string(data, fdt_obj.header.off_dt_strings + prop_string_pos)
            prop_raw_value = data[offset + prop_start : offset + prop_start + prop_size]
            index = prop_start + prop_size
            index = ((index + 3) & ~0x3)
            if current_node is not None:
                current_node.append(new_property(prop_name, prop_raw_value))
        elif tag == DTB_END:
            break
        else:
            raise Exception("Unknown Tag: {}".format(tag))

    return fdt_obj


def diff(fdt1, fdt2):
    """ Diff two flattened device tree objects
    :param fdt1: The object 1 of FDT
    :param fdt2: The object 2 of FDT
    :return: list of 3 objects (same in 1 and 2, specific for 1, specific for 2)
    """
    assert isinstance(fdt1, FDT), "Invalid argument type"
    assert isinstance(fdt2, FDT), "Invalid argument type"

    fdt_a = FDT(fdt1.header)
    fdt_b = FDT(fdt2.header)

    if fdt1.header.version is not None and fdt2.header.version is not None:
        fdt_same = FDT(fdt1.header if fdt1.header.version > fdt2.header.version else fdt2.header)
    else:
        fdt_same = FDT(fdt1.header)

    if fdt1.entries and fdt2.entries:
        for entry_a in fdt1.entries:
            for entry_b in fdt2.entries:
                if entry_a['address'] == entry_b['address'] and entry_a['size'] == entry_b['size']:
                    fdt_same.entries.append(entry_a)
                    break

    for entry_a in fdt1.entries:
        found = False
        for entry_s in fdt_same.entries:
            if entry_a['address'] == entry_s['address'] and entry_a['size'] == entry_s['size']:
                found = True
                break
        if not found:
            fdt_a.entries.append(entry_a)

    for entry_b in fdt2.entries:
        found = False
        for entry_s in fdt_same.entries:
            if entry_b['address'] == entry_s['address'] and entry_b['size'] == entry_s['size']:
                found = True
                break
        if not found:
            fdt_b.entries.append(entry_b)

    for path, nodes, props in fdt1.walk():
        try:
            rnode = fdt2.get_node(path)
        except:
            rnode = None

        for node_b in nodes:
            if rnode is None or rnode.get_subnode(node_b.name) is None:
                fdt_a.add_item(Node(node_b.name), path)
            else:
                fdt_same.add_item(Node(node_b.name), path)

        for prop_a in props:
            if rnode is not None and prop_a == rnode.get_property(prop_a.name):
                fdt_same.add_item(prop_a.copy(), path)
            else:
                fdt_a.add_item(prop_a.copy(), path)

    for path, nodes, props in fdt2.walk():
        try:
            rnode = fdt_same.get_node(path)
        except:
            rnode = None

        for node_b in nodes:
            if rnode is None or rnode.get_subnode(node_b.name) is None:
                fdt_b.add_item(Node(node_b.name), path)

        for prop_b in props:
            if rnode is None or prop_b != rnode.get_property(prop_b.name):
                fdt_b.add_item(prop_b.copy(), path)

    return fdt_same, fdt_a, fdt_b
