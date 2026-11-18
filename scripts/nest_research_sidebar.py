"""Build-time nesting of lab notes inside the generated Quarto Book sidebar.

Quarto Books support parts and chapters but do not natively nest chapters under
other chapters. This transform groups neighboring chapter links by lab directory
in generated HTML, preserving all links and relying on Bootstrap's collapse API.
No third-party dependencies are required.
"""

from pathlib import Path
import re
import sys

LABS = {
    "computational-plasma-dynamics-lab": "Computational Plasma Dynamics Lab",
    "plasmawise": "PLASMAWISE",
    "rotating-detonation-engines-lab": "Rotating Detonation Engines Lab",
}
LEAF = '<li class="sidebar-item">'


def li_end(text: str, start: int) -> int:
    """Get the end of a <li> subtree, including any nested <li> elements."""
    depth = 0
    for tag in re.finditer(r'</?li\b[^>]*>', text[start:], flags=re.I):
        if tag.group().startswith('</'):
            depth -= 1
            if depth == 0:
                return start + tag.end()
        else:
            depth += 1
    raise ValueError("Unclosed sidebar list item")


def href_in(chunk: str) -> str:
    match = re.search(r'<a\s+[^>]*href="([^"]+)"[^>]*>', chunk)
    return match.group(1) if match else ""


def patch_lab(text: str, key: str, label: str) -> tuple[str, int]:
    sidebar_start = text.find('class="sidebar-menu-container"')
    if sidebar_start == -1:
        raise ValueError("Missing Quarto sidebar")
    sidebar_end = text.find('</nav>', sidebar_start)
    if sidebar_end == -1:
        raise ValueError("Missing sidebar boundary")
    lab_marker = "/research/" + key + "/index.html"
    href_matches = re.finditer(r'<a\s+[^>]*href="([^"]+)"[^>]*>', text[sidebar_start:sidebar_end])
    lab_anchor = next((sidebar_start + x.start() for x in href_matches if x.group(1).endswith(lab_marker)), None)
    if lab_anchor is None:
        raise ValueError("Missing lab link: " + key)
    lab_start = text.rfind(LEAF, sidebar_start, lab_anchor)
    if lab_start < 0:
        raise ValueError("Expected leaf item for lab: " + key)
    lab_stop = li_end(text, lab_start)
    lab_original = text[lab_start:lab_stop]
    if not href_in(lab_original).endswith(lab_marker):
        raise ValueError("Found incorrect lab item: " + key)
    if 'research-lab-item' in lab_original:
        return text, 0

    found = []
    pos = lab_stop
    while True:
        sibling_match = re.match(r'\s*<li class="sidebar-item">', text[pos:])
        if not sibling_match:
            break
        start = pos + sibling_match.start() + len(sibling_match.group()) - len(LEAF)
        end = li_end(text, start)
        sibling = text[start:end]
        href = href_in(sibling)
        if "/research/" + key + "/" not in href or href.endswith("/index.html"):
            break
        # Hide the book chapter number in this nested navigation entry only.
        # Keep Quarto's original chapter numbering and cross-references intact.
        sibling = re.sub(
            r'<span class="chapter-number">[^<]*</span>(?:&nbsp;|\\s)*',
            "",
            sibling,
            count=1,
        )
        found.append(sibling)
        pos = end
    if not found:
        return text, 0

    id_ = "research-lab-notes-" + key
    modified = lab_original.replace(LEAF, '<li class="sidebar-item sidebar-item-section research-lab-item">', 1)
    modified = modified.replace('<span class="menu-text">', f'<span class="menu-text" id="{id_}-label">', 1)
    button = (
        f'<button type="button" class="sidebar-item-toggle text-start research-lab-toggle" '
        f'data-bs-toggle="collapse" data-bs-target="#{id_}" '
        f'aria-controls="{id_}" aria-expanded="false" '
        f'aria-label="Toggle notes under {label}">'
        '<i class="bi bi-chevron-right ms-2" aria-hidden="true"></i>'
        '</button>\n'
    )
    close_div = modified.rfind('</div>')
    if close_div < 0:
        raise ValueError("Missing link container for lab: " + key)
    modified = modified[:close_div] + button + modified[close_div:]
    notes_html = '\n'.join(found)
    ul = (
        f'<ul id="{id_}" aria-labelledby="{id_}-label" '
        'class="collapse list-unstyled sidebar-section depth2 research-lab-children">\n'
        + notes_html + '\n</ul>\n'
    )
    close_li = modified.rfind('</li>')
    modified = modified[:close_li] + ul + modified[close_li:]
    return text[:lab_start] + modified + text[pos:], len(found)


def main() -> None:
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('_book')
    pages = sorted(output.rglob('*.html'))
    if not pages:
        raise SystemExit('No Quarto HTML files found')
    patched = 0
    for page in pages:
        original = page.read_text(encoding='utf-8')
        updated = original
        groups = 0
        for key, name in LABS.items():
            updated, notes = patch_lab(updated, key, name)
            groups += int(notes > 0)
        if updated != original:
            page.write_text(updated, encoding='utf-8')
            patched += 1
        if groups != 1:
            raise RuntimeError(f'{page}: expected 1 nested lab group, found {groups}')
    print(f'Nested lab notes successfully in {patched}/{len(pages)} HTML pages')
    if patched != len(pages):
        raise RuntimeError('Not all pages received sidebar nesting')


if __name__ == '__main__':
    main()
