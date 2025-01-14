#!/usr/bin/env python
# Copyright (c) 2007 ActiveState Software Inc.
# See the file LICENSE.txt for licensing information.

"""
koXMLDatasetInfo ties together the use of koXMLTreeService and
XML Catalog/DTD support in koCatalog to supply data handlers for determining
valid elements/attributes for the current position in the tree.

All tree arguments are cElementTree elements and should be the root element
of an XMLDocument from koXMLTreeService.

Note: most of this logic moved out of koXMLCompletionBase.py in order to
allow testing outside of Komodo.
"""

import sys
import os
import logging

import koXMLTreeService
from koCatalog import CatalogResolver


log = logging.getLogger("koXMLDatasetInfo")



class EmptyDatasetHandler:
    def tagnames(self, tree, node=None):
        if node is None:
            node = tree.current
        if node is not None:
            tags = tree.tags.get(tree.namespace(node), {})
        else:
            tags = tree.tags.get("", {})
        return [t for t in tags.keys() if t]

    def attrs(self, tree, node=None):
        if node is None:
            node = tree.current
        attrs = {}
        nodes = [n for n in tree.nodes if n.tag.lower() == node.tag.lower()]
        # now, get all attributes from all the tags
        for n in nodes:
            attrs.update(n.attrib)
        return attrs.keys()

    def values(self, attrname, tree, node=None):
        return []

class DataSetHandler(EmptyDatasetHandler):
    def __init__(self, namespace, dataset):
        self.namespace = namespace
        self.dataset = dataset

    def getnamespace(self, tree):
        """ if we were created without a namespace (eg. doctype only) then
            use the top level namespace for the document we're handling
            don't save the namespace, as it could change from document
            to document.  """
        if not self.namespace and tree.root is not None:
            return tree.root.ns
        return self.namespace

    def tagnames(self, tree, node=None):
        namespace = self.getnamespace(tree)
        if node is None:
            node = tree.current
        if node is None:
            # get root elements
            return self.dataset.possible_children()
        orig_node = node
        while node is not None:
            #print "node [%s] ns [%s]" % (node.localName, tree.namespace(node))
            ns = tree.namespace(node)
            if node.localName and (not ns or ns.lower()==namespace.lower()):
                if self.dataset.element_info(node.localName):
                    return self.dataset.possible_children(node.localName)
            node = tree.parent(node)
        if self.dataset.element_info(orig_node.localName):
            return self.dataset.possible_children(orig_node.localName)
        return self.dataset.all_element_types()

    def attrs(self, tree, node=None):
        if node is None:
            node = tree.current
        return self.dataset.possible_attributes(node.localName)

    def values(self, attrname, tree, node=None):
        if node is None:
            node = tree.current
        return self.dataset.\
               possible_attribute_values(node.localName, attrname)

class DatasetHandlerService:
    handlers = {} # empty dataset handlers
    resolver = None
    def __init__(self):
        self._default_public_ids = {
            "HTML": "-//W3C//DTD HTML 5//EN",
            "AngularJS": "-//ANGULARJS//DTD HTML 5 NG//EN",
        }
        self._default_namespace_ids = {}
        self.defaultHandler = EmptyDatasetHandler()
        self.resolver = CatalogResolver()

    def setCatalogs(self, catalogs):
        self.resolver.resetCatalogs(catalogs)
        DatasetHandlerService.handlers = {}

    def getDefaultPublicId(self, lang, env):
        decl = self._default_public_ids.get(lang, None)
        if env:
            decl = env.get_pref("default%sDecl" % (lang,), decl)
        return decl

    def setDefaultPublicId(self, lang, public_id):
        self._default_public_ids[lang] = public_id

    def getDefaultNamespace(self, lang, env):
        namespace = self._default_namespace_ids.get(lang, None)
        if env:
            namespace = env.get_pref("default%sNamespace" % (lang,), namespace)
        return namespace

    def setDefaultNamespace(self, lang, namespace):
        self._default_namespace_ids[lang] = namespace

    def getDocumentHandler(self, publicId=None, systemId=None, namespace=None):
        try:
            if namespace:
                if publicId or systemId:
                    log.debug("getDocumentHandler: using all three, %s %s %s",
                              publicId, systemId, namespace)
                    return self.handlers[(publicId, systemId, namespace)]
                else:
                    log.debug("getDocumentHandler: namespace only, %s",
                              namespace)
                    return self.handlers[namespace]
            else:
                log.debug("getDocumentHandler: ids only, %s, %s",
                          publicId, systemId)
                return self.handlers[(publicId, systemId)]
        except KeyError:
            log.debug("getDocumentHandler: Failed, retrying with %s, %s, %s...",
                      publicId, systemId, namespace)
            dataset = self.resolver.getDataset(publicId, systemId, namespace)
            if not dataset:
                handler = EmptyDatasetHandler()
            else:
                handler = DataSetHandler(namespace, dataset)
                if namespace:
                    self.handlers[namespace] = handler
                    if publicId or systemId:
                        self.handlers[(publicId, systemId, namespace)] = handler
                if publicId or systemId:
                    self.handlers[(publicId, systemId)] = handler
            return handler

__datasetSvc = None
def getService():
    global __datasetSvc
    if not __datasetSvc:
        __datasetSvc = DatasetHandlerService()
    return __datasetSvc

def get_tree_handler(tree, node=None, default=None):
    # if we have a namespace, use it,  otherwise, fallback to the doctype
    namespace = None
    if node is None:
        node = tree.root
    if node is not None:
        namespace = tree.namespace(node)
    log.info("getting handler for (%s,%s,%s)"%(tree.publicId, tree.systemId, namespace))
    #print "getDocumentHandler (%s,%s,%s)"%(tree.publicId, tree.systemId, namespace)
    publicId = tree.publicId
    systemId = tree.systemId
    if not (publicId or systemId or namespace) and default:
        #print "using defaults %r" % (default,)
        publicId = default[0]
        systemId = default[1]
        namespace = default[2]
    return getService().getDocumentHandler(publicId, systemId, namespace)
    
if __name__ == "__main__":
    import sys, os
    # basic logging configuration
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    # set a format which is simpler for console use
    formatter = logging.Formatter('%(name)-12s: %(levelname)-8s %(message)s')
    # tell the handler to use this format
    console.setFormatter(formatter)
    # add the handler to the root logger
    logging.getLogger('').addHandler(console)

    # utility functions for testing, these are *SIMILAR* to codeintel lang_xml
    default_completion = { 'HTML': ('-//W3C//DTD XHTML 1.0 Strict//EN',
                              'http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd',
                              'http://www.w3.org/1999/xhtml') }
    
    def getDefaultCompletion(tree, node, lang):
        if lang=="XSLT":
            if node is not None and not tree.namespace(node):
                # do we have an output element, if so, figure out if we're html
                # cheap way to get the output element
                output = tree.tags.get('http://www.w3.org/1999/XSL/Transform', []).get('output')
                if output is not None:
                    lang = output.attrib.get('method').upper()
                    publicId = output.attrib.get('doctype-public')
                    systemId = output.attrib.get('doctype-system')
                    default_dataset_info = default_completion.get(lang)
                    if publicId or systemId:
                        default_dataset_info = (publicId, systemId, default_dataset_info[2])
                return default_dataset_info
            return None
        return default_completion.get(lang)
      
    def getValidTagNames(text, uri=None, lang=None):
        """getValidTagNames
        return a list of valid element names that can be inserted at the end
        of the text segment
        """
        tree = koXMLTreeService.getService().getTreeForURI(uri, text)
        default_dataset_info = getDefaultCompletion(tree, tree.current, lang)
        handlerclass = get_tree_handler(tree, tree.current, default_dataset_info)
        tagnames = handlerclass.tagnames(tree)
        if not tagnames:
            return None
        tagnames.sort()
        return tagnames
    
    def getOpenTagName(text, uri=None):
        """getOpenTagName
        return the current tag name
        """
        tree = koXMLTreeService.getService().getTreeForURI(uri, text)
        if tree.current is None: return None
        return tree.tagname(tree.current)
    
    def getValidAttributes(text, uri=None, lang=None):
        """getValidAttributes
        get the current tag, and return the attributes that are allowed in that
        element
        """
        tree = koXMLTreeService.getService().getTreeForURI(uri, text)
        if tree.current is None: return None
        already_supplied = tree.current.attrib.keys()
        handlerclass = get_tree_handler(tree, tree.current, default_completion.get(lang))
        attrs = handlerclass.attrs(tree)
        if not attrs:
            return None
        attrs = [name for name in attrs if name not in already_supplied]
        attrs.sort()
        return attrs
    
    def getValidAttributeValues(text, attr, uri=None, lang=None):
        """getValidAttributeValues
        get the current attribute, and return the values that are allowed in that
        attribute
        """
        tree = koXMLTreeService.getService().getTreeForURI(uri, text)
        if tree.current is None: return None
        handlerclass = get_tree_handler(tree, tree.current, default_completion.get(lang))
        values = handlerclass.values(attr, tree)
        if not values:
            return None
        values.sort()
        return values

    # configure catalogs to use
    basedir = os.path.dirname(os.path.dirname(os.getcwd()))
    catalogs = os.path.join(basedir, "test", "stuff", "xml")
    getService().setCatalogs([os.path.join(catalogs, "testcat.xml")])

    from cElementTree import Element
    tree = koXMLTreeService.XMLDocument()
    tree.root = tree.current = Element('')
    handlerclass = get_tree_handler(tree, tree.current)
    assert handlerclass != None, "no handler class for empty tree"

    xml = """<?xml version="1.0"?> 
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" version="1.0">
  <xsl:output method="html" indent="yes"/>
  <html> <
"""
    tags = getValidTagNames(xml, lang="XSLT")
    assert tags == ['body', 'head'], \
                "invalid output tags for stylesheet"

    xml = "<"
    assert getValidTagNames(xml) == None, "invalid children for html"

    xml = """<html>
    <body>
        <scr"""
    assert "script" in getValidTagNames(xml, lang="HTML"), "invalid children for body"

    html = """<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">"""
    # XXX this should only be html, have to figure out why area is there.
    tags = getValidTagNames(html)
    assert tags == ["html"], "invalid children for doc root"

    xml = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE window PUBLIC "-//MOZILLA//DTD XUL V1.0//EN" "http://www.mozilla.org/keymaster/gatekeeper/there.is.only.xul">
<window xmlns="http://www.mozilla.org/keymaster/gatekeeper/there.is.only.xul">
    <popupset id="editorTooltipSet">
        <popup type="tooltip" id="editorTooltip" flex="1">
            <description multiline="true" id="editorTooltip-tooltipText" class="tooltip-label" flex="1"/>
        </popup><
        <popup type="autocomplete" id="popupTextboxAutoComplete"/>
    </popupset>

"""
    tags = getValidTagNames(xml) 
    assert tags == ["popup"], "invalid children for popupset %r" % tags

    xml = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" lang="en">
"""
    # lets get the next valid element
    assert getValidTagNames(xml) == ['body', 'head'], "invalid children for html tag"

    xml ="""<
    
<?php
?>
"""
    tags = getValidTagNames(xml, lang="HTML")
    assert tags == ['html'], "invalid attributes for html tag"

    xml = """<html """
    attrs = getValidAttributes(xml, lang="HTML")
    assert attrs == ['dir', 'id', 'lang'], "invalid attributes for html tag"
    
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html """
    attrs = getValidAttributes(xml)
    assert attrs == ['dir', 'id', 'lang'], "invalid attributes for html tag"

    xml = """<?xml version="1.0"?> 
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" version="1.0">
  <xsl:output method="xml" indent="yes"/>
  <xsl:
  
  <xsl:template/>
"""
    assert getValidTagNames(xml) == ['attribute-set', 'decimal-format', 'import', 'include', 'key', 'namespace-alias', 'output', 'param', 'preserve-space', 'strip-space', 'template', 'variable'], \
                "invalid children tags for stylesheet"

    xml = """<?xml version="1.0"?> 
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" version="1.0">
  <xsl:output method="xml" indent="yes"/>
  <xsl:template"""
    assert getValidAttributes(xml) == ['match', 'mode', 'name', 'priority'], \
                "invalid attributes for template"

    xml = """<?xml version="1.0"?> 
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" version="1.0">
  <xsl:output method="xml" indent="yes"/>
  <xsl:"""
    assert getValidTagNames(xml) == ['attribute-set', 'decimal-format', 'import', 'include', 'key', 'namespace-alias', 'output', 'param', 'preserve-space', 'strip-space', 'template', 'variable'], \
                "invalid children for stylesheet"

    # test getting custom tags from the default namespace
    xml = """<?xml version="1.0"?> 
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" version="1.0">
  <xsl:output method="xml" indent="yes"/>
  <mycustomtag>
  <
  
  <xsl:template/>
"""
    assert getValidTagNames(xml) == ['mycustomtag'], \
                "invalid children for mycustomtag"

    xml = """<?xml version="1.0"?> 
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" version="1.0">
  <xsl:output method="xml" indent="yes"/><xsl:
  <xsl:template/>
</xsl:stylesheet>
"""
    assert getValidTagNames(xml) == ['attribute-set', 'decimal-format', 'import', 'include', 'key', 'namespace-alias', 'output', 'param', 'preserve-space', 'strip-space', 'template', 'variable'], \
                "invalid children for stylesheet"

    xml = """<?xml version="1.0"?> 
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" version="1.0">
  <xsl:output method="xml" indent="yes"/>

  <xsl:template>
  </xsl:template><xsl:

  <xsl:template>
  </xsl:template>
</xsl:stylesheet>
"""
    assert getValidTagNames(xml) == ['attribute-set', 'decimal-format', 'import', 'include', 'key', 'namespace-alias', 'output', 'param', 'preserve-space', 'strip-space', 'template', 'variable'], \
                "invalid children for stylesheet"

