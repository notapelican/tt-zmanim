"""Shared A4 pagination for the HTML renderers (classic engine + modern service).

Layout spec (accepted 2026-07-14):
  - single week  -> one full A4 page; content fills the page inside a
    whitespace margin and never overflows to a second page.
  - multi-week   -> 4 blocks per page in a 2x2 grid, filling the page.
    Additional blocks overflow to further 4-up pages, except:
      * a 2-block remainder renders as two full-height columns side by side;
      * a 1-block remainder renders as a single full page;
      * a 3-block remainder stays in the 2x2 grid (one empty cell).
  - yom-tov day blocks occupy grid cells exactly like weeks.

Every page is an explicit fixed 210x297mm box. The embedded fit script
(FIT_JS) measures each page's content and applies a uniform scale so the
content fills the printable area without overflowing — larger type on sparse
pages, shrink-to-fit on dense ones. The same HTML therefore looks identical
in the dashboard preview iframe, the printed PDF and the PNG raster (all
three execute the script before display/print).

Layout/styling only — never computes or re-rounds a time.
"""
from __future__ import annotations

# Content scale clamps for the fit pass. MIN stops dense pages from becoming
# unreadable (operators should split the range instead); MAX stops sparse
# pages from blowing type up comically large.
FIT_MIN = 0.5
FIT_MAX = 1.7


def paginate(cells: list) -> list[tuple[str, list]]:
    """Chunk cells (pre-rendered block HTML) into pages per the layout spec.

    Returns [(layout, cells)] where layout is "grid" (2x2), "two" (two
    side-by-side full-height columns) or "one" (single full page).
    """
    pages: list[tuple[str, list]] = []
    i, n = 0, len(cells)
    while n - i > 4:
        pages.append(("grid", cells[i:i + 4]))
        i += 4
    rest = n - i
    if rest == 1:
        pages.append(("one", cells[i:]))
    elif rest == 2:
        pages.append(("two", cells[i:]))
    elif rest > 0:  # 3 or 4
        pages.append(("grid", cells[i:]))
    return pages


def page_css(margin_mm: float = 12) -> str:
    """Structural CSS for the fixed A4 page boxes and the cell layouts.

    Renderers add their own skin on top (dividers, gaps, typography). The
    print margin lives INSIDE the page box (.page-margin) so @page prints
    edge-to-edge and preview/PDF geometry match exactly.
    """
    m = f"{margin_mm:g}mm"
    return f"""
@page {{ size:A4; margin:0; }}
html, body {{ margin:0; padding:0; }}
.page {{ position:relative; width:210mm; height:297mm; overflow:hidden;
         background:#fff; page-break-after:always; break-after:page; }}
.page:last-child {{ page-break-after:auto; break-after:auto; }}
.page-margin {{ position:absolute; left:{m}; top:{m}; right:{m}; bottom:{m};
                overflow:hidden; }}
.page-content {{ transform-origin:0 0; width:100%; }}
.page-cells {{ min-width:0; }}
.page-cells.grid, .page-cells.two {{ display:grid; grid-template-columns:1fr 1fr; }}
.page-cells.one {{ display:block; }}
.page-cells > .cell {{ min-width:0; }}
"""


# Runs in-page after load (and after web fonts settle): for each .page,
# iterate width/scale to a fixed point where the content's displayed height
# fills the printable box, then back off until nothing overflows. Sets
# data-ttcc-fitted="1" on <html> when done so the rasterizer / preview can
# wait for a stable layout.
FIT_JS = """
<script id="ttcc-fit">
(function () {
  var MIN = %(min)s, MAX = %(max)s;
  function fitLines(root) {
    // Headers marked .fit-line must NEVER wrap: shrink the font until the
    // text fits on one line. Proportional first jump (text width scales with
    // font size), then fine steps; absolute floor of 6px.
    var els = root.querySelectorAll('.fit-line'), i;
    for (i = 0; i < els.length; i++) {
      var el = els[i];
      el.style.fontSize = ''; // re-measure from the styled size
      var size = parseFloat(getComputedStyle(el).fontSize);
      var w = el.clientWidth, sw = el.scrollWidth;
      if (!size || !w || sw <= w + 0.5) { continue; }
      size = Math.max(6, size * (w / sw) * 0.98);
      el.style.fontSize = size + 'px';
      var guard = 0;
      while (el.scrollWidth > el.clientWidth + 0.5 && size > 6 && guard++ < 30) {
        size -= 0.25;
        el.style.fontSize = size + 'px';
      }
    }
  }
  function fitPage(page) {
    var m = page.querySelector('.page-margin');
    var c = page.querySelector('.page-content');
    if (!m || !c) { return; }
    var W = m.clientWidth, H = m.clientHeight;
    if (!W || !H) { return; }
    var s = 1, k, h, next;
    for (k = 0; k < 6; k++) {
      c.style.width = (W / s) + 'px';
      c.style.transform = 'scale(' + s + ')';
      h = c.scrollHeight;
      if (!h) { return; }
      next = Math.max(MIN, Math.min(MAX, H / h));
      if (Math.abs(next - s) < 0.004) { s = next; break; }
      s = next;
    }
    c.style.width = (W / s) + 'px';
    c.style.transform = 'scale(' + s + ')';
    var guard = 0;
    while (c.scrollHeight * s > H + 0.5 && s > MIN && guard++ < 60) {
      s -= 0.01;
      c.style.width = (W / s) + 'px';
      c.style.transform = 'scale(' + s + ')';
    }
  }
  function fitViewport() {
    // Narrow viewports (public embeds on phones): shrink whole pages to the
    // viewport width. The A4 ratio stays locked; wide viewports are untouched.
    var page = document.querySelector('.page');
    if (!page) { return; }
    var vw = document.documentElement.clientWidth, pw = page.offsetWidth;
    if (vw && pw && vw < pw) { document.body.style.zoom = vw / pw; }
    else { document.body.style.zoom = ''; }
  }
  function fitAll() {
    var pages = document.querySelectorAll('.page'), i;
    // fitPage first so .fit-line headers are measured at the page's final
    // content width; shrinking them afterwards only reduces height.
    for (i = 0; i < pages.length; i++) { fitPage(pages[i]); fitLines(pages[i]); }
    fitViewport();
    document.documentElement.setAttribute('data-ttcc-fitted', '1');
  }
  window.addEventListener('resize', fitViewport);
  function run() {
    if (document.fonts && document.fonts.ready && document.fonts.ready.then) {
      document.fonts.ready.then(fitAll, fitAll);
    } else { fitAll(); }
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', run);
  } else { run(); }
})();
</script>
""" % {"min": FIT_MIN, "max": FIT_MAX}


def pages_html(pages: list[tuple[str, list]], *, chrome: str = "",
               foot: str = "", page_class: str = "",
               one_class: str = "single", many_class: str = "multi") -> str:
    """Assemble page divs. ``chrome`` (header HTML) repeats on every page;
    ``foot`` renders once, on the last page. "one"-layout pages get
    ``one_class`` sizing, grid/two pages get ``many_class``."""
    out: list[str] = []
    for pi, (layout, cells) in enumerate(pages):
        last = pi == len(pages) - 1
        size_cls = one_class if layout == "one" else many_class
        cls = " ".join(c for c in ("page", page_class, size_cls) if c)
        cell_html = "".join(f'<div class="cell">{c}</div>' for c in cells)
        out.append(
            f'<div class="{cls}"><div class="page-margin"><div class="page-content">'
            f'{chrome}<div class="page-cells {layout}">{cell_html}</div>'
            f'{foot if last else ""}'
            '</div></div></div>')
    return "".join(out)
