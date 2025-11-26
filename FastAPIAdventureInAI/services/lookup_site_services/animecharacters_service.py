"""Extractor for animecharactersdatabase.com character pages.

Scrapes the Profile block and trait table from pages like:
https://www.animecharactersdatabase.com/characters.php?id=22961

Returns a dict with keys: html, text, profile, traits
"""
from typing import Optional, Dict, Any
import re
from services.http_service import fetch_html, _strip_html


async def extract_animecharacters(url: str) -> Optional[Dict[str, Any]]:
    try:
        payload = await fetch_html(url)
        if not payload:
            return None
        html = payload.get("html") if isinstance(payload, dict) else None
        if not html:
            return None

        out: Dict[str, Any] = {"html": html}

        # Find the main bo2 content block (may be used in multiple places)
        # Match a div whose class contains 'bo2'
        div_m = re.search(r'<div[^>]*class=["\']?[^"\']*\bbo2\b[^"\']*["\']?[^>]*>([\s\S]*?)</div>', html, re.I)
        profile_text = None
        div_html = None
        if div_m:
            div_html = div_m.group(1)
            # Look specifically for a Profile section inside that div
            prof_m = re.search(r'<h3[^>]*>\s*Profile\s*</h3>([\s\S]*)', div_html, re.I)
            if prof_m:
                # take everything after the <h3>Profile</h3> inside the div
                prof_html = prof_m.group(1)
                # stop at another <h3> if present
                stop = re.search(r'<h3[^>]*>', prof_html, re.I)
                if stop:
                    prof_html = prof_html[: stop.start()]
                profile_text = _strip_html(prof_html).strip()

        # Extract trait table: be more robust by searching inside the profile div for a table
        # containing a 'Trait' header. Fall back to previous heuristics if needed.
        traits: Dict[str, str] = {}
        table_html = None

        if div_html:
            # find tables inside the div and pick the one that has a TH containing 'Trait'
            for t in re.finditer(r'(<table[^>]*>[\s\S]*?</table>)', div_html, re.I):
                t_html = t.group(1)
                if re.search(r'<th[^>]*>\s*Trait\b', t_html, re.I):
                    # strip outer <table> wrapper to keep consistent with earlier code
                    inner = re.sub(r'^<table[^>]*>|</table>$', '', t_html, flags=re.I)
                    table_html = inner
                    break

        if not table_html:
            # try to find a table by class globally (lenient fallback: require 'zero' and 'bo2')
            table_m = re.search(r'<table[^>]*class=["\']?[^"\']*\bzero\b[^"\']*\bbo2\b[^"\']*["\']?[^>]*>([\s\S]*?)</table>', html, re.I)
            if not table_m:
                # even more lenient: any table that contains a TH with 'Trait'
                for t in re.finditer(r'(<table[^>]*>[\s\S]*?</table>)', html, re.I):
                    if re.search(r'<th[^>]*>\s*Trait\b', t.group(1), re.I):
                        table_html = re.sub(r'^<table[^>]*>|</table>$', '', t.group(1), flags=re.I)
                        break
            else:
                table_html = table_m.group(1)

        if table_html:
            # iterate rows and capture th and first td
            for tr in re.finditer(r'<tr[^>]*>([\s\S]*?)</tr>', table_html, re.I):
                row_html = tr.group(1)
                th_m = re.search(r'<th[^>]*>([\s\S]*?)</th>', row_html, re.I)
                td_m = re.search(r'<td[^>]*>([\s\S]*?)</td>', row_html, re.I)
                if th_m and td_m:
                    k = _strip_html(th_m.group(1)).strip()
                    v = _strip_html(td_m.group(1)).strip()
                    if k:
                        traits[k] = v
        # Fallback: if traits empty or missing expected keys, extract specific common trait rows
        expected_keys = {
            "Gender": r'Gender',
            "Eye Color": r'Eye Color',
            "Hair Color": r'Hair Color',
            "Hair Length": r'Hair Length',
            "Apparent Age": r'Apparent Age',
            "Animal Ears": r'Animal Ears',
        }
        if not traits or any(k not in traits for k in expected_keys):
            for out_key, label in expected_keys.items():
                if out_key in traits:
                    continue
                # Look for a TH containing the label and the following TD
                m = re.search(r'<th[^>]*>\s*(?:<a[^>]*>)?\s*' + re.escape(label) + r'(?:<[^>]*>)?\s*</th>\s*<td[^>]*>([\s\S]*?)</td>', html, re.I)
                if not m:
                    # sometimes the label appears without the exact spacing or inside links; try a looser search
                    m = re.search(r'<th[^>]*>\s*(?:<[^>]*>\s*)*' + re.escape(label) + r'(?:\s*<[^>]*>)*\s*</th>\s*<td[^>]*>([\s\S]*?)</td>', html, re.I)
                if m:
                    val = _strip_html(m.group(1)).strip()
                    if val:
                        traits[out_key] = val

        # Ensure we have a traits map (may be empty values)
        if not traits:
            traits = {}
            for key in expected_keys.keys():
                traits.setdefault(key, "")

        # Attempt to extract a full traits table with columns (Trait | Appears as | Official)
        traits_table = []
        try:
            # find a table that contains headers 'Trait' and 'Appears'
            table_full_m = re.search(r'<table[^>]*>([\s\S]*?<th[^>]*>\s*Trait\b[\s\S]*?<th[^>]*>\s*Appears as\b[\s\S]*?)</table>', html, re.I)
            if table_full_m:
                full_table_html = table_full_m.group(0)
                # Extract header order
                headers = [h.lower().strip() for h in re.findall(r'<th[^>]*>([\s\S]*?)</th>', full_table_html, re.I)]
                # Normalize header names to keys
                norm_headers = []
                for h in headers:
                    t = _strip_html(h).lower()
                    if 'trait' in t:
                        norm_headers.append('Trait')
                    elif 'appear' in t:
                        norm_headers.append('Appears as')
                    elif 'official' in t:
                        norm_headers.append('Official')
                    else:
                        norm_headers.append(_strip_html(h).strip())
                # Iterate rows
                for row in re.finditer(r'<tr[^>]*>([\s\S]*?)</tr>', full_table_html, re.I):
                    row_html = row.group(1)
                    # extract td/th cells in order
                    cells = re.findall(r'<t[dh][^>]*>([\s\S]*?)</t[dh]>', row_html, re.I)
                    if not cells or len(cells) <2:
                        continue
                    # Map cells to headers
                    row_map = {'Trait': '', 'Appears as': '', 'Official': ''}
                    for i, cell in enumerate(cells[: len(norm_headers)]):
                        key = norm_headers[i]
                        val = _strip_html(cell).strip()
                        if key in row_map:
                            row_map[key] = val
                        else:
                            row_map[key] = val
                    # Only include rows that look like trait rows (Trait key present)
                    if row_map.get('Trait'):
                        traits_table.append(row_map)
        except Exception:
            traits_table = []

        # If we didn't find a full table, build one from the expected keys
        if not traits_table:
            for k in expected_keys.keys():
                traits_table.append({
                    'Trait': k,
                    'Appears as': traits.get(k, ''),
                    'Official': ''
                })

        # Do not expose `traits_table` in the returned object — it is not used by callers.
        # traits_table is retained locally if needed for future internal use.

        # Build sections: denormalize traits into a single string and include profile
        denorm_traits = "\n".join([f"{k}: {v}" for k, v in traits.items()]) if traits else ""
        sections: Dict[str, str] = {
            'traits': denorm_traits,
            'profile': profile_text or ""
        }
        out['sections'] = sections

        # Compose a simple text summary (keep existing behavior)
        parts = []
        if profile_text:
            parts.append("PROFILE:\n" + profile_text)
        if traits:
            tlines = [f"{k}: {v}" for k, v in traits.items()]
            parts.append("TRAITS:\n" + "\n".join(tlines))

        out_text = "\n\n---\n\n".join(parts) if parts else _strip_html(html)[:2000]
        out["text"] = out_text
        print(out)
        return out
    except Exception:
        return None
