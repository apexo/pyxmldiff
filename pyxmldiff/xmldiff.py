import sys
from hashlib import sha1

from . import fmt as _fmt

try:
	from lxml.etree import fromstring, _Element as Element
except ImportError:
	try:
		from xml.etree.cElementTree import fromstring, Element
	except ImportError:
		from xml.etree.ElementTree import fromstring, Element

__all__ = ["xmlDiff", "fromstring"]

_true = lambda node: True

TRANSLATE_CDATA = {
	ord('&'): '&amp',
	ord('<'): '&lt',
	ord('>'): '&gt',
}

TRANSLATE_ATTRIB = {
	ord('"'): '&quot;',
	ord('\n'): '&#10;',
}
TRANSLATE_ATTRIB.update(TRANSLATE_CDATA)

class NSMap(object):
	def __init__(self, nsmap):
		self.fwd = {}
		self.rev = {}
		self.nsid = 0
		self.a = [{}]
		self.b = [{}]
		self.used = set()
		for prefix, ns in nsmap.items():
			self.fwd[prefix] = ns
			self.rev[ns] = prefix

	def lookup(self, ns, el):
		prefix = self.rev.get(ns)
		if prefix is not None:
			return prefix

		if hasattr(el, "nsmap"):
			if ns in el.nsmap.values():
				self.used.add(ns)
				return next(key for (key, value) in el.nsmap.items() if value == ns)

	def add(self, ns):
		while u"ns%d" % self.nsid in self.fwd:
			self.nsid += 1
		prefix = u"ns%d" % self.nsid
		self.fwd[prefix] = ns
		self.rev[ns] = prefix
		self.nsid += 1
		return prefix

	def _targetState(self, el):
		if hasattr(el, "nsmap"):
			target = dict(self.fwd)
			for prefix, ns in el.nsmap.items():
				if ns in self.used:
					target[prefix] = ns
			return target
		return self.fwd

	def diffNsAttrs(self, a, b, push=True):
		ta = self._targetState(a)
		tb = self._targetState(b)
		ca = self.a[-1]
		cb = self.b[-1]
		da = dict((key, ta[key]) for key in ta if key not in ca or ta[key] != ca[key])
		db = dict((key, tb[key]) for key in tb if key not in cb or tb[key] != cb[key])

		for key in sorted(set(da) & set(db)):
			if da[key] == da[key]:
				yield u" ", key, da[key]
		for key in sorted(set(da) - set(db)):
			yield u"-", key, da[key]
		for key in sorted(set(da) & set(db)):
			if da[key] != db[key]:
				yield u"-", key, da[key]
				yield u"+", key, db[key]
		for key in sorted(set(db) - set(da)):
			yield u"+", key, da[key]

		if push:
			self.a.append(ta)
			self.b.append(tb)

	def popState(self):
		self.a.pop()
		self.b.pop()

	def nsAttrs(self, el, state, push=True):
		t = self._targetState(el)
		c = state[-1]
		d = dict((key, t[key]) for key in t if key not in c or t[key] != c[key])

		for key in d:
			yield key, d[key]

		if push:
			state.append(t)

def is_element(v):
	return isinstance(v, Element)

if sys.version_info.major > 2:
	escape_attrib = lambda v: v.translate(TRANSLATE_ATTRIB)
	escape_cdata = lambda v: v.translate(TRANSLATE_CDATA)
	encode = lambda v: v.encode("UTF-8")
	is_text = lambda v: isinstance(v, str)
else:
	def escape_attrib(v):
		if isinstance(v, unicode):
			return v.translate(TRANSLATE_ATTRIB)
		else:
			if "&" in v:
				v = v.replace("&", "&amp;")
			if "<" in v:
				v = v.replace("<", "&lt;")
			if ">" in v:
				v = v.replace(">", "&gt;")
			if "\"" in v:
				v = v.replace("\"", "&quot;")
			if "\n" in v:
				v = v.replace("\n", "&#10;")
			return v

	def escape_cdata(v):
		if isinstance(v, unicode):
			return v.translate(TRANSLATE_CDATA)
		else:
			if "&" in v:
				v = v.replace("&", "&amp;")
			if "<" in v:
				v = v.replace("<", "&lt;")
			if ">" in v:
				v = v.replace(">", "&gt;")
			return v

	import codecs
	encode = lambda v: codecs.utf_8_encode(v)[0]
	is_text = lambda v: isinstance(v, basestring)

def _elementKey(el):
	md = sha1(b"E" + encode(el.tag) + b"\0")
	if el.get("id") is not None:
		md.update(b"I" + encode(el.get("id")))
	elif el.get("full-path") is not None:
		md.update(b"F" + encode(el.get("full-path")))
	elif el.get("name") is not None:
		md.update(b"N" + encode(el.get("name")))
	return md.digest()

def _textKey(text):
	return sha1(b"T" + encode(text)).digest()

def _fmtAttr(name, value, el, nsmap):
	return u'%s="%s"' % (_fmtNsName(name, el, nsmap), escape_attrib(value))

def _fmtAttrs(el, nsmap, state, push, nsattrs=None):
	return (
		u"".join(u" " + _fmtNsAttr(key, value) for (key, value) in (nsmap.nsAttrs(el, state, push) if nsattrs is None else nsattrs)) +
		u"".join(u" " + _fmtAttr(attr, el.get(attr), el, nsmap) for attr in el.keys())
	)

def _fmtNsAttr(key, value):
	return u'xmlns:%s="%s"' % (key, escape_attrib(value))

def _wrapElement(fmt, prefix, el, nsmap, state, ns_attr=None):
	return fmt.subsection(u"<%s%s>" % (_fmtTag(el, nsmap), _fmtAttrs(el, nsmap, state, True, ns_attr)), prefix=prefix, tail=u"</%s>" % (_fmtTag(el, nsmap),), tailPrefix=prefix)

def _fmtNsName(nsname, el, nsmap):
	if nsname.startswith(u"{"):
		ns, sep, name = nsname[1:].rpartition(u"}")
		if not sep:
			raise ValueError(nsname)
		prefix = nsmap.lookup(ns, el)
		if prefix is None:
			prefix = nsmap.add(ns)
		return u"%s:%s" % (prefix, name)
	return nsname

def _fmtTag(el, nsmap):
	return _fmtNsName(el.tag, el, nsmap)

def _wrapElementDiff(fmt, a, b, nsmap):
	a_attr = set(a.keys())
	b_attr = set(b.keys())
	common_attr = a_attr & b_attr
	equal_attr = set(attr for attr in common_attr if a.get(attr) == b.get(attr))
	diff_attr = common_attr - equal_attr
	a_only_attr = a_attr - common_attr
	b_only_attr = b_attr - common_attr
	ns_attr = list(nsmap.diffNsAttrs(a, b))
	diff_ns_attr = any(prefix != U" " for (prefix, key, value) in ns_attr)

	if not diff_attr and not a_only_attr and not b_only_attr and not diff_ns_attr:
		return _wrapElement(fmt, u" ", a, nsmap, nsmap.a, [(key, value) for (prefix, key, value) in ns_attr]), []

	equal_attr_s = (
		u"".join(u" " + _fmtNsAttr(key, value) for (pref, key, value) in ns_attr if pref == u" ") +
		u"".join(u" " + _fmtAttr(attr, a.get(attr), a, nsmap) for attr in sorted(equal_attr))
	)

	delta = []
	for prefix, key, value in ns_attr:
		if prefix != u" ":
			delta.append(prefix, u"  " + _fmtNsAttr(key, value))
	for attr in sorted(diff_attr | a_only_attr | b_only_attr):
		if attr in (a_only_attr | diff_attr):
			delta.append((u"-", u"  " + _fmtAttr(attr, a.get(attr), a, nsmap)))
		if attr in (b_only_attr | diff_attr):
			delta.append((u"+", u"  " + _fmtAttr(attr, b.get(attr), b, nsmap)))

	delta[-1] = delta[-1][0], delta[-1][1] + u">"

	return fmt.subsection(u"<%s%s" % (_fmtTag(a, nsmap), equal_attr_s), prefix=u" ", tail=u"</%s>" % (_fmtTag(a, nsmap),)), delta

def _dumpText(fmt, prefix, node):
	fmt.write(escape_cdata(node), prefix=prefix)

def _dumpRecursiveElement(fmt, prefix, el, filter_, nsmap, state):
	if not len(el) and not el.text:
		if filter_(el):
			fmt.write(u"<%s%s/>" % (_fmtTag(el, nsmap), _fmtAttrs(el, nsmap, state, False)), prefix=prefix)
		return
	if not len(el):
		if filter_(el):
			fmt.write(u"<%s%s>%s</%s>" % (_fmtTag(el, nsmap), _fmtAttrs(el, nsmap, state, False), escape_cdata(el.text), _fmtTag(el, nsmap)), prefix=prefix)
		return
	al, bl = len(nsmap.a), len(nsmap.b)
	with _wrapElement(fmt, prefix, el, nsmap, state):
		for node in _children(el):
			_dumpRecursive(fmt, prefix, node, filter_, nsmap, state)
	state.pop()
	assert (al, bl) == (len(nsmap.a), len(nsmap.b))

def _dumpRecursive(fmt, prefix, node, filter_, nsmap, state):
	f = filter_(node)
	if f is False:
		pass
	elif is_element(node):
		_dumpRecursiveElement(fmt, prefix, node, _true if f else filter_, nsmap, state)
	elif is_text(node):
		if f:
			_dumpText(fmt, prefix, node)
	else:
		raise Exception("unsupported node type: %r" % (node,))

def _nodeKey(node):
	if is_element(node):
		return _elementKey(node)
	elif is_text(node):
		return _textKey(node)
	else:
		raise Exception("unsupported node type: %r" % (node,))

def _type(node):
	if is_element(node):
		return "element"
	elif is_text(node):
		return "text"
	else:
		raise Exception("unsupported node type: %r" % (node,))

def _children(element):
	if element.text:
		yield element.text
	for child in element:
		yield child
		if child.tail:
			yield child.tail

def _xmlDiffElementChildren(fmt, a, b, filter_, nsmap):
	aNodes = [(_nodeKey(node), node) for node in _children(a)]
	bNodes = [(_nodeKey(node), node) for node in _children(b)]

	# compute longest common subsequence
	# https://en.wikipedia.org/w/index.php?title=Longest_common_subsequence_problem&oldid=573748360#Computing_the_length_of_the_LCS
	state = [(0, ())]

	for j, (bKey, bNode) in enumerate(bNodes, 1):
		state.append((state[j-1][0], state[j-1][1] + ((None, bNode),)))

	for i, (aKey, aNode) in enumerate(aNodes):
		new_state = [(state[0][0], state[0][1] + ((aNode, None),))]
		for j, (bKey, bNode) in enumerate(bNodes, 1):
			if aKey == bKey:
				new_state.append((state[j-1][0] + 1, state[j-1][1] + ((aNode, bNode),)))
			else:
				if state[j][0] >= new_state[j - 1][0]:
					new_state.append((state[j][0], state[j][1] + ((aNode, None),)))
				else:
					new_state.append((new_state[j-1][0], new_state[j-1][1] + ((None, bNode),)))
		state = new_state

	for aNode, bNode in state[-1][1]:
		_xmlDiff(fmt, aNode, bNode, filter_, nsmap)

def _xmlDiff(fmt, a, b, filter_, nsmap):
	if a is None:
		if b is not None:
			_dumpRecursive(fmt, u"+", b, filter_, nsmap, nsmap.b)
		return
	elif b is None:
		_dumpRecursive(fmt, u"-", a, filter_, nsmap, nsmap.a)
		return

	if _type(a) != _type(b) or is_element(a) and a.tag != b.tag:
		_dumpRecursive(fmt, u"-", a, filter_, nsmap, nsmap.a)
		_dumpRecursive(fmt, u"+", b, filter_, nsmap, nsmap.b)
		return

	if is_text(a):
		if a != b:
			_dumpRecursive(fmt, u"-", a, filter_, nsmap, nsmap.a)
			_dumpRecursive(fmt, u"+", b, filter_, nsmap, nsmap.b)
		return

	if not is_element(a):
		raise Exception("unsupported node type: " + a.type)

	f = filter_(a)
	if f is False:
		return

	al, bl = len(nsmap.a), len(nsmap.b)
	subsection, delta = _wrapElementDiff(fmt, a, b, nsmap)
	with subsection:
		for prefix, line in delta:
			fmt.write(line, prefix=prefix)

		_xmlDiffElementChildren(fmt, a, b, _true if f else filter_, nsmap)
	nsmap.popState()
	assert (al, bl) == (len(nsmap.a), len(nsmap.b))

class Null(object):
	@classmethod
	def write(self, f):
		pass

def xmlDiff(a, b, fmt=None, filter_=_true, namespaces={}):
	# compute namespaces (on root element, for non-lxml), for lxml (where
	# elements have nsmap property) we remember which namespaces we
	# actually need for the output (via nsmap.used)
	nsmap = NSMap(namespaces)
	dummy = _fmt.Formatter(target=Null)
	_xmlDiff(dummy, a, b, filter_, nsmap)

	# throw an exception if the subsequent _xmlDiff tries to add a new namespace (shouldn't happen)
	nsmap.add = None

	# output diff via provided or default formatter
	fmt = fmt or _fmt.Formatter()
	_xmlDiff(fmt, a, b, filter_, nsmap)
