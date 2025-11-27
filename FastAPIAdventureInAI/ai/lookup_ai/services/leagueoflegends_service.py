from typing import Optional, Dict, Any, List
import re
import json
from ai.services.http_service import fetch_html, _strip_html


async def extract_leagueoflegends_champion(url: str) -> Optional[Dict[str, Any]]:
    """Extractor for leagueoflegends.com champion pages.

    Prefers structured __NEXT_DATA__ payload. Falls back to meta description or
    stripped HTML when necessary.
    """
    try:
        payload = await fetch_html(url)
        if not payload or not isinstance(payload, dict):
            return None
        html = payload.get("html")
        if not html:
            return None

        # Attempt to find the Next.js serialized data blob
        data = None
        m = re.search(r'<script[^>]*id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>', html, re.I | re.S)
        if m:
            txt = m.group(1).strip()
            try:
                data = json.loads(txt)
            except Exception:
                data = None

        pieces: List[str] = []

        if data:
            page = data.get("props", {}).get("pageProps", {}).get("page", {})

            # title / subtitle / description
            title = page.get("title") or page.get("metaTitle")
            subtitle = None
            blades = page.get("blades") or []

            # find character masthead blade
            masthead = None
            for b in blades:
                if isinstance(b, dict) and b.get("type") == "characterMasthead":
                    masthead = b
                    break

            # gather description from masthead
            if masthead and isinstance(masthead, dict):
                subtitle = masthead.get("subtitle")
                desc = None
                dobj = masthead.get("description") or masthead.get("content") or {}
                if isinstance(dobj, dict):
                    desc = dobj.get("body") or dobj.get("text")
                elif isinstance(dobj, str):
                    desc = dobj
                if desc:
                    pieces.append(desc)

            # fallback to top-level description
            if not pieces:
                desc_top = page.get("description") or page.get("metaDescription")
                if isinstance(desc_top, str) and desc_top:
                    pieces.append(desc_top)

            # title/subtitle line
            title_line = "".join([s for s in [title, subtitle] if s])
            if title_line:
                pieces.insert(0, title_line)

            # role / difficulty
            if masthead and isinstance(masthead, dict):
                try:
                    role_block = masthead.get("role") or {}
                    roles = role_block.get("roles") if isinstance(role_block, dict) else None
                    if roles and isinstance(roles, list):
                        role_names = [r.get("name") for r in roles if isinstance(r, dict) and r.get("name")]
                        if role_names:
                            pieces.append("Role: " + " / ".join(role_names))
                except Exception:
                    pass

                diff = masthead.get("difficulty") if masthead.get("difficulty") else None
                if isinstance(diff, dict):
                    diff_name = diff.get("name") or (str(diff.get("value")) if diff.get("value") else None)
                    if diff_name:
                        pieces.append("Difficulty: " + str(diff_name))

            # Abilities
            abilities: List[str] = []
            for b in blades:
                if not isinstance(b, dict):
                    continue
                header = b.get("header")
                is_abilities = (
                    b.get("type") == "iconTab"
                    or (isinstance(header, dict) and header.get("title") and "ABILITY" in header.get("title", "").upper())
                    or (isinstance(header, str) and "ABILITY" in header.upper())
                )
                if not is_abilities:
                    continue

                groups = b.get("groups") or []
                for g in groups:
                    if not isinstance(g, dict):
                        continue
                    label = g.get("label") or (g.get("content") or {}).get("title")
                    desc = None
                    content = g.get("content") or {}
                    if isinstance(content, dict):
                        d1 = content.get("description")
                        if isinstance(d1, dict):
                            desc = d1.get("body") or d1.get("text")
                        elif isinstance(d1, str):
                            desc = d1
                        if not desc:
                            desc = content.get("body") or content.get("text")
                    if label and desc:
                        subtitle_field = content.get("subtitle") or ""
                        abilities.append(f"{label} ({subtitle_field}): {desc}")
                    elif label:
                        abilities.append(label)

                if abilities:
                    break

            if abilities:
                pieces.append("ABILITIES:\n" + "\n\n".join(abilities))

            # Skins
            skins: List[str] = []
            for b in blades:
                if not isinstance(b, dict):
                    continue
                header = b.get("header")
                is_skins = (
                    b.get("type") == "landingMediaCarousel"
                    or (isinstance(header, dict) and header.get("title") == "Available Skins")
                )
                if not is_skins:
                    continue
                groups = b.get("groups") or []
                for g in groups:
                    if isinstance(g, dict):
                        lab = g.get("label")
                        if lab:
                            skins.append(lab)
                if skins:
                    break

            if skins:
                pieces.append("Available Skins: " + ", ".join(skins))

        # final fallbacks when no structured pieces
        if not pieces:
            m = re.search(r'<meta\s+name=["\']description["\']\s+content=["\']([^"\']+)["\']', html, re.I)
            if m:
                pieces.append(m.group(1).strip())
            else:
                m2 = re.search(r'<meta\s+property=["\']og:description["\']\s+content=["\']([^"\']+)["\']', html, re.I)
                if m2:
                    pieces.append(m2.group(1).strip())
                else:
                    body_text = _strip_html(html)
                    if body_text and body_text.strip():
                        pieces.append(body_text.strip()[:3000])

        out_text = "\n\n".join(pieces)
        return {"html": html, "text": out_text}

    except Exception:
        return None
