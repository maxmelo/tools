#!/usr/bin/env python3

import math
import unicodedata
import html
import os
import subprocess
import shutil
import tempfile
import regex
import psutil
from titlecase import titlecase as pip_titlecase
import se


def word_count(xhtml: str) -> int:
	"""
	Get the word count from an XHTML string.

	INPUTS
	xhtml: A string of XHTML

	OUTPUTS
	The number of words in the XHTML string.
	"""

	# Remove HTML tags
	xhtml = regex.sub(r"<title>.+?</title>", " ", xhtml)
	xhtml = regex.sub(r"<.+?>", "", xhtml, flags=regex.DOTALL)

	# Replace some formatting characters
	xhtml = regex.sub(r"[…–—― ‘’“”\{\}\(\)]", " ", xhtml, flags=regex.IGNORECASE | regex.DOTALL)

	# Remove word-connecting dashes, apostrophes, commas, and slashes (and/or), they count as a word boundry but they shouldn't
	xhtml = regex.sub(r"[a-z0-9][\-\'\,\.\/][a-z0-9]", "aa", xhtml, flags=regex.IGNORECASE | regex.DOTALL)

	# Replace sequential spaces with one space
	xhtml = regex.sub(r"\s+", " ", xhtml, flags=regex.IGNORECASE | regex.DOTALL)

	# Get the word count
	return len(regex.findall(r"\b\w+\b", xhtml, flags=regex.IGNORECASE | regex.DOTALL))

def render_mathml_to_png(mathml: str, output_filename: str) -> None:
	"""
	Render a string of MathML into a transparent PNG file.

	INPUTS
	mathml: A string of MathML
	output_filename: A filename to store PNG output to

	OUTPUTS
	A string of XHTML with soft hyphens inserted in words. The output is not guaranteed to be pretty-printed.
	"""

	firefox_path = shutil.which("firefox")
	convert_path = shutil.which("convert")

	if firefox_path is None:
		raise se.MissingDependencyException("Couldn’t locate firefox. Is it installed?")

	if convert_path is None:
		raise se.MissingDependencyException("Couldn’t locate imagemagick. Is it installed?")

	if "firefox" in (p.name() for p in psutil.process_iter()):
		raise se.FirefoxRunningException("Firefox is required, but it’s currently running. Stop all instances of Firefox and try again.")

	with tempfile.NamedTemporaryFile(mode="w+") as mathml_temp_file:
		with tempfile.NamedTemporaryFile(mode="w+", suffix=".png") as png_temp_file:
			mathml_temp_file.write("<!doctype html><html><head><meta charset=\"utf-8\"><title>MathML fragment</title></head><body>{}</body></html>".format(mathml))
			mathml_temp_file.seek(0)

			subprocess.call([firefox_path, "-screenshot", png_temp_file.name, "file://{}".format(mathml_temp_file.name)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

			subprocess.call([convert_path, png_temp_file.name, "-fuzz", "10%", "-transparent", "white", "-trim", output_filename])

def replace_character_references(match_object) -> str:
	"""Replace most XML character references with literal characters.

	This function excludes &, >, and < (&amp;, &lt;, and &gt;), since
	un-escaping them would create an invalid document.
	"""

	entity = match_object.group(0).lower()

	retval = entity

	# Explicitly whitelist the three (nine) essential character references
	try:
		if entity in ["&gt;", "&lt;", "&amp;", "&#62;", "&#60;", "&#38;", "&#x3e;", "&#x3c;", "&#x26;"]:
			retval = entity
		# Convert base 16 references
		elif entity.startswith("&#x"):
			retval = chr(int(entity[3:-1], 16))
		# Convert base 10 references
		elif entity.startswith("&#"):
			retval = chr(int(entity[2:-1]))
		# Convert named references
		else:
			retval = html.entities.html5[entity[1:]]
	except (ValueError, KeyError):
		pass

	return retval

def format_xhtml(xhtml: str, single_lines: bool = False, is_metadata_file: bool = False, is_endnotes_file: bool = False) -> str:
	"""
	Render a string of MathML into a transparent PNG file.

	INPUTS
	mathml: A string of MathML
	output_filename: A filename to store PNG output to

	OUTPUTS
	A string of XHTML with soft hyphens inserted in words. The output is not guaranteed to be pretty-printed.
	"""

	xmllint_path = shutil.which("xmllint")

	if xmllint_path is None:
		se.print_error("Couldn’t locate xmllint. Is it installed?")
		return se.MissingDependencyException.code

	env = os.environ.copy()
	env["XMLLINT_INDENT"] = "\t"

	if single_lines:
		xhtml = xhtml.replace("\n", " ")
		xhtml = regex.sub(r"\s+", " ", xhtml)

	# Epub3 doesn't allow named entities, so convert them to their unicode equivalents
	# But, don't unescape the content.opf long-description accidentally
	if not is_metadata_file:
		xhtml = regex.sub(r"&#?\w+;", replace_character_references, xhtml)

	# Remove unnecessary doctypes which can cause xmllint to hang
	xhtml = regex.sub(r"<!DOCTYPE[^>]+?>", "", xhtml, flags=regex.DOTALL)

	# Canonicalize XHTML
	result = subprocess.run([xmllint_path, "--c14n", "-"], input=xhtml.encode(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
	xhtml = result.stdout.decode()
	try:
		error = result.stderr.decode().strip()

		if error:
			raise se.InvalidXhtmlException("Couldn't parse file; files must be in XHTML format, which is not the same as HTML. xmllint says:\n{}".format(error.replace("-:", "Line ")))
	except Exception:
	 	raise se.InvalidEncodingException("Invalid encoding; UTF-8 expected")

	# Add the XML header that xmllint stripped during c14n
	xhtml = "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n" + xhtml

	# Pretty-print XML
	xhtml = subprocess.run([xmllint_path, "--format", "-"], input=xhtml.encode(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env).stdout.decode()

	# Remove white space between some tags
	xhtml = regex.sub(r"<p([^>]*?)>\s+([^<\s])", "<p\\1>\\2", xhtml, flags=regex.DOTALL)
	xhtml = regex.sub(r"([^>\s])\s+</p>", "\\1</p>", xhtml, flags=regex.DOTALL)

	# xmllint has problems with removing spacing between some inline HTML5 elements. Try to fix those problems here.
	xhtml = regex.sub(r"</(abbr|cite|i|span)><(abbr|cite|i|span)", "</\\1> <\\2", xhtml)

	# Try to fix inline elements directly followed by an <a> tag, unless that <a> tag is a noteref.
	xhtml = regex.sub(r"</(abbr|cite|i|span)><(a(?! href=\"[^\"]+?\" id=\"noteref\-))", "</\\1> <\\2", xhtml)

	# Two sequential inline elements, when they are the only children of a block, are indented. But this messes up spacing if the 2nd element is a noteref.
	xhtml = regex.sub(r"</(abbr|cite|i|span)>\s+<(a href=\"[^\"]+?\" id=\"noteref\-)", "</\\1><\\2", xhtml, flags=regex.DOTALL)

	# Try to fix <cite> tags running next to referrer <a> tags.
	if is_endnotes_file:
		xhtml = regex.sub(r"</cite>(<a href=\"[^\"]+?\" epub:type=\"se:referrer\")", "</cite> \\1", xhtml)

	return xhtml

def remove_tags(text: str) -> str:
	"""
	Remove all HTML tags from a string.

	INPUTS
	text: Text that may have HTML tags

	OUTPUTS
	A string with all HTML tags removed
	"""

	return regex.sub(r"</?([a-z]+)[^>]*?>", "", text, flags=regex.DOTALL)

def ordinal(number: str) -> str:
	"""
	Given an string representing an integer, return a string of the integer followed by its ordinal, like "nd" or "rd".

	INPUTS
	number: A string representing an integer like "1" or "2"

	OUTPUTS
	A string of the integer followed by its ordinal, like "1st" or "2nd"
	"""

	number = int(number)
	return "%d%s" % (number, "tsnrhtdd"[(math.floor(number / 10) % 10 != 1) * (number % 10 < 4) * number % 10::4])

def titlecase(text: str) -> str:
	"""
	Titlecase a string according to SE house style.

	INPUTS
	text: The string to titlecase

	OUTPUTS
	A titlecased version of the input string
	"""

	text = pip_titlecase(text)

	# We make some additional adjustments here

	# Lowercase HTML tags that titlecase might have screwed up. We just lowercase the entire contents of the tag, including attributes,
	# since they're typically lowercased anyway. (Except for things like `alt`, but we won't be titlecasing images!)
	text = regex.sub(r"<(/?)([^>]+?)>", lambda result: "<" + result.group(1) + result.group(2).lower() + ">", text)

	# Lowercase leading "d', as in "Marie d'Elle"
	text = regex.sub(r"\bD’([A-Z]+?)", "d’\\1", text)

	# Lowercase "and", even if preceded by punctuation
	text = regex.sub(r"([^a-zA-Z]) (And|Or)\b", lambda result: result.group(1) + " " + result.group(2).lower(), text)

	# pip_titlecase capitalizes *all* prepositions preceded by parenthesis; we only want to capitalize ones that *aren't the first word of a subtitle*
	# OK: From Sergeant Bulmer (of the Detective Police) to Mr. Pendril
	# OK: Three Men in a Boat (To Say Nothing of the Dog)
	text = regex.sub(r"\((For|Of|To)(.*?)\)(.+?)", lambda result: "(" + result.group(1).lower() + result.group(2) + ")" + result.group(3), text)

	# Lowercase "and", if followed by a word-joiner
	regex_string = r"\bAnd{}".format(se.WORD_JOINER)
	text = regex.sub(regex_string, "and{}".format(se.WORD_JOINER), text)

	# Lowercase "in", if followed by a semicolon (but not words like "inheritance")
	text = regex.sub(r"\b; In\b", "; in", text)

	# Lowercase "from", "with", as long as they're not the first word and not preceded by a parenthesis
	text = regex.sub(r"(?<!^)(?<!\()\b(From|With)\b", lambda result: result.group(1).lower(), text)

	# Capitalise the first word after an opening quote or italicisation that signifies a work
	text = regex.sub(r"(‘|“|<i.*?epub:type=\".*?se:.*?\".*?>)([a-z])", lambda result: result.group(1) + result.group(2).upper(), text)

	# Lowercase "the" if preceded by "vs."
	text = regex.sub(r"(?:vs\.) The\b", "vs. the", text)

	# Lowercase "de", "von", "van", "le", as in "Charles de Gaulle", "Werner von Braun", etc., and if not the first word and not preceded by an &ldquo;
	text = regex.sub(r"(?<!^|“)\b(De|Von|Van|Le)\b", lambda result: result.group(1).lower(), text)

	# Uppercase word following "Or,", since it is probably a subtitle
	text = regex.sub(r"\bOr, ([a-z])", lambda result: "Or, " + result.group(1).upper(), text)

	# Fix html entities
	text = text.replace("&Amp;", "&amp;")

	# Lowercase etc.
	text = text.replace("Etc.", "etc.")

	return text

def make_url_safe(text: str) -> str:
	"""
	Return a URL-safe version of the input. For example, the string "Mother's Day" becomes "mothers-day".

	INPUTS
	text: A string to make URL-safe

	OUTPUTS
	A URL-safe version of the input string
	"""

	# 1. Convert accented characters to unaccented characters
	text = regex.sub(r"\p{M}", "", unicodedata.normalize("NFKD", text))

	# 2. Trim
	text = text.strip()

	# 3. Convert title to lowercase
	text = text.lower()

	# 4. Remove apostrophes
	text = regex.sub(r"['‘’]", "", text)

	# 5. Convert any non-digit, non-letter character to a space
	text = regex.sub(r"[^0-9a-z]", " ", text, flags=regex.IGNORECASE)

	# 6. Convert any instance of one or more space to a dash
	text = regex.sub(r"\s+", "-", text)

	# 7. Remove trailing dashes
	text = regex.sub(r"\-+$", "", text)

	return text
