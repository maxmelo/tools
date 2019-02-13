#!/usr/bin/env python3

import subprocess
import shutil
import regex
import se

def format_inkscape_svg(filename: str):
	with open(filename, "r+") as file:
		svg = file.read()

		# Time to clean up Inkscape's mess
		svg = regex.sub(r"id=\"[^\"]+?\"", "", svg)
		svg = regex.sub(r"<metadata[^>]*?>.*?</metadata>", "", svg, flags=regex.DOTALL)
		svg = regex.sub(r"<defs[^>]*?/>", "", svg)
		svg = regex.sub(r"xmlns:(dc|cc|rdf)=\"[^\"]*?\"", "", svg)

		# Inkscape includes CSS even though we've removed font information
		svg = regex.sub(r" style=\".*?\"", "", svg)

		file.seek(0)
		file.write(svg)
		file.truncate()

	se.formatting.format_xhtml_file(filename)

def remove_image_metadata(filename: str) -> None:
	exiftool_path = shutil.which("exiftool")

	if exiftool_path is None:
		raise se.MissingDependencyException("Couldn’t locate exiftool. Is it installed?")

	subprocess.run([exiftool_path, "-overwrite_original", "-all=", filename], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
