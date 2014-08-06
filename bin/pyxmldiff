#!/usr/bin/python

import argparse

from pyxmldiff import xmldiff

DEFAULT_NAMESPACES = {
	"office": "urn:oasis:names:tc:opendocument:xmlns:office:1.0",
}

if __name__ == '__main__':
	ap = argparse.ArgumentParser()
	ap.add_argument("FILE1", type=argparse.FileType())
	ap.add_argument("FILE2", type=argparse.FileType())
	args = ap.parse_args()

	A = xmldiff.fromstring(args.FILE1.read())
	B = xmldiff.fromstring(args.FILE2.read())

	xmldiff.xmlDiff(A, B, namespaces=DEFAULT_NAMESPACES)
