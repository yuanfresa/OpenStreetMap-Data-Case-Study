#!/usr/bin/env python
# -*- coding: utf-8 -*-

import xml.etree.ElementTree as ET  # Use cElementTree or lxml if too slow
import re
import csv
import codecs

def get_element(osm_file, tags=('node', 'way', 'relation')):
    """Yield element if it is the right type of tag

    Reference:
    http://stackoverflow.com/questions/3095434/inserting-newlines-in-xml-file-generated-via-xml-etree-elementtree-in-python
    """
    context = iter(ET.iterparse(osm_file, events=('start', 'end')))
    _, root = next(context)
    for event, elem in context:
        if event == 'end' and elem.tag in tags:
            yield elem
            root.clear()

def sample_osm(FILE, SAMPLE_FILE, k):
	""" 
	param k: take every k-th top level element
	"""
	
	with open(SAMPLE_FILE, 'wb') as output:
		output.write('<?xml version="1.0" encoding="UTF-8"?>\n')
		output.write('<osm>\n  ')

	# Write every kth top level element
	for i, element in enumerate(get_element(FILE)):
	    if i % k == 0:
	        output.write(ET.tostring(element, encoding='utf-8'))

	output.write('</osm>')

LOWER_COLON = re.compile(r'^([a-z]|_)+:([a-z]|_)+')
PROBLEMCHARS = re.compile(r'[=\+/&<>;\'"\?%#$@\,\. \t\r\n]')


# Make sure the fields order in the csvs matches the column order in the sql table schema
#'id', 'lat', 'lon', 'user', 'uid', 'version', 'changeset', 'timestamp'
NODE_FIELDS = ['id', 'lat', 'lon', 'changeset', 'timestamp', 'version', 'uid', 'user']
NODE_FIELDS_NOUSR = ['id', 'lat', 'lon', 'changeset', 'timestamp', 'version']
NODE_TAGS_FIELDS = ['id', 'key', 'value', 'type']
WAY_FIELDS = ['id', 'user', 'uid', 'version', 'changeset', 'timestamp']
WAY_TAGS_FIELDS = ['id', 'key', 'value', 'type']
WAY_NODES_FIELDS = ['id', 'node_id', 'position']

def shape_element(element, node_attr_fields=NODE_FIELDS, way_attr_fields=WAY_FIELDS,
                  problem_chars=PROBLEMCHARS, default_tag_type='regular'):
    """Clean and shape node or way XML element to Python dict"""

    node_attribs = {}
    way_attribs = {}
    way_nodes = []
    tags = []  # Handle secondary tags the same way for both node and way elements

    if element.tag == 'node':
        # IF 'uid' or 'user' not in the node attribute
        try:
            for node_attrb in node_attr_fields:
                node_attribs[node_attrb] = element.attrib[node_attrb];
        except KeyError, e:
            for node_attrb in NODE_FIELDS_NOUSR:
                node_attribs[node_attrb] = element.attrib[node_attrb];
        if node_attribs['id'] == '935182740':
            print(node_attribs['id'])
                
        for tag in element.iter('tag'): #several tags
            node_tags = {}
            if not problem_chars.match(tag.attrib['k']):
                node_tags['id']=element.attrib['id']
                node_tags['value']=tag.attrib['v']
                if LOWER_COLON.search(tag.attrib['k']):
                    node_tags['key']=tag.attrib['k'].split(":",1)[1]
                    node_tags['type']=tag.attrib['k'].split(":",1)[0]
                else:
                    node_tags['key']=tag.attrib['k']
                    node_tags['type']=default_tag_type
                
                if node_tags['key']=='postcode':
                    node_tags['value'] = transfer_postcode(node_tags['value'])
                
                tags.append(node_tags)
        
        return {'node': node_attribs, 'node_tags': tags}

    elif element.tag == 'way':
        
        for way_attrb in way_attr_fields:
            way_attribs[way_attrb] = element.attrib[way_attrb];
        
        way_node = {}
        
        count = 0
        for nd in element.iter("nd"):
            way_nodes.append({'id': element.attrib['id'],
                              'node_id': nd.attrib['ref'],
                              'position': count})
            count += 1        
            
        
        for tag in element.iter('tag'): #several tags
            way_tags = {}
            if not problem_chars.match(tag.attrib['k']):                
                way_tags['id']=element.attrib['id']
                way_tags['value']=tag.attrib['v']
                if LOWER_COLON.match(tag.attrib['k']):
                    way_tags['key']=tag.attrib['k'].split(":",1)[1]
                    way_tags['type']=tag.attrib['k'].split(":",1)[0]
                else:
                    way_tags['key']=tag.attrib['k']
                    way_tags['type']=default_tag_type
                
                if way_tags['key']=='postcode':
                    way_tags['value'] = transfer_postcode(way_tags['value'])                   
                    
                tags.append(way_tags)
              
        
        return {'way': way_attribs, 'way_nodes': way_nodes, 'way_tags': tags}

def transfer_postcode(postcode):
    """Transform postcode to correct format.

    :param postcode:
    :return:

    >>> transfer_postcode("11619")
    '116 19'
    >>> transfer_postcode("116 19")
    '116 19'
    """
    match = re.search(r"(\d{3})\s*(\d{2})", postcode)
    if match:
        return match.group(1) + " " + match.group(2)


class UnicodeDictWriter(csv.DictWriter, object):
    """Extend csv.DictWriter to handle Unicode input"""

    def writerow(self, row):
        super(UnicodeDictWriter, self).writerow({
            k: (v.encode('ISO-8859-1','ignore') if isinstance(v, unicode) else v) for k, v in row.iteritems()
        })

    def writerows(self, rows):
        for row in rows:
            self.writerow(row)

def process_map(file_in):
    """Iteratively process each XML element and write to csv(s)"""

    with codecs.open(NODES_PATH, 'wb') as nodes_file, \
         codecs.open(NODE_TAGS_PATH, 'wb') as nodes_tags_file, \
         codecs.open(WAYS_PATH, 'wb') as ways_file, \
        codecs.open(WAY_NODES_PATH, 'wb') as way_nodes_file, \
         codecs.open(WAY_TAGS_PATH, 'wb') as way_tags_file:

        nodes_writer = UnicodeDictWriter(nodes_file, NODE_FIELDS)
        node_tags_writer = UnicodeDictWriter(nodes_tags_file, NODE_TAGS_FIELDS)
        ways_writer = UnicodeDictWriter(ways_file, WAY_FIELDS)
        way_nodes_writer = UnicodeDictWriter(way_nodes_file, WAY_NODES_FIELDS)
        way_tags_writer = UnicodeDictWriter(way_tags_file, WAY_TAGS_FIELDS)

        nodes_writer.writeheader()
        node_tags_writer.writeheader()
        ways_writer.writeheader()
        way_nodes_writer.writeheader()
        way_tags_writer.writeheader()


        for element in get_element(file_in, tags=('node', 'way')):
            el = shape_element(element)
            if el:

                if element.tag == 'node':
                    nodes_writer.writerow(el['node'])
                    node_tags_writer.writerows(el['node_tags'])
                elif element.tag == 'way':
                    ways_writer.writerow(el['way'])
                    way_nodes_writer.writerows(el['way_nodes'])
                    way_tags_writer.writerows(el['way_tags'])


if __name__ == '__main__':
    OSM_FILE = "stockholm_sweden.osm"  
	SAMPLE_FILE = "sample.osm"

	#extract sample osm file
	#sample_osm(OSM_FILE, SAMPLE_FILE, 400)
	
	#prepare csv files
	process_map(OSM_FILE)