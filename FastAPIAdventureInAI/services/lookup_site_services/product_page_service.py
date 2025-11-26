"""Product page extractor service.

Provides `extract_product_page(url)` which returns a best-effort product
extraction: raw HTML and a concise description/snippet (price if found).
This was refactored out of `extractor_factory.py` to keep services modular.
"""
from typing import Optional, Dict, Any
import re
from services.http_service import fetch_html, _strip_html
import json


async def extract_product_page(url: str) -> Optional[Dict[str, Any]]:
	"""Basic product page extractor: returns title, price (if found) and description

	Returns a dict: { 'html': <raw html>, 'text': <extracted summary> }
	"""
	try:
		payload = await fetch_html(url)
		if not payload:
			return None
		html = payload.get('html')
		if not html:
			return None

		# attempt to get a nice title
		title = None
		m = re.search(r'<meta\s+property="og:title"\s+content="([^"]+)"', html, re.I)
		if not m:
			m = re.search(r'<meta\s+name="twitter:title"\s+content="([^"]+)"', html, re.I)
		if not m:
			m = re.search(r'<title>(.*?)</title>', html, re.I | re.S)
		if m:
			title = re.sub(r"\s+", " ", m.group(1)).strip()

		# description
		desc = None
		m = re.search(r'<meta\s+property="og:description"\s+content="([^"]+)"', html, re.I)
		if not m:
			m = re.search(r'<meta\s+name="description"\s+content="([^"]+)"', html, re.I)
		if m:
			desc = re.sub(r"\s+", " ", m.group(1)).strip()

		# price patterns - common currencies
		price = None
		# try schema.org itemprop or meta
		m = re.search(r'itemprop="price"\s+content="([^"]+)"', html, re.I)
		if m:
			price = m.group(1).strip()
		if not price:
			m = re.search(r'<meta\s+property="product:price:amount"\s+content="([^"]+)"', html, re.I)
			if m:
				price = m.group(1).strip()
		if not price:
			# match common currency symbols: $, € , £ using unicode escapes
			m = re.search(r'([\$\u20AC\u00A3]\s?\d[\d,]*\.?\d{0,2})', html)
			if m:
				price = m.group(1).strip()

		# Prefer explicit description metadata. If not found, try JSON-LD Product
		# objects. As a last resort, fall back to a short snippet of the page body.
		if not desc:
			for jl in re.finditer(r'<script[^>]*type=[\"\']application/ld\+json[\"\'][^>]*>(.*?)</script>', html, re.I | re.S):
				txt = jl.group(1).strip()
				try:
					parsed = json.loads(txt)
				except Exception:
					continue
				# json-ld may be a list or object; handle both
				objs = parsed if isinstance(parsed, list) else [parsed]
				for obj in objs:
					if isinstance(obj, dict):
						# product-level description
						d = obj.get('description')
						if d:
							desc = d
							break
				if desc:
					break

		# final fallback: stripped body snippet
		if not desc:
			body_text = _strip_html(html)
			desc = body_text.strip()[:2000] if body_text else None

		# Return only the description (best-effort) as the 'text' field.
		return {"html": html, "text": desc}
	except Exception:
		return None
