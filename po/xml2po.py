#!/usr/bin/python
# -*- coding: utf-8 -*-
import six

import sys
from os import listdir, path as ospath
import re
from xml.sax import make_parser
from xml.sax.handler import ContentHandler, property_lexical_handler
try:
	from _xmlplus.sax.saxlib import LexicalHandler
	no_comments = False
except ImportError:
	class LexicalHandler:
		def __init__(self):
			pass
	no_comments = True


class parseXML(ContentHandler, LexicalHandler):
	def __init__(self, attrlist):
		self.isPointsElement, self.isReboundsElement = 0, 0
		self.attrlist = attrlist
		self.last_comment = None
		self.ishex = re.compile(r'#[0-9a-fA-F]+\Z')

	def comment(self, comment):
		if "TRANSLATORS:" in comment:
			self.last_comment = comment

	def startElement(self, name, attrs):
		for x in ["text", "title", "menuTitle", "value", "caption", "description"]:
			try:
				k = six.ensure_str(attrs[x])
				if k.strip() != "" and not self.ishex.match(k):
					attrlist.add((k, self.last_comment))
					self.last_comment = None
			except KeyError:
				pass


parser = make_parser()

attrlist = set()

contentHandler = parseXML(attrlist)
parser.setContentHandler(contentHandler)
if not no_comments:
	parser.setProperty(property_lexical_handler, contentHandler)

for arg in sys.argv[1:]:
	if ospath.isdir(arg):
		for file in listdir(arg):
			if file.endswith(".xml"):
				parser.parse(ospath.join(arg, file))
	else:
		parser.parse(arg)

	attrlist = list(attrlist)
	attrlist.sort(key=lambda a: a[0])

	for (k, c) in attrlist:
		print()
		print('#: ' + arg)
		k.replace("\\n", "\"\n\"")
		if c:
			for l in c.split('\n'):  # noqa: E741
				print("#. ", l)
		print('msgid "' + six.ensure_str(k) + '"')
		print('msgstr ""')

	attrlist = set()
