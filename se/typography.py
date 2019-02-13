#!/usr/bin/env python3

import regex
from hyphen import Hyphenator
from hyphen.dictools import list_installed
from bs4 import BeautifulSoup
import se

def hyphenate_file(filename: str, language: str, ignore_h_tags: bool = False) -> None:
	"""
	Add soft hyphens to an XHTML file.

	INPUTS
	filename: A filename containing well-formed XHTML.
	language: An ISO language code, like en-US, or None to auto-detect based on XHTML input
	ignore_h_tags: True to not hyphenate within <h1-6> tags

	OUTPUTS
	None.
	"""
	with open(filename, "r+") as file:
		xhtml = file.read()

		processed_xhtml = se.typography.hyphenate(xhtml, language, ignore_h_tags)

		if processed_xhtml != xhtml:
			file.seek(0)
			file.write(processed_xhtml)
			file.truncate()

def hyphenate(xhtml: str, language: str, ignore_h_tags: bool = False) -> str:
	"""
	Add soft hyphens to a string of XHTML.

	INPUTS
	xhtml: A string of XHTML
	language: An ISO language code, like en-US, or None to auto-detect based on XHTML input
	ignore_h_tags: True to not hyphenate within <h1-6> tags

	OUTPUTS
	A string of XHTML with soft hyphens inserted in words. The output is not guaranteed to be pretty-printed.
	"""

	hyphenators = {}
	soup = BeautifulSoup(xhtml, "lxml")

	if language is None:
		try:
			language = soup.html["xml:lang"]
		except Exception:
			try:
				language = soup.html["lang"]
			except Exception:
				raise se.InvalidLanguageException("No `xml:lang` or `lang` attribute on root <html> element; couldn’t guess file language.")

	try:
		language = language.replace("-", "_")
		if language not in hyphenators:
			hyphenators[language] = Hyphenator(language)
	except Exception:
		raise se.MissingDependencyException("Hyphenator for language \"{}\" not available.\nInstalled hyphenators: {}".format(language, list_installed()))

	text = str(soup.body)
	result = text
	word = ""
	in_tag = False
	tag_name = ""
	reading_tag_name = False
	in_h_tag = False
	pos = 1
	h_opening_tag_pattern = regex.compile("^h[1-6]$")
	h_closing_tag_pattern = regex.compile("^/h[1-6]$")

	# The general idea here is to read the whole contents of the <body> tag character by character.
	# If we hit a <, we ignore the contents until we hit the next >.
	# Otherwise, we consider a word to be an unbroken sequence of alphanumeric characters.
	# We can't just split at whitespace because HTML tags can contain whitespace (attributes for example)
	for char in text:
		process = False

		if char == "<":
			process = True
			in_tag = True
			reading_tag_name = True
			tag_name = ""
		elif in_tag and char == ">":
			in_tag = False
			reading_tag_name = False
			word = ""
		elif in_tag and char == " ":
			reading_tag_name = False
		elif in_tag and reading_tag_name:
			tag_name = tag_name + char
		elif not in_tag and char.isalnum():
			word = word + char
		elif not in_tag:
			process = True

		# Do we ignore <h1-6> tags?
		if not reading_tag_name and h_opening_tag_pattern.match(tag_name):
			in_h_tag = True

		if not reading_tag_name and h_closing_tag_pattern.match(tag_name):
			in_h_tag = False

		if ignore_h_tags and in_h_tag:
			process = False

		if process:
			if word != "":
				new_word = word

				# 100 is the hard coded max word length in the hyphenator module
				# Check here to avoid an error
				if len(word) < 100:
					syllables = hyphenators[language].syllables(word)

					if syllables:
						new_word = "\u00AD".join(syllables)

				result = result[:pos - len(word) - 1] + new_word + char + result[pos:]
				pos = pos + len(new_word) - len(word)
			word = ""

		pos = pos + 1

	xhtml = regex.sub(r"<body.+<\/body>", "", xhtml, flags=regex.DOTALL)
	xhtml = xhtml.replace("</head>", "</head>\n\t" + result)

	return xhtml

def guess_quoting_style(xhtml: str) -> str:
	"""
	Guess whether the passed XHTML quotation is British or American style.

	INPUTS
	xhtml: A string of XHTML

	OUTPUTS
	A string containing one of these three values: "british", "american", or "unsure"
	"""

	# Want to discover the first quote type after a <p> tag. Doesn't have to be
	# directly after.

	# Count pattern matches for each quote style (disregard matches where the
	# capturing group contains opposite quote style).

	# Quote style percentage above the threshold is returned.
	threshold = 80

	ldq_pattern = regex.compile(r"\t*<p>(.*?)“")
	lsq_pattern = regex.compile(r"\t*<p>(.*?)‘")

	lsq_count = len([m for m in lsq_pattern.findall(xhtml) if m.count("“") == 0])
	ldq_count = len([m for m in ldq_pattern.findall(xhtml) if m.count("‘") == 0])

	detected_style = "unsure"
	american_percentage = 0

	try:
		american_percentage = (ldq_count / (ldq_count + lsq_count) * 100)
	except ZeroDivisionError:
		pass

	if american_percentage >= threshold:
		detected_style = "american"
	elif 100 - american_percentage >= threshold:
		detected_style = "british"

	return detected_style

def convert_british_to_american(xhtml: str) -> str:
	"""
	Attempt to convert a string of XHTML from British-style quotation to American-style quotation.

	INPUTS
	xhtml: A string of XHTML

	OUTPUTS
	The XHTML with British-style quotation converted to American style
	"""
	xhtml = regex.sub(r"“", r"<ldq>", xhtml)
	xhtml = regex.sub(r"”", r"<rdq>", xhtml)
	xhtml = regex.sub(r"‘", r"<lsq>", xhtml)
	xhtml = regex.sub(r"<rdq>⁠ ’(\s+)", r"<rdq> <rsq>\1", xhtml)
	xhtml = regex.sub(r"<rdq>⁠ ’</", r"<rdq> <rsq></", xhtml)
	xhtml = regex.sub(r"([\.\,\!\?\…\:\;])’", r"\1<rsq>", xhtml)
	xhtml = regex.sub(r"—’(\s+)", r"—<rsq>\1", xhtml)
	xhtml = regex.sub(r"—’</", r"—<rsq></", xhtml)
	xhtml = regex.sub(r"([a-z])’([a-z])", r"\1<ap>\2", xhtml)
	xhtml = regex.sub(r"(\s+)’([a-z])", r"\1<ap>\2", xhtml)
	xhtml = regex.sub(r"<ldq>", r"‘", xhtml)
	xhtml = regex.sub(r"<rdq>", r"’", xhtml)
	xhtml = regex.sub(r"<lsq>", r"“", xhtml)
	xhtml = regex.sub(r"<rsq>", r"”", xhtml)
	xhtml = regex.sub(r"<ap>", r"’", xhtml)

	# Correct some common errors
	xhtml = regex.sub(r"’ ’", r"’ ”", xhtml)
	xhtml = regex.sub(r"“([^‘”]+?[^s])’([!\?:;\)\s])", r"“\1”\2", xhtml)
	xhtml = regex.sub(r"“([^‘”]+?)’([!\?:;\)])", r"“\1”\2", xhtml)

	return xhtml
