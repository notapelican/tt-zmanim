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

The page box is a fixed 210x297mm here, but the fit pass only ever reads the
box it is given, so a renderer may re-shape it in CSS — the share-image
rasterizer (service/raster.py) puts the sheet on a square page for a 1:1
WhatsApp canvas, and the layout spec above then applies to that square.

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


# Runs in-page after load (and after web fonts settle): for each .page, search
# for the largest uniform content scale that still fits the printable box, and
# centre what is left over. Sets data-ttcc-fitted="1" on <html> when done so the
# rasterizer / preview can wait for a stable layout.
FIT_JS = """
<script id="ttcc-fit">
(function () {
  var MIN = %(min)s;
  // The ceiling stops a sparse A4 page blowing type up comically large. A share
  // image wants the opposite — filling the frame is the point — so a renderer
  // can raise it with the --ttcc-fit-max custom property on :root. Whatever it
  // is set to, fitPage's search still holds the content inside the page.
  var MAX = parseFloat(
    getComputedStyle(document.documentElement).getPropertyValue('--ttcc-fit-max')
  ) || %(max)s;
  // 'fill' (default): scale content to fill the page. 'fixed': show content at
  // its chosen (base) size and only shrink to prevent overflow — so the
  // content-size control has a visible effect.
  var MODE = document.documentElement.getAttribute('data-ttcc-fit') || 'fill';
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
  // Leftover height is split above and below the block, so a page that cannot
  // grow all the way (the MAX clamp, 'fixed' sizing, or a row that has run out of
  // width — see fitPage) reads as a centred sheet rather than content pinned to
  // the top with all the paper at the foot.
  // translateY sits left of scale() in the list, so its px are page px.
  function centreY(c, H, s) {
    // Balance what is DRAWN (offsetHeight), not the flow height: a trailing
    // margin can push scrollHeight past the painted box and would bias the
    // block upwards. Capped by the room the flow actually leaves, so trailing
    // whitespace is all that a tight page can ever lose.
    var slack = H - c.offsetHeight * s;
    var room = H - c.scrollHeight * s;
    var t = Math.max(0, Math.min(slack / 2, room));
    c.style.transform = ( t > 1 ? 'translateY(' + t + 'px) ' : '' ) + 'scale(' + s + ')';
  }
  function fitPage(page) {
    var m = page.querySelector('.page-margin');
    var c = page.querySelector('.page-content');
    if (!m || !c) { return; }
    var W = m.clientWidth, H = m.clientHeight;
    if (!W || !H) { return; }
    // The .fit-line headers are nowrap and are shrunk to fit AFTERWARDS, by
    // fitLines — so mid-search they legitimately stick out past the content
    // width. Clip them to their own box (which is the printable width, where
    // .page-margin would clip them anyway) so they stay out of the width test
    // below; only the body rows should hold the scale back.
    var fl = page.querySelectorAll('.fit-line'), fi;
    for (fi = 0; fi < fl.length; fi++) { fl[fi].style.overflow = 'hidden'; }
    // The content is laid out at width W/s and drawn at scale s, so its drawn
    // width is always W: a larger s means a NARROWER design width, hence more
    // wrapping. Two things can therefore break as s grows, and both break
    // monotonically:
    //   - the block gets taller than the page (scrollHeight * s > H);
    //   - a row runs out of room for its label, which never wraps, and spills
    //     sideways out of its cell (scrollWidth > clientWidth).
    // So "does scale v still fit?" is monotone in v and the largest fitting
    // scale can be bisected for. (Iterating s = H/scrollHeight instead — the
    // obvious fixed point — oscillates on a tall or narrow box and can settle
    // well below the true fit.)
    function fits(v) {
      c.style.width = (W / v) + 'px';
      c.style.transform = 'scale(' + v + ')';
      return c.scrollHeight * v <= H + 0.5 && c.scrollWidth <= c.clientWidth + 0.5;
    }
    // 'fixed' sizing never magnifies: the base size is the operator's choice, so
    // 1 is the ceiling and the search only ever shrinks to prevent overflow.
    var lo = MIN, hi = (MODE === 'fixed') ? 1 : MAX, s, i;
    if (fits(hi)) {
      s = hi;
    } else {
      for (i = 0; i < 16; i++) {           // ~1e-4 of the range: sub-pixel
        var mid = (lo + hi) / 2;
        if (fits(mid)) { lo = mid; } else { hi = mid; }
      }
      s = lo;                              // MIN if even that overflows
      fits(s);                             // re-apply: the last probe was `hi`
    }
    centreY(c, H, s);
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
