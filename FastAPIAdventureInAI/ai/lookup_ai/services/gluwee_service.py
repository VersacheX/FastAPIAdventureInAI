"""Gluwee.com content extractor.

Provides a small extractor for Gluwee biography pages (e.g. /<name>/) that
returns a focused extraction of the "Height, Weight, & Physical Appearances"
section when present.
"""
from typing import Optional, Dict, Any
import re

from ai.services.http_service import fetch_html, _strip_html


async def extract_gluwee_physical_section(url: str) -> Optional[Dict[str, Any]]:
	"""Fetch the page at `url` and return the physical appearances section.

	Returns a dict with keys:
	- html: raw page HTML
	- section_title: detected section title (string)
	- section_html: raw HTML of the ul/list for the section
	- section_text: plaintext cleaned section content
	"""
	try:
		payload = await fetch_html(url)
		if not payload or not isinstance(payload, dict):
			print(f"[gluwee_service] fetch_html returned no payload for {url}")
			return None
		html = payload.get("html")
		if not html:
			print(f"[gluwee_service] no html in payload for {url}")
			return None

		out: Dict[str, Any] = {"html": html}

		matched_by = None

		# Try to find the section by id first (example page uses this id)
		m = re.search(
			r"<h[12][^>]*>\s*.*?<span[^>]*id=[\"']Height_Weight_Physical_Appearances[\"'][^>]*>.*?</span>.*?</h[12]>\s*(<ul[\s\S]*?</ul>)",
			html,
			re.I,
		)

		section_html = None
		section_title = "Height, Weight, & Physical Appearances"

		if m:
			section_html = m.group(1)
			matched_by = "id"
		else:
			# Fallback: find a heading that mentions Height and Weight and capture the following UL
			m2 = re.search(
				r"<h[12][^>]*>[\s\S]{0,200}?Height[\s\S]{0,40}?Weight[\s\S]*?</h[12]>\s*(<ul[\s\S]*?</ul>)",
				html,
				re.I,
			)
			if m2:
				section_html = m2.group(1)
				matched_by = "heading"
			else:
				# Final fallback: iterate all ULs and pick the one containing 'Height:' token
				for ul_match in re.finditer(r"(<ul[\s\S]*?</ul>)", html, re.I):
					ul_html = ul_match.group(1)
					if re.search(r"Height\s*:\s*", ul_html, re.I):
						section_html = ul_html
						matched_by = "ul_scan"
						break

		if not section_html:
			print(f"[gluwee_service] no physical section found for {url}")
			return None

		section_text = _strip_html(section_html).strip()
		# cap length
		if len(section_text) >2000:
			section_text = section_text[:2000] + "..."

		# Debug info about the sourced section
		try:
			preview = section_text.replace("\n", " ")[:500]
		except Exception:
			preview = ""
		print(f"[gluwee_service] sourced section for {url} matched_by={matched_by} len={len(section_text)} preview={preview!r}")

		# Provide standardized keys expected by describer: 'text' and optional 'sections'
		out.update({
			"section_title": section_title,
			"section_html": section_html,
			"section_text": section_text,
			"text": section_text,
			"sections": {section_title: section_text},
		})
		return out

	except Exception as e:
		print(f"[gluwee_service] extractor failed for {url}: {e}")
		return None


async def fetch_gluwee_physical(url: str) -> Optional[str]:
	"""Convenience wrapper returning only section_text or None."""
	try:
		res = await extract_gluwee_physical_section(url)
		if not res:
			return None
		return res.get("section_text")
	except Exception:
		return None
