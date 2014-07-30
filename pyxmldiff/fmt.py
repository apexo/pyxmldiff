import sys

class SubSection(object):
	def __init__(self, formatter, heading, indent, prefix=None, tail=None, tailPrefix=None):
		self.formatter = formatter
		self.heading = heading
		self.indent = indent
		self.prefix = prefix
		self.tail = tail
		self.tailPrefix = tailPrefix

	def __enter__(self):
		if self.heading is not None:
			self.formatter.write(self.heading, conditional=True, prefix=self.prefix)
			self._conditional = self.formatter.conditional[-1]
		self._saved_indent = self.formatter.indent
		self.formatter.indent += self.indent
		return self.formatter

	def __exit__(self, *args):
		self.formatter.indent = self._saved_indent
		if self.heading is not None and self.formatter.conditional and self.formatter.conditional[-1] is self._conditional:
			self.formatter.conditional.pop()
		else:
			if self.tail is not None:
				self.formatter.write(self.tail, prefix=self.tailPrefix)
			if not self.formatter.indent:
				self.formatter._pendingNewLine = True

class Formatter(object):
	def __init__(self, indent="  ", target=sys.stdout, newline="\n"):
		self._pendingNewLine = False
		self.indent = ""
		self._default_indent = indent
		self.data = []
		self.conditional = []
		self.target = target
		self.newline = newline

	def subsection(self, heading=None, indent=None, **kw):
		return SubSection(self, heading, self._default_indent if indent is None else indent, **kw)

	def write(self, msg, conditional=False, prefix=None):
		if not conditional and self._pendingNewLine:
			self.data.append(("",))
			self._pendingNewLine = False
		value = (prefix or " ") + self.indent + msg
		if conditional:
			self.conditional.append(value)
		else:
			if self.conditional:
				for line in self.conditional:
					self.target.write(line + self.newline)
				del self.conditional[:]
			self.target.write(value + self.newline)
