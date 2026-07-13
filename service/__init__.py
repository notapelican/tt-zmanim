"""TTCC sheet service.

A thin HTTP wrapper around the fixture-validated Python engine (``engine/``),
so the WordPress plugin (PHP) can generate block data and rendered output over
HTTPS. The service imports the engine unchanged and never recomputes or
re-rounds a time: every value comes verbatim from ``engine.assemble.generate``.

Stateless and computation-only. All persistence lives in WordPress.
"""
